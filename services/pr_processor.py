import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

from agents.developer_agent import DeveloperAgent
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class PRProcessingResult:
    """Result of PR processing."""
    success: bool
    message: str
    actions_taken: List[Dict[str, Any]]
    pr_number: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'success': self.success,
            'message': self.message,
            'actions_taken': self.actions_taken,
            'pr_number': self.pr_number
        }

class PRProcessor:
    """Service for processing PRs using the DeveloperAgent."""
    
    def __init__(self, config: Config, github_integration=None, notification_manager=None, llm_integration=None):
        """Initialize the PR processor.
        
        Args:
            config: Application configuration
            github_integration: GitHub integration instance
            notification_manager: Notification manager instance
            llm_integration: LLM integration instance (optional, will be initialized from config if not provided)
        """
        self.config = config
        self.github_integration = github_integration
        self.notification_manager = notification_manager
        
        # Initialize LLM integration if not provided
        if llm_integration is None and hasattr(config, 'perplexity') and hasattr(config.perplexity, 'api_key'):
            from integrations.perplexity_integration import PerplexityIntegration
            llm_integration = PerplexityIntegration(
                api_key=config.perplexity.api_key,
                model=getattr(config.perplexity, 'model', 'llama-3.1-70b-instruct')
            )
        
        self.llm_integration = llm_integration
        
        # Mock the dependencies if not provided
        if notification_manager is None:
            from unittest.mock import MagicMock
            notification_manager = MagicMock()
        
        # Initialize the developer agent with all required dependencies
        self.developer_agent = DeveloperAgent(
            llm_integration=self.llm_integration,
            github_integration=github_integration,
            notification_manager=notification_manager,
            config=config,
            workspace_dir=getattr(config.agent, 'workspace_dir', './workspace')
        )
        
    async def process_pr(self, pr_info) -> PRProcessingResult:
        """Process a pull request using CrewAI.
        
        Args:
            pr_info: PR information
            
        Returns:
            PRProcessingResult: Result of the processing
        """
        # Handle different input types to get PR info
        if isinstance(pr_info, int):
            pr_data = self.github_integration.get_pr_info_dict(pr_info)
        elif hasattr(pr_info, 'number'):
            pr_data = self.github_integration.get_pr_info_dict(pr_info.number)
        else:
            pr_data = pr_info
            
        if not pr_data:
            return PRProcessingResult(
                success=False,
                message="Could not retrieve PR information",
                actions_taken=[],
                pr_number=0
            )

        pr_number = pr_data.get('number')
        logger.info(f"Processing PR #{pr_number} using CrewAI Orchestration...")
        
        try:
            review_result = await self.developer_agent.review_pr(pr_data)
            
            if not review_result.get('success', False):
                return PRProcessingResult(
                    success=False,
                    message=review_result.get('message', 'Review failed'),
                    actions_taken=[],
                    pr_number=pr_number
                )

            pr_number = pr_data.get('number')
            logger.info(f"Processing PR #{pr_number} using CrewAI...")
            
            review_result = await self.developer_agent.review_pr(pr_data)
            
            if review_result.get('success', False):
                return PRProcessingResult(
                    success=False,
                    message=review_result.get('message', 'Review failed'),
                    actions_taken=[],
                    pr_number=pr_number
                )

            # If review suggests improvements, apply them
            if review_result.get('suggested_changes'):
                logger.info(f"Applying {len(review_result['suggested_changes'])} suggested changes...")
                
                # Create new branch for improvements
                import time
                timestamp = int(time.time())
                improvement_branch = f"improvements/pr-{pr_number}-{timestamp}"
                
                branch_created = self.github_integration.create_branch(
                    repo=f"{self.config.github.repo_owner}/{self.config.github.repo_name}",
                    branch=improvement_branch,
                    base_branch=pr_data.get('base_branch', 'main')
                )
                
                if not branch_created:
                    logger.error(f"Failed to create branch {improvement_branch}")
                    return PRProcessingResult(
                        success=False,
                        message="Failed to create improvement branch",
                        actions_taken=[],
                        pr_number=pr_number
                    )
                
                # Apply suggested changes
                changes_applied = []
                for change in review_result['suggested_changes']:
                    file_path = change.get('file_path', '')
                    new_content = change.get('new_content', '')
                    
                    if file_path and new_content:
                        file_updated = self.github_integration.update_file(
                            repo=f"{self.config.github.repo_owner}/{self.config.github.repo_name}",
                            path=file_path,
                            content=new_content,
                            message=f"Apply improvement: {change.get('description', 'Code improvement')}",
                            branch=improvement_branch
                        )
                        
                        if file_updated:
                            changes_applied.append({
                                'action': 'file_updated',
                                'file_path': file_path,
                                'details': f"Updated {file_path}"
                            })
                            logger.info(f"Updated file: {file_path}")
                        else:
                            logger.error(f"Failed to update file: {file_path}")
                
                # Create PR with improvements
                if changes_applied:
                    pr_url = self.github_integration.create_pull_request(
                        repo=f"{self.config.github.repo_owner}/{self.config.github.repo_name}",
                        title=f"Improvements for PR #{pr_number}",
                        body=f"This PR implements improvements suggested by AI review for PR #{pr_number}.\n\nChanges made:\n" + 
                              "\n".join([f"- {change.get('description', 'Code improvement')}" for change in review_result['suggested_changes']]),
                        head=improvement_branch,
                        base=pr_data.get('base_branch', 'main')
                    )
                    
                    if pr_url:
                        changes_applied.append({
                            'action': 'pr_created',
                            'pr_url': pr_url,
                            'details': f"Created improvement PR: {pr_url}"
                        })
                        logger.info(f"Created improvement PR: {pr_url}")
                        
                        # Add comment to original PR
                        comment = f"I've created an improvement PR with the suggested changes: {pr_url}"
                        self.github_integration.create_pr_comment(pr_number, comment)
                        
                    else:
                        logger.error("Failed to create improvement PR")
                
                return PRProcessingResult(
                    success=True,
                    message=f"PR #{pr_number} processed successfully",
                    actions_taken=changes_applied,
                    pr_number=pr_number
                )
            else:
                # No changes suggested, just review
                return PRProcessingResult(
                    success=True,
                    message=f"PR #{pr_number} reviewed successfully (no changes needed)",
                    actions_taken=[{
                        'action': 'review_completed',
                        'details': 'Review completed - no changes needed'
                    }],
                    pr_number=pr_number
                )
                
        except Exception as e:
            logger.error(f"Error processing PR: {str(e)}", exc_info=True)
            return PRProcessingResult(
                success=False,
                message=f"Error processing PR: {str(e)}",
                actions_taken=[],
                pr_number=pr_number if 'pr_number' in locals() else 0
            )
    
    async def review_pr_only(self, pr_info) -> PRProcessingResult:
        """Review a PR without making changes (review-only mode).
        
        Args:
            pr_info: PR information
            
        Returns:
            PRProcessingResult: Result of the review-only processing
        """
        # Handle different input types to get PR info
        if isinstance(pr_info, int):
            pr_data = self.github_integration.get_pr_info_dict(pr_info)
        elif hasattr(pr_info, 'number'):
            pr_data = self.github_integration.get_pr_info_dict(pr_info.number)
        else:
            pr_data = pr_info
            
        if not pr_data:
            return PRProcessingResult(
                success=False,
                message="Could not retrieve PR information",
                actions_taken=[],
                pr_number=0
            )

        pr_number = pr_data.get('number')
        logger.info(f"Reviewing PR #{pr_number} (review-only mode)...")
        
        try:
            review_result = await self.developer_agent.review_pr(pr_data)
            
            if review_result.get('success', False):
                return PRProcessingResult(
                    success=False,
                    message=review_result.get('message', 'Review failed'),
                    actions_taken=[],
                    pr_number=pr_number
                )
            
            # Add review comment to PR
            if review_result.get('should_comment', False):
                comment = review_result.get('comment', 'AI review completed')
                if comment:
                    comment_added = self.github_integration.create_pr_comment(pr_number, comment)
                    if comment_added:
                        logger.info(f"Added review comment to PR #{pr_number}")
                        return PRProcessingResult(
                            success=True,
                            message=f"PR #{pr_number} reviewed successfully",
                            actions_taken=[{
                                'action': 'review_comment_added',
                                'details': 'Added review comment'
                            }],
                            pr_number=pr_number
                        )
                    else:
                        logger.error(f"Failed to add review comment to PR #{pr_number}")
                        return PRProcessingResult(
                            success=False,
                            message="Failed to add review comment",
                            actions_taken=[],
                            pr_number=pr_number
                        )
                else:
                    logger.warning("No comment to add to PR")
            
            return PRProcessingResult(
                success=True,
                message=f"PR #{pr_number} reviewed successfully",
                actions_taken=[{
                    'action': 'review_completed',
                    'details': 'Review completed'
                }],
                pr_number=pr_number
            )
                
        except Exception as e:
            logger.error(f"Error reviewing PR: {str(e)}", exc_info=True)
            return PRProcessingResult(
                success=False,
                message=f"Error reviewing PR: {str(e)}",
                actions_taken=[],
                pr_number=pr_number if 'pr_number' in locals() else 0
            )
