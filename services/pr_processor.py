#!/usr/bin/env python3
"""
PR Processor Service

Handles the processing of pull requests using the DeveloperAgent.
"""
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
                model=getattr(config.perplexity, 'model', 'sonar-pro')
            )
        
        self.llm_integration = llm_integration
        
        # Initialize the developer agent with all required dependencies
        self.developer_agent = DeveloperAgent(
            llm_integration=self.llm_integration,
            github_integration=github_integration,
            notification_manager=notification_manager,
            config=config,
            workspace_dir=getattr(config.agent, 'workspace_dir', './workspace')
        )
        
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
        """Process a pull request.
        
        Args:
            pr_info: PR information as either a dict, PRInfo object, or PR number
            
        Returns:
            PRProcessingResult: Result of the processing
        """
        # Handle different input types
        if isinstance(pr_info, int):  # PR number
            pr_number = pr_info
            # Get the full PR info dict with the structure expected by the developer agent
            pr_data = self.github_integration.get_pr_info_dict(pr_number)
            if not pr_data:
                return PRProcessingResult(
                    success=False,
                    message=f"Could not retrieve PR #{pr_number} information",
                    actions_taken=[],
                    pr_number=pr_number
                )
            pr_title = pr_data.get('title', 'No title')
        elif hasattr(pr_info, 'number'):  # PRInfo object
            pr_number = pr_info.number
            pr_title = pr_info.title
            # Get the full PR info dict with the structure expected by the developer agent
            pr_data = self.github_integration.get_pr_info_dict(pr_number)
            if not pr_data:
                return PRProcessingResult(
                    success=False,
                    message=f"Could not retrieve PR #{pr_number} information",
                    actions_taken=[],
                    pr_number=pr_number
                )
        else:  # dict
            pr_number = pr_info.get('number')
            pr_title = pr_info.get('title', 'No title')
            # If it's already a dict, check if it has the required structure
            if 'base' in pr_info and 'repo' in pr_info.get('base', {}):
                pr_data = pr_info
            else:
                # Get the full PR info dict with the structure expected by the developer agent
                pr_data = self.github_integration.get_pr_info_dict(pr_number)
                if not pr_data:
                    return PRProcessingResult(
                        success=False,
                        message=f"Could not retrieve PR #{pr_number} information",
                        actions_taken=[],
                        pr_number=pr_number
                    )
            
        logger.info(f"Processing PR #{pr_number}: {pr_title}")
        
        try:
            # 1. Get PR diff and files
            try:
                diff = self.github_integration.get_pr_diff(pr_number)
                files = self.github_integration.get_pr_files(pr_number)
                
                if not diff and not files:
                    error_msg = "Could not retrieve PR diff or files - empty response"
                    logger.error(error_msg)
                    return PRProcessingResult(
                        success=False,
                        message=error_msg,
                        actions_taken=[],
                        pr_number=pr_number
                    )
                    
            except Exception as e:
                error_msg = f"Error fetching PR details: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return PRProcessingResult(
                    success=False,
                    message=error_msg,
                    actions_taken=[],
                    pr_number=pr_number
                )
            
            # 2. Review PR
            try:
                # Determine the language from the first modified file
                language = 'python'  # Default to python
                if files and len(files) > 0:
                    # Get the first file and extract its extension
                    first_file = files[0].get('filename', '')
                    if '.' in first_file:
                        ext = first_file.split('.')[-1].lower()
                        # Map common extensions to languages
                        ext_to_lang = {
                            'py': 'python',
                            'js': 'javascript',
                            'ts': 'typescript',
                            'java': 'java',
                            'go': 'go',
                            'rs': 'rust',
                            'rb': 'ruby',
                            'php': 'php',
                            'c': 'c',
                            'cpp': 'cpp',
                            'h': 'c',
                            'hpp': 'cpp',
                            'cs': 'csharp',
                            'swift': 'swift',
                            'kt': 'kotlin',
                            'scala': 'scala',
                        }
                        language = ext_to_lang.get(ext, 'python')
                
                logger.info(f"Starting code review for PR #{pr_number} (language: {language})")
                
                # Get the actual file content for review
                code_content = ""
                if files and len(files) > 0:
                    # Get content from the first file
                    first_filename = files[0].get('filename', '')
                    if first_filename:
                        code_content = self.github_integration.get_pr_file_content(pr_number, first_filename)
                        if not code_content:
                            logger.warning(f"Could not get content for file {first_filename}, using diff")
                            code_content = diff
                    else:
                        code_content = diff
                else:
                    code_content = diff
                
                review_result = await self.developer_agent.review_code(
                    code=code_content,
                    language=language,
                    task_description=f"Review PR #{pr_number}: {pr_title}"
                )
                
                logger.info(f"Review completed. Success: {review_result.get('success', False)}")
                
                if not review_result.get('success', False):
                    error_msg = f"Code review failed: {review_result.get('message', 'Unknown error')}"
                    logger.error(error_msg)
                    return PRProcessingResult(
                        success=False,
                        message=error_msg,
                        actions_taken=[],
                        pr_number=pr_number
                    )
                
                # 3. Process the review results
                actions = []
                if review_result.get('feedback'):
                    logger.info("Review feedback received")
                    # Don't add comments after review - only after making changes
                    actions.append({
                        'action': 'reviewed',
                        'details': review_result['feedback']
                    })
                
                # 4. Apply suggested changes if any
                if review_result.get('suggested_changes'):
                    logger.info(f"Found {len(review_result['suggested_changes'])} suggested changes")
                    try:
                        logger.info("Applying code changes...")
                        apply_result = await self.developer_agent.apply_code_changes(
                            pr_info=pr_data,
                            changes=review_result['suggested_changes']
                        )
                        
                        logger.info(f"Code changes applied. Success: {apply_result.get('success', False)}")
                        
                        if apply_result.get('success', False):
                            actions.append({
                                'action': 'applied_changes',
                                'details': apply_result.get('message', 'Changes applied'),
                                'pr_url': apply_result.get('pr_url')
                            })
                            logger.info(f"New PR created: {apply_result.get('pr_url')}")
                            
                            # Add comment to original PR after making changes
                            try:
                                comment = f"""
## AI Code Review Completed ✅

I've reviewed your PR and made the following improvements:

**Changes Applied:**
{chr(10).join(f'- {c.get("description", "Code improvement")}' for c in review_result.get('suggested_changes', []))}

**New PR Created:** {apply_result.get('pr_url')}

The improvements have been applied in a separate PR to maintain a clean history.
                                """
                                self.github_integration.add_comment(pr_number, comment)
                                logger.info(f"Added comment to PR #{pr_number}")
                            except Exception as comment_error:
                                logger.warning(f"Failed to add comment to PR #{pr_number}: {comment_error}")
                        else:
                            logger.warning(f"Failed to apply changes: {apply_result.get('message', 'Unknown error')}")
                            
                    except Exception as e:
                        error_msg = f"Error applying code changes: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        actions.append({
                            'action': 'error',
                            'details': error_msg
                        })
                else:
                    logger.info("No suggested changes to apply")
                
                return PRProcessingResult(
                    success=True,
                    message="PR processed successfully",
                    actions_taken=actions,
                    pr_number=pr_number
                )
                
            except Exception as e:
                error_msg = f"Error during PR processing: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return PRProcessingResult(
                    success=False,
                    message=error_msg,
                    actions_taken=[],
                    pr_number=pr_number
                )
                
        except Exception as e:
            error_msg = f"Unexpected error processing PR: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return PRProcessingResult(
                success=False,
                message=error_msg,
                actions_taken=[],
                pr_number=pr_number
            )

    async def process_and_merge_pr(
        self, 
        pr_info, 
        auto_merge: bool = False,
        merge_method: str = "merge"
    ) -> PRProcessingResult:
        """Process a pull request and optionally merge it.
        
        Args:
            pr_info: PR information as either a dict, PRInfo object, or PR number
            auto_merge: Whether to automatically merge if criteria are met
            merge_method: Merge method to use ('merge', 'squash', or 'rebase')
            
        Returns:
            PRProcessingResult: Result of the processing and merge
        """
        # First process the PR normally
        process_result = await self.process_pr(pr_info)
        
        if not process_result.success:
            return process_result
        
        # Extract PR number from the result
        pr_number = process_result.pr_number
        
        # Check if we should attempt to merge
        if not auto_merge:
            return process_result
        
        try:
            logger.info(f"Attempting to merge PR #{pr_number} after processing")
            
            # Check if PR can be merged
            can_merge_result = await self.developer_agent.can_merge_pr(pr_number)
            if not can_merge_result.get('can_merge', False):
                logger.info(f"PR #{pr_number} cannot be merged: {can_merge_result.get('reason', 'Unknown reason')}")
                # Add merge check to actions
                actions = process_result.actions_taken + [{
                    'action': 'merge_check',
                    'details': f"Cannot merge: {can_merge_result.get('reason', 'Unknown reason')}",
                    'mergeable_state': can_merge_result.get('mergeable_state')
                }]
                return PRProcessingResult(
                    success=True,
                    message=f"PR processed successfully but cannot be merged: {can_merge_result.get('reason', 'Unknown reason')}",
                    actions_taken=actions,
                    pr_number=pr_number
                )
            
            # Attempt to merge the PR
            merge_result = await self.developer_agent.merge_pr(
                pr_number=pr_number,
                merge_method=merge_method,
                auto_merge=True
            )
            
            if merge_result.get('success', False):
                logger.info(f"Successfully merged PR #{pr_number}")
                # Add merge action to the result
                actions = process_result.actions_taken + [{
                    'action': 'merged',
                    'details': merge_result.get('message', 'PR merged successfully'),
                    'merge_commit_sha': merge_result.get('merge_commit_sha'),
                    'merge_method': merge_method
                }]
                return PRProcessingResult(
                    success=True,
                    message=f"PR processed and merged successfully",
                    actions_taken=actions,
                    pr_number=pr_number
                )
            else:
                logger.warning(f"Failed to merge PR #{pr_number}: {merge_result.get('error', 'Unknown error')}")
                # Add merge failure to actions
                actions = process_result.actions_taken + [{
                    'action': 'merge_failed',
                    'details': merge_result.get('error', 'Unknown error'),
                    'mergeable_state': merge_result.get('mergeable_state')
                }]
                return PRProcessingResult(
                    success=True,
                    message=f"PR processed successfully but merge failed: {merge_result.get('error', 'Unknown error')}",
                    actions_taken=actions,
                    pr_number=pr_number
                )
                
        except Exception as e:
            error_msg = f"Error during merge attempt for PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Add merge error to actions
            actions = process_result.actions_taken + [{
                'action': 'merge_error',
                'details': error_msg
            }]
            return PRProcessingResult(
                success=True,
                message=f"PR processed successfully but merge failed: {error_msg}",
                actions_taken=actions,
                pr_number=pr_number
            )

    async def review_and_merge_pr(
        self, 
        pr_info, 
        merge_method: str = "merge"
    ) -> PRProcessingResult:
        """Review a PR and merge it if it meets the criteria.
        
        Args:
            pr_info: PR information as either a dict, PRInfo object, or PR number
            merge_method: Merge method to use ('merge', 'squash', or 'rebase')
            
        Returns:
            PRProcessingResult: Result of the review and merge
        """
        # Handle different input types to get PR number
        if isinstance(pr_info, int):
            pr_number = pr_info
        elif hasattr(pr_info, 'number'):
            pr_number = pr_info.number
        else:
            pr_number = pr_info.get('number')
        
        if not pr_number:
            return PRProcessingResult(
                success=False,
                message="Could not determine PR number",
                actions_taken=[],
                pr_number=0
            )
        
        try:
            logger.info(f"Reviewing and potentially merging PR #{pr_number}")
            
            # Use the developer agent's review_and_merge_pr method
            result = await self.developer_agent.review_and_merge_pr(
                pr_number=pr_number,
                auto_merge=True,
                merge_method=merge_method
            )
            
            if result.get('success', False):
                actions = []
                
                # Add review action
                if result.get('reviewed', False):
                    actions.append({
                        'action': 'reviewed',
                        'details': 'PR reviewed successfully'
                    })
                
                # Add merge action if merged
                if result.get('merged', False):
                    merge_result = result.get('merge_result', {})
                    actions.append({
                        'action': 'merged',
                        'details': merge_result.get('message', 'PR merged successfully'),
                        'merge_commit_sha': merge_result.get('merge_commit_sha'),
                        'merge_method': merge_method
                    })
                
                return PRProcessingResult(
                    success=True,
                    message=result.get('message', 'PR reviewed and processed successfully'),
                    actions_taken=actions,
                    pr_number=pr_number
                )
            else:
                return PRProcessingResult(
                    success=False,
                    message=result.get('error', 'Unknown error during review and merge'),
                    actions_taken=[],
                    pr_number=pr_number
                )
                
        except Exception as e:
            error_msg = f"Error in review_and_merge_pr for PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return PRProcessingResult(
                success=False,
                message=error_msg,
                actions_taken=[],
                pr_number=pr_number
            )

    async def review_pr_only(self, pr_info) -> PRProcessingResult:
        """Review a pull request without applying any changes.
        
        Args:
            pr_info: PR information as either a dict, PRInfo object, or PR number
            
        Returns:
            PRProcessingResult: Result of the review
        """
        # Handle different input types
        if isinstance(pr_info, int):  # PR number
            pr_number = pr_info
            # Get the full PR info dict with the structure expected by the developer agent
            pr_data = self.github_integration.get_pr_info_dict(pr_number)
            if not pr_data:
                return PRProcessingResult(
                    success=False,
                    message=f"Could not retrieve PR #{pr_number} information",
                    actions_taken=[],
                    pr_number=pr_number
                )
            pr_title = pr_data.get('title', 'No title')
        elif hasattr(pr_info, 'number'):  # PRInfo object
            pr_number = pr_info.number
            pr_title = pr_info.title
            # Get the full PR info dict with the structure expected by the developer agent
            pr_data = self.github_integration.get_pr_info_dict(pr_number)
            if not pr_data:
                return PRProcessingResult(
                    success=False,
                    message=f"Could not retrieve PR #{pr_number} information",
                    actions_taken=[],
                    pr_number=pr_number
                )
        else:  # dict
            pr_number = pr_info.get('number')
            pr_title = pr_info.get('title', 'No title')
            # If it's already a dict, check if it has the required structure
            if 'base' in pr_info and 'repo' in pr_info.get('base', {}):
                pr_data = pr_info
            else:
                # Get the full PR info dict with the structure expected by the developer agent
                pr_data = self.github_integration.get_pr_info_dict(pr_number)
                if not pr_data:
                    return PRProcessingResult(
                        success=False,
                        message=f"Could not retrieve PR #{pr_number} information",
                        actions_taken=[],
                        pr_number=pr_number
                    )
            
        logger.info(f"Reviewing PR #{pr_number}: {pr_title} (review only mode)")
        
        try:
            # 1. Get PR diff and files
            try:
                diff = self.github_integration.get_pr_diff(pr_number)
                files = self.github_integration.get_pr_files(pr_number)
                
                if not diff and not files:
                    error_msg = "Could not retrieve PR diff or files - empty response"
                    logger.error(error_msg)
                    return PRProcessingResult(
                        success=False,
                        message=error_msg,
                        actions_taken=[],
                        pr_number=pr_number
                    )
                    
            except Exception as e:
                error_msg = f"Error fetching PR details: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return PRProcessingResult(
                    success=False,
                    message=error_msg,
                    actions_taken=[],
                    pr_number=pr_number
                )
            
            # 2. Review PR (review only)
            try:
                # Determine the language from the first modified file
                language = 'python'  # Default to python
                if files and len(files) > 0:
                    # Get the first file and extract its extension
                    first_file = files[0].get('filename', '')
                    if '.' in first_file:
                        ext = first_file.split('.')[-1].lower()
                        # Map common extensions to languages
                        ext_to_lang = {
                            'py': 'python',
                            'js': 'javascript',
                            'ts': 'typescript',
                            'java': 'java',
                            'go': 'go',
                            'rs': 'rust',
                            'rb': 'ruby',
                            'php': 'php',
                            'c': 'c',
                            'cpp': 'cpp',
                            'h': 'c',
                            'hpp': 'cpp',
                            'cs': 'csharp',
                            'swift': 'swift',
                            'kt': 'kotlin',
                            'scala': 'scala',
                        }
                        language = ext_to_lang.get(ext, 'python')
                
                logger.info(f"Starting code review for PR #{pr_number} (language: {language})")
                
                # Get the actual file content for review
                code_content = ""
                if files and len(files) > 0:
                    # Get content from the first file
                    first_filename = files[0].get('filename', '')
                    if first_filename:
                        code_content = self.github_integration.get_pr_file_content(pr_number, first_filename)
                        if not code_content:
                            logger.warning(f"Could not get content for file {first_filename}, using diff")
                            code_content = diff
                    else:
                        code_content = diff
                else:
                    code_content = diff
                
                review_result = await self.developer_agent.review_code(
                    code=code_content,
                    language=language,
                    task_description=f"Review PR #{pr_number}: {pr_title}"
                )
                
                logger.info(f"Review completed. Success: {review_result.get('success', False)}")
                
                if not review_result.get('success', False):
                    error_msg = f"Code review failed: {review_result.get('message', 'Unknown error')}"
                    logger.error(error_msg)
                    return PRProcessingResult(
                        success=False,
                        message=error_msg,
                        actions_taken=[],
                        pr_number=pr_number
                    )
                
                # 3. Process the review results (review only - no changes applied)
                actions = []
                if review_result.get('feedback'):
                    logger.info("Review feedback received")
                    actions.append({
                        'action': 'reviewed',
                        'details': review_result['feedback']
                    })
                
                # 4. Add review comments to the PR
                if review_result.get('feedback'):
                    try:
                        logger.info("Adding review comments to PR...")
                        comment_result = await self.developer_agent.add_pr_comment(
                            pr_number=pr_number,
                            comment=review_result['feedback']
                        )
                        
                        if comment_result.get('success', False):
                            actions.append({
                                'action': 'added_comment',
                                'details': 'Review feedback added to PR'
                            })
                            logger.info("Review comments added successfully")
                        else:
                            logger.warning(f"Failed to add review comments: {comment_result.get('message', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.warning(f"Error adding review comments: {str(e)}")
                
                logger.info(f"Review completed successfully for PR #{pr_number}")
                return PRProcessingResult(
                    success=True,
                    message=f"Successfully reviewed PR #{pr_number}",
                    actions_taken=actions,
                    pr_number=pr_number
                )
                
            except Exception as e:
                error_msg = f"Error during review: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return PRProcessingResult(
                    success=False,
                    message=error_msg,
                    actions_taken=[],
                    pr_number=pr_number
                )
                
        except Exception as e:
            error_msg = f"Error processing PR review: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return PRProcessingResult(
                success=False,
                message=error_msg,
                actions_taken=[],
                pr_number=pr_number
            )

    async def process_prs(self, prs: List[Dict[str, Any]]) -> List[PRProcessingResult]:
        """Process multiple pull requests.
        
        Args:
            prs: List of PR data dictionaries
            
        Returns:
            List of PRProcessingResult objects
        """
        results = []
        for pr in prs:
            result = await self.process_pr(pr)
            results.append(result)
        return results
