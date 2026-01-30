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
                    message=f"Review failed: {review_result.get('error', 'Unknown error')}",
                    actions_taken=[],
                    pr_number=pr_number
                )
            
            actions = [{
                'action': 'reviewed',
                'details': review_result.get('review', 'Review completed')
            }]
            
            
            return PRProcessingResult(
                success=True,
                message="PR reviewed successfully using CrewAI",
                actions_taken=actions,
                pr_number=pr_number
            )
            
        except Exception as e:
            logger.error(f"Error processing PR #{pr_number}: {str(e)}", exc_info=True)
            return PRProcessingResult(
                success=False,
                message=str(e),
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
        if isinstance(pr_info, int):  # PR number
            pr_number = pr_info
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
            if 'base' in pr_info and 'repo' in pr_info.get('base', {}):
                pr_data = pr_info
            else:
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
            try:
                diff = self.github_integration.get_pr_diff(pr_number)
                files = self.github_integration.get_pr_files(pr_number, include_content=True)
                
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
            
            try:
                language = 'python'  
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
                    # Get content from the first file (now included in files data)
                    first_file = files[0]
                    if first_file.get('content'):
                        code_content = first_file['content']
                    else:
                        logger.warning(f"No content available for file {first_file.get('filename', '')}, using diff")
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
                
                actions = []
                if review_result.get('feedback'):
                    logger.info("Review feedback received")
                    actions.append({
                        'action': 'reviewed',
                        'details': review_result['feedback']
                    })
                
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

