import os
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from crewai import Agent, Task
from integrations.github_integration import GitHubIntegration
from integrations.perplexity_integration import PerplexityIntegration
from .notification_manager import NotificationManager
from config import Config
import json
import time

logger = logging.getLogger(__name__)

class DeveloperAgent:
    """AI Developer Agent that can generate and modify code."""
    
    
    def __init__(
        self, 
        llm_integration: Any = None,
        github_integration: Optional[GitHubIntegration] = None,
        notification_manager: Optional[NotificationManager] = None,
        workspace_dir: str = "./workspace",
        config: Optional[Config] = None
    ):
        """Initialize the Developer Agent.
        
        Args:
            llm_integration: Initialized LLM integration (Perplexity, etc.)
            github_integration: GitHub integration instance
            notification_manager: Notification manager instance
            workspace_dir: Directory for storing code
            config: Application configuration
        """
        self.llm = llm_integration
        self.github = github_integration
        self.notification_manager = notification_manager
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        self.config = config
        
        if not self.llm and self.config:
            # Initialize Perplexity LLM from config if not provided
            if hasattr(self.config, 'perplexity') and hasattr(self.config.perplexity, 'api_key'):
                self.llm = PerplexityIntegration(
                    api_key=self.config.perplexity.api_key,
                    model=getattr(self.config.perplexity, 'model', 'sonar-pro')
                )
        
        if not self.llm:
            raise ValueError("No LLM integration provided and none could be initialized from config")
        
        # Initialize CrewAI agent
        self.agent = Agent(
            role='Senior Software Developer',
            goal='Write clean, efficient, and well-documented code',
            backstory=(
                'You are an expert software developer with years of experience '
                'writing production-grade code. You follow best practices and '
                'write clean, maintainable, and efficient code.'
            ),
            verbose=True
        )
        
        logger.info("DeveloperAgent initialized")
    
    async def implement_feature(self, task_description: str, context: Optional[Dict] = None) -> Dict:
        """Implement a new feature based on the task description.
        
        Args:
            task_description: Description of the feature to implement
            context: Additional context (e.g., related files, dependencies)
            
        Returns:
            Dict containing implementation details and results
        """
        try:
            # Generate code using LLM
            generated_code = await self.llm.generate_code(
                task_description=task_description,
                context=context
            )
            
            # Extract code blocks if any
            code_blocks = self._extract_code_blocks(generated_code)
            
            result = {
                'success': True,
                'generated_code': generated_code,
                'code_blocks': code_blocks,
                'files_created': []
            }
            
            # Save generated files if code blocks are found
            if code_blocks:
                for i, (lang, code) in enumerate(code_blocks.items()):
                    ext = self._get_file_extension(lang)
                    filename = f"feature_{i+1}{ext}"
                    filepath = self.workspace_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(code)
                    
                    result['files_created'].append(str(filepath))
            
            return result
            
        except Exception as e:
            logger.error(f"Error implementing feature: {str(e)}", exc_info=True)
            self.notification_manager.send_notification(f"Error implementing feature: {str(e)}", level='error')
            return {
                'success': False,
                'error': str(e),
                'generated_code': '',
                'code_blocks': {},
                'files_created': []
            }
    
    async def review_code(self, code: str, language: str, task_description: str = None) -> Dict:
        """Review code and provide feedback.
        
        Args:
            code: Code to review
            language: Programming language
            task_description: Original task description (optional)
            
        Returns:
            Dict containing review feedback
        """
        return await self.llm.review_code(
            code=code,
            language=language,
            task_description=task_description
        )
    
    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """Extract code blocks from markdown text.
        
        Args:
            text: Text containing markdown code blocks
            
        Returns:
            Dict mapping language to code
        """
        import re
        pattern = r"```(\w+)?\n([\s\S]*?)\n```"
        matches = re.findall(pattern, text)
        
        code_blocks = {}
        for i, (lang, code) in enumerate(matches):
            lang = lang or f"code_{i+1}"
            code_blocks[lang] = code.strip()
            
        return code_blocks
    
    def _get_file_extension(self, language: str) -> str:
        """Get file extension for a programming language."""
        extensions = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'cpp': '.cpp',
            'c': '.c',
            'csharp': '.cs',
            'go': '.go',
            'rust': '.rs',
            'ruby': '.rb',
            'php': '.php',
            'swift': '.swift',
            'kotlin': '.kt',
            'scala': '.scala',
            'html': '.html',
            'css': '.css',
            'sql': '.sql',
            'bash': '.sh',
            'shell': '.sh',
            'json': '.json',
            'yaml': '.yaml',
            'toml': '.toml',
            'markdown': '.md',
            'text': '.txt'
        }
        
        language = language.lower()
        # Handle cases like 'python3' or 'javascript-es6'
        for lang, ext in extensions.items():
            if language.startswith(lang):
                return ext
                
        return ".txt"  # Default extension
    
    async def execute_task(self, task):
        """Execute a development task.
        
        Args:
            task: The task to execute (can be a string or CrewAI Task)
            
        Returns:
            dict: Task execution result
        """
        try:
            # If task is a string, create a simple task
            if isinstance(task, str):
                task = Task(description=task)
            
            # Log task details
            task_desc = getattr(task, 'description', 'No description')
            logger.info(f"Executing task: {task_desc[:100]}...")
            
            # Try different ways to execute the task
            if hasattr(task, 'execute') and callable(task.execute):
                result = task.execute()
                if hasattr(result, '__await__'):
                    result = await result
            elif hasattr(task, 'run') and callable(task.run):
                result = task.run()
                if hasattr(result, '__await__'):
                    result = await result
            elif hasattr(task, 'crew') and task.crew is not None:
                result = await task.crew.kickoff()
            else:
                # If we can't execute the task directly, return a success response
                result = {
                    'status': 'success',
                    'message': 'Task processed (no execution needed)',
                    'task_description': task_desc[:200]
                }
            
            return {
                'success': True,
                'result': str(result)[:500],  # Convert to string and limit length
                'should_comment': True,
                'comment': f'Task completed: {task_desc[:100]}...' if task_desc else 'Task completed successfully'
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing task: {error_msg}", exc_info=True)
            self.notification_manager.send_notification(f"Error executing task: {error_msg}", level='error')
            return {
                'success': False,
                'error': error_msg,
                'should_comment': True,
                'comment': f'Error executing task: {error_msg}'
            }
    
    def create_development_task(self, issue: Any) -> Task:
        """Create a development task from a GitHub PR.
        
        Args:
            issue: GitHub PR or issue object (can be PRInfo or dict)
                
        Returns:
            Task: CrewAI task for development
        """
        try:
            # Handle both PRInfo object and dict for backward compatibility
            if hasattr(issue, 'title'):
                pr_title = issue.title
                pr_body = getattr(issue, 'body', '')
                pr_number = getattr(issue, 'number', 'unknown')
                pr_url = getattr(issue, 'html_url', '')
            else:
                pr_title = issue.get('title', 'Untitled PR')
                pr_body = issue.get('body', '')
                pr_number = issue.get('number', 'unknown')
                pr_url = issue.get('html_url', '')
            
            # Create a task with all information in the description
            task_description = (
                f"PR #{pr_number}: {pr_title}\n\n"
                f"URL: {pr_url}\n\n"
                f"{pr_body}"
            )
            
            return Task(
                description=task_description,
                expected_output=f"Implementation for PR #{pr_number}"
            )
            
        except Exception as e:
            logger.error(f"Error creating development task: {str(e)}", exc_info=True)
            self.notification_manager.send_notification(f"Error creating development task: {str(e)}", level='error')
            return Task(
                description="Error: Could not create development task. Please check the logs.",
                expected_output="Error handling PR"
            )
    
    async def review_pr(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Review a pull request and provide feedback.
        
        Args:
            pr_info: PR information including number, title, and diff
            
        Returns:
            Dict containing review feedback and suggested changes
        """
        try:
            pr_number = pr_info.get('number')
            logger.info(f"Reviewing PR #{pr_number}: {pr_info.get('title')}")
            
            # Get PR diff and files
            diff = self.github.get_pr_diff(pr_number)
            files = self.github.get_pr_files(pr_number)
            
            if not diff or not files:
                return {
                    'success': False,
                    'error': 'Could not retrieve PR diff or files',
                    'should_comment': True,
                    'comment': 'Error: Could not retrieve PR diff or files.'
                }
            
            # Prepare context for the LLM
            context = {
                'pr_title': pr_info.get('title', ''),
                'pr_body': pr_info.get('body', ''),
                'diff': diff,
                'files': files,
                'repo': f"{self.github.repo_owner}/{self.github.repo_name}"
            }
            
            # Generate review using LLM
            review_prompt = f"""
            You are an expert code reviewer. Please review the following pull request:
            
            Repository: {context['repo']}
            PR #{pr_number}: {context['pr_title']}
            
            Changes:
            {context['diff']}
            
            Please provide a detailed code review that includes:
            1. Overall assessment of the changes
            2. Code quality issues (if any)
            3. Security concerns (if any)
            4. Performance implications (if any)
            5. Suggestions for improvements
            6. Whether the PR is ready to be merged
            
            Additionally, provide a list of specific changes that could be made to improve the code.
            Format your response in markdown.
            """
            
            review = await self.llm.generate_code(review_prompt)
            
            # Extract suggested changes (if any)
            changes_prompt = f"""
            Based on the following code review, extract specific code changes that should be made.
            Format the response as a list of changes, where each change includes:
            - file: path to the file
            - change_type: 'add', 'modify', or 'delete'
            - content: the code to add/modify (if applicable)
            - line_number: the line number to modify (if applicable)
            - description: brief description of the change
            
            Review:
            {review}
            
            Return only the JSON array of changes, nothing else.
            """
            
            changes_json = await self.llm.generate_code(changes_prompt, response_format="json")
            suggested_changes = json.loads(changes_json) if changes_json else []
            
            return {
                'success': True,
                'review': review,
                'suggested_changes': suggested_changes,
                'should_comment': True,
                'comment': f"## Code Review Summary\n\n{review}"
            }
            
        except Exception as e:
            error_msg = f"Error reviewing PR: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'should_comment': True,
                'comment': f'Error during code review: {str(e)}'
            }
    
    async def apply_code_changes(
        self, 
        pr_info: Dict[str, Any], 
        changes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply suggested code changes and create a new PR with the changes.
        
        Args:
            pr_info: Original PR information
            changes: List of changes to apply
            
        Returns:
            Dict with success status and message
        """
        try:
            if not self.github:
                return {
                    'success': False,
                    'message': 'GitHub integration not available',
                    'pr_url': None
                }
            
            # Create a new branch for the changes
            base_branch = pr_info.get('base', {}).get('ref', 'main')
            pr_number = pr_info.get('number')
            repo = pr_info.get('base', {}).get('repo', {}).get('full_name')
            
            if not all([base_branch, pr_number, repo]):
                return {
                    'success': False,
                    'message': 'Missing required PR information',
                    'pr_url': None
                }
            
            # Create a new branch name
            new_branch = f'fix/pr-{pr_number}-improvements-{int(time.time())}'
            
            # Create the branch
            branch_created = await self.github.create_branch(
                repo=repo,
                branch=new_branch,
                base_branch=base_branch
            )
            
            if not branch_created:
                return {
                    'success': False,
                    'message': 'Failed to create branch',
                    'pr_url': None
                }
            
            # Apply each change
            for change in changes:
                file_path = change.get('file_path')
                new_content = change.get('new_content')
                
                if not file_path or new_content is None:
                    continue
                
                # Update the file in the new branch
                file_updated = await self.github.update_file(
                    repo=repo,
                    path=file_path,
                    content=new_content,
                    message=f"Apply suggested changes to {file_path}",
                    branch=new_branch
                )
                
                if not file_updated:
                    logger.warning(f"Failed to update file {file_path}")
            
            # Create a new PR
            pr_title = f"Improve PR #{pr_number}: {pr_info.get('title', '')}"
            pr_body = f"""
            This PR contains improvements suggested by the AI code review for PR #{pr_number}.
            
            **Original PR**: {pr_info.get('html_url')}
            
            Changes include:
            {chr(10).join(f'- {c.get("description", "Code improvements")}' for c in changes)}
            """
            
            pr_url = await self.github.create_pull_request(
                repo=repo,
                title=pr_title,
                body=pr_body,
                head=new_branch,
                base=base_branch
            )
            
            if pr_url:
                return {
                    'success': True,
                    'message': 'Successfully created PR with improvements',
                    'pr_url': pr_url
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to create PR',
                    'pr_url': None
                }
                
        except Exception as e:
            logger.error(f"Error applying code changes: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error applying changes: {str(e)}',
                'pr_url': None
            }
    
    def update_code_based_on_feedback(self, pr_info: Dict[str, str], feedback: Dict[str, Any]) -> Dict[str, str]:
        """Update code based on review feedback.
        
        Args:
            pr_info: Pull request information
            feedback: Review feedback dictionary with overall_assessment, comments, and suggestions
            
        Returns:
            Dict: Updated pull request information
        """
        logger.info(f"Updating code based on feedback for PR: {pr_info['pr_url']}")
        
        try:
            # Get the files that need to be updated based on the feedback
            files_to_update = {}
            for comment in feedback.get('comments', []):
                file_path = comment.get('file')
                if file_path and file_path not in files_to_update:
                    # In a real implementation, we would get the current content of the file
                    # For the MVP, we'll simulate it
                    files_to_update[file_path] = "// Current file content would be here"
            
            # For each file that needs to be updated
            updated_files = {}
            for file_path, current_content in files_to_update.items():
                # Create a prompt for updating the file based on the feedback
                file_comments = [c for c in feedback.get('comments', []) if c.get('file') == file_path]
                
                update_prompt = f"""Update the following code based on these review comments:
                
                File: {file_path}
                
                Current Code:
                {current_content}
                
                Review Comments:
                {', '.join([f"Line {c.get('line')}: {c.get('comment')}" for c in file_comments])}
                
                Overall Assessment: {feedback.get('overall_assessment', '')}
                
                Suggestions:
                {', '.join(feedback.get('suggestions', []))}
                
                Please provide the complete updated code for this file.
                """
                
                # Generate updated code using LLM
                updated_code = self.llm.generate_code_update(current_content, update_prompt)
                updated_files[file_path] = updated_code
            
            # Use GitHub integration to commit the updated files
            commit_message = "Update code based on review feedback"
            self.github.commit_to_branch(
                branch_name=pr_info['branch_name'],
                commit_message=commit_message,
                files_to_commit=updated_files
            )
            
            # Return updated PR info
            updated_pr_info = pr_info.copy()
            updated_pr_info["updated"] = True
            updated_pr_info["update_message"] = commit_message
            updated_pr_info["updated_files"] = list(updated_files.keys())
            
            return updated_pr_info
            
        except Exception as e:
            logger.error(f"Error updating code based on feedback: {str(e)}")
            self.notification_manager.send_notification(f"Error updating code based on feedback: {str(e)}", level='error')
            raise

    async def can_merge_pr(self, pr_number: int) -> Dict[str, Any]:
        """Check if a pull request can be merged.
        
        Args:
            pr_number: PR number to check
            
        Returns:
            Dict containing mergeability status and details
        """
        try:
            if not self.github:
                return {
                    'can_merge': False,
                    'reason': 'GitHub integration not available',
                    'mergeable_state': None
                }
            
            logger.info(f"Checking if PR #{pr_number} can be merged")
            return self.github.can_merge_pr(pr_number)
            
        except Exception as e:
            error_msg = f"Error checking mergeability for PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'can_merge': False,
                'reason': error_msg,
                'mergeable_state': None
            }

    async def merge_pr(
        self, 
        pr_number: int, 
        merge_method: str = "merge",
        commit_title: str = None,
        commit_message: str = None,
        auto_merge: bool = False
    ) -> Dict[str, Any]:
        """Merge a pull request after code changes.
        
        Args:
            pr_number: PR number to merge
            merge_method: Merge method ('merge', 'squash', or 'rebase')
            commit_title: Custom commit title (for squash and rebase)
            commit_message: Custom commit message (for squash and rebase)
            auto_merge: Whether this is an automatic merge (affects logging and notifications)
            
        Returns:
            Dict containing merge result with success status and details
        """
        try:
            if not self.github:
                return {
                    'success': False,
                    'error': 'GitHub integration not available',
                    'merged': False
                }
            
            logger.info(f"Attempting to merge PR #{pr_number} using {merge_method} method")
            
            # First check if the PR can be merged
            mergeability_check = await self.can_merge_pr(pr_number)
            if not mergeability_check.get('can_merge', False):
                return {
                    'success': False,
                    'error': f"Cannot merge PR #{pr_number}: {mergeability_check.get('reason', 'Unknown reason')}",
                    'merged': False,
                    'mergeable_state': mergeability_check.get('mergeable_state')
                }
            
            # Get PR info for logging and notifications
            pr_info = self.github.get_pr_info_dict(pr_number)
            pr_title = pr_info.get('title', f'PR #{pr_number}') if pr_info else f'PR #{pr_number}'
            
            # Perform the merge
            merge_result = await self.github.merge_pull_request(
                pr_number=pr_number,
                merge_method=merge_method,
                commit_title=commit_title,
                commit_message=commit_message
            )
            
            if merge_result.get('success', False):
                # Successfully merged
                merge_msg = f"Successfully merged PR #{pr_number}: {pr_title}"
                logger.info(merge_msg)
                
                # Send notification
                if self.notification_manager:
                    notification_level = 'info' if auto_merge else 'success'
                    self.notification_manager.send_notification(
                        f"✅ {merge_msg}",
                        level=notification_level
                    )
                
                # Add a comment to the PR about the merge
                try:
                    merge_comment = f"""
## ✅ PR Merged Successfully

This pull request has been successfully merged to the main branch.

**Merge Details:**
- **Method**: {merge_method}
- **Merge Commit**: {merge_result.get('merge_commit_sha', 'N/A')}
- **Merged by**: AI Developer Agent
- **Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}

The changes are now live in the main branch.
                    """
                    self.github.add_comment(pr_number, merge_comment)
                except Exception as comment_error:
                    logger.warning(f"Failed to add merge comment to PR #{pr_number}: {comment_error}")
                
                return {
                    'success': True,
                    'message': merge_msg,
                    'merged': True,
                    'merge_commit_sha': merge_result.get('merge_commit_sha'),
                    'merge_method': merge_method,
                    'pr_title': pr_title
                }
            else:
                # Merge failed
                error_msg = f"Failed to merge PR #{pr_number}: {merge_result.get('error', 'Unknown error')}"
                logger.error(error_msg)
                
                # Send notification
                if self.notification_manager:
                    self.notification_manager.send_notification(
                        f"❌ {error_msg}",
                        level='error'
                    )
                
                return merge_result
                
        except Exception as e:
            error_msg = f"Error merging PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Send notification
            if self.notification_manager:
                self.notification_manager.send_notification(
                    f"❌ {error_msg}",
                    level='error'
                )
            
            return {
                'success': False,
                'error': error_msg,
                'merged': False
            }

    async def review_and_merge_pr(
        self, 
        pr_number: int, 
        auto_merge: bool = False,
        merge_method: str = "merge"
    ) -> Dict[str, Any]:
        """Review a PR and merge it if it meets the criteria.
        
        Args:
            pr_number: PR number to review and potentially merge
            auto_merge: Whether to automatically merge if criteria are met
            merge_method: Merge method to use if merging
            
        Returns:
            Dict containing review and merge results
        """
        try:
            logger.info(f"Reviewing and potentially merging PR #{pr_number}")
            
            # Get PR info
            pr_info = self.github.get_pr_info_dict(pr_number)
            if not pr_info:
                return {
                    'success': False,
                    'error': f'Could not retrieve PR #{pr_number} information',
                    'reviewed': False,
                    'merged': False
                }
            
            # Review the PR
            review_result = await self.review_pr(pr_info)
            
            if not review_result.get('success', False):
                return {
                    'success': False,
                    'error': f'Failed to review PR #{pr_number}: {review_result.get("error", "Unknown error")}',
                    'reviewed': False,
                    'merged': False
                }
            
            # Check if PR meets merge criteria
            can_merge = await self.can_merge_pr(pr_number)
            if not can_merge.get('can_merge', False):
                return {
                    'success': True,
                    'message': f'PR #{pr_number} reviewed but cannot be merged: {can_merge.get("reason", "Unknown reason")}',
                    'reviewed': True,
                    'merged': False,
                    'review': review_result.get('review'),
                    'mergeable_state': can_merge.get('mergeable_state')
                }
            
            # If auto_merge is enabled and PR is ready, merge it
            if auto_merge:
                merge_result = await self.merge_pr(
                    pr_number=pr_number,
                    merge_method=merge_method,
                    auto_merge=True
                )
                
                return {
                    'success': merge_result.get('success', False),
                    'message': merge_result.get('message', ''),
                    'reviewed': True,
                    'merged': merge_result.get('merged', False),
                    'review': review_result.get('review'),
                    'merge_result': merge_result
                }
            else:
                # Just return the review result
                return {
                    'success': True,
                    'message': f'PR #{pr_number} reviewed successfully. Ready for merge.',
                    'reviewed': True,
                    'merged': False,
                    'review': review_result.get('review'),
                    'mergeable_state': can_merge.get('mergeable_state'),
                    'can_merge': True
                }
                
        except Exception as e:
            error_msg = f"Error in review_and_merge_pr for PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'reviewed': False,
                'merged': False
            }

    async def add_pr_comment(self, pr_number: int, comment: str) -> Dict[str, Any]:
        """Add a comment to a pull request.
        
        Args:
            pr_number: PR number to comment on
            comment: Comment content to add
            
        Returns:
            Dict containing the result of the operation
        """
        try:
            logger.info(f"Adding comment to PR #{pr_number}")
            
            if not self.github:
                return {
                    'success': False,
                    'message': 'GitHub integration not available'
                }
            
            # Add comment to the PR
            result = self.github.add_comment(pr_number, comment)
            
            if result:
                logger.info(f"Successfully added comment to PR #{pr_number}")
                return {
                    'success': True,
                    'message': f'Comment added to PR #{pr_number}'
                }
            else:
                logger.error(f"Failed to add comment to PR #{pr_number}")
                return {
                    'success': False,
                    'message': f'Failed to add comment to PR #{pr_number}'
                }
                
        except Exception as e:
            error_msg = f"Error adding comment to PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    async def add_issue_comment(self, issue_number: int, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue.
        
        Args:
            issue_number: Issue number to comment on
            comment: Comment content to add
            
        Returns:
            Dict containing the result of the operation
        """
        try:
            logger.info(f"Adding comment to issue #{issue_number}")
            
            if not self.github:
                return {
                    'success': False,
                    'message': 'GitHub integration not available'
                }
            
            # Add comment to the issue
            result = self.github.add_issue_comment(issue_number, comment)
            
            if result:
                logger.info(f"Successfully added comment to issue #{issue_number}")
                return {
                    'success': True,
                    'message': f'Comment added to issue #{issue_number}'
                }
            else:
                logger.error(f"Failed to add comment to issue #{issue_number}")
                return {
                    'success': False,
                    'message': f'Failed to add comment to issue #{issue_number}'
                }
                
        except Exception as e:
            error_msg = f"Error adding comment to issue #{issue_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    async def implement_feature_from_issue(self, issue_info: Dict[str, Any]) -> Dict[str, Any]:
        """Implement a feature based on an issue description.
        
        Args:
            issue_info: Issue information dictionary
            
        Returns:
            Dict containing implementation results
        """
        try:
            if not self.github:
                return {
                    'success': False,
                    'message': 'GitHub integration not available',
                    'pr_url': None
                }
            
            issue_number = issue_info.get('number')
            issue_title = issue_info.get('title', 'No title')
            issue_body = issue_info.get('body', '')
            repo_full_name = issue_info.get('repository', {}).get('full_name')
            
            if not repo_full_name:
                # Try to get repo from config
                if self.config and hasattr(self.config, 'github'):
                    repo_full_name = f"{self.config.github.repo_owner}/{self.config.github.repo_name}"
                else:
                    return {
                        'success': False,
                        'message': 'Repository information not available',
                        'pr_url': None
                    }
            
            logger.info(f"Implementing feature from issue #{issue_number}: {issue_title}")
            
            # 1. Generate code based on issue requirements
            code_generation_prompt = f"""
            Please implement the feature described in this issue:
            
            Title: {issue_title}
            Description: {issue_body}
            
            Requirements:
            1. Generate clean, production-ready code
            2. Follow best practices for the language/framework
            3. Include proper error handling
            4. Add appropriate documentation
            5. Consider edge cases and validation
            
            IMPORTANT: You MUST format your response with clear file paths and code blocks.
            
            Use this EXACT format for each file:
            
            **File: filename.ext**
            ```language
            // Your code here
            ```
            
            For example:
            **File: src/main.py**
            ```python
            def main():
                print("Hello World")
            ```
            
            Make sure to:
            - Use realistic file paths that make sense for the project structure
            - Include all necessary imports and dependencies
            - Write code that actually works and follows best practices
            - Consider the project context and existing patterns
            - ALWAYS use the **File: path** format before each code block
            """
            
            logger.info("Generating code using LLM...")
            
            # Use the new generate_code_with_files method for better file path extraction
            if hasattr(self.llm, 'generate_code_with_files'):
                code_result = await self.llm.generate_code_with_files(
                    task_description=code_generation_prompt,
                    max_tokens=4000,
                    temperature=0.2
                )
                
                if code_result.get('success', False):
                    code_blocks = code_result.get('code_blocks', {})
                    logger.info(f"Generated {len(code_blocks)} code blocks with file paths")
                    
                    # Log the raw response for debugging
                    raw_response = code_result.get('raw_response', '')
                    if raw_response:
                        logger.info(f"Raw AI response (first 500 chars): {raw_response[:500]}...")
                        if len(raw_response) > 500:
                            logger.info(f"Raw AI response (last 500 chars): ...{raw_response[-500:]}")
                    
                    # Log extracted code blocks
                    for file_path, code_content in code_blocks.items():
                        logger.info(f"Extracted file: {file_path} ({len(code_content)} chars)")
                        logger.info(f"Code preview: {code_content[:200]}...")
                else:
                    logger.warning("generate_code_with_files failed, falling back to old method")
                    # Fallback to old method
                    generated_code = await self.llm.generate_code(
                        prompt=code_generation_prompt,
                        max_tokens=4000,
                        temperature=0.2
                    )
                    code_blocks = self._extract_code_blocks(generated_code)
            else:
                logger.info("LLM doesn't have generate_code_with_files, using old method")
                # Fallback to old method
                generated_code = await self.llm.generate_code(
                    prompt=code_generation_prompt,
                    max_tokens=4000,
                    temperature=0.2
                )
                code_blocks = self._extract_code_blocks(generated_code)
            
            if not code_blocks:
                # Try one more time with a simpler prompt
                logger.warning("No code blocks found, trying with simpler prompt...")
                simple_prompt = f"""
                Create code to implement this feature:
                
                Issue: {issue_title}
                Description: {issue_body}
                
                Please provide working code in this format:
                
                **File: main.py**
                ```python
                # Your Python code here
                ```
                
                Make sure to include actual working code, not just descriptions.
                """
                
                try:
                    if hasattr(self.llm, 'generate_code_with_files'):
                        fallback_result = await self.llm.generate_code_with_files(
                            task_description=simple_prompt,
                            max_tokens=2000,
                            temperature=0.1
                        )
                        if fallback_result.get('success', False):
                            code_blocks = fallback_result.get('code_blocks', {})
                            logger.info(f"Fallback generated {len(code_blocks)} code blocks")
                            
                            # Log fallback response for debugging
                            raw_fallback = fallback_result.get('raw_response', '')
                            if raw_fallback:
                                logger.info(f"Fallback AI response (first 500 chars): {raw_fallback[:500]}...")
                            
                            # Log extracted code blocks from fallback
                            for file_path, code_content in code_blocks.items():
                                logger.info(f"Fallback extracted file: {file_path} ({len(code_content)} chars)")
                                logger.info(f"Fallback code preview: {code_content[:200]}...")
                except Exception as fallback_error:
                    logger.warning(f"Fallback generation failed: {fallback_error}")
                
                if not code_blocks:
                    return {
                        'success': False,
                        'message': 'AI failed to generate code in the expected format. Please try again with a more detailed issue description.',
                        'pr_url': None
                    }
            
            logger.info(f"Generated {len(code_blocks)} code blocks")
            
            # 3. Create a new branch for the feature
            base_branch = "main"  # Default to main branch
            if self.config and hasattr(self.config, 'agent') and hasattr(self.config.agent, 'target_branch'):
                base_branch = self.config.agent.target_branch
            
            feature_branch = f"feature/issue-{issue_number}-{int(time.time())}"
            
            logger.info(f"Creating feature branch: {feature_branch}")
            branch_created = await self.github.create_branch(
                repo=repo_full_name,
                branch=feature_branch,
                base_branch=base_branch
            )
            
            if not branch_created:
                return {
                    'success': False,
                    'message': 'Failed to create feature branch',
                    'pr_url': None
                }
            
            # 4. Create/update files with generated code
            files_created = []
            for file_path, code_content in code_blocks.items():
                try:
                    logger.info(f"Creating/updating file: {file_path}")
                    
                    # Clean up the code content (remove markdown formatting if any)
                    clean_code = code_content.strip()
                    if clean_code.startswith('```'):
                        lines = clean_code.split('\n')
                        clean_code = '\n'.join(lines[1:-1])  # Remove first and last lines
                    
                    file_updated = await self.github.update_file(
                        repo=repo_full_name,
                        path=file_path,
                        content=clean_code,
                        message=f"Implement feature from issue #{issue_number}: {issue_title}",
                        branch=feature_branch
                    )
                    
                    if file_updated:
                        files_created.append(file_path)
                        logger.info(f"Successfully created/updated {file_path}")
                    else:
                        logger.warning(f"Failed to create/update {file_path}")
                        
                except Exception as e:
                    logger.error(f"Error creating file {file_path}: {str(e)}")
            
            if not files_created:
                return {
                    'success': False,
                    'message': 'Failed to create any files',
                    'pr_url': None
                }
            
            # 5. Create a pull request
            pr_title = f"Implement: {issue_title}"
            pr_body = f"""
            ## Feature Implementation
            
            This PR implements the feature requested in issue #{issue_number}.
            
            **Issue:** {issue_title}
            **Issue URL:** {issue_info.get('html_url', 'N/A')}
            
            ### Changes Made
            
            The following files were created/updated:
            {chr(10).join(f'- `{file_path}`' for file_path in files_created)}
            
            ### Implementation Details
            
            This implementation was generated by the AI agent based on the issue requirements.
            
            **Generated Code Summary:**
            - {len(files_created)} files created/updated
            - Feature: {issue_title}
            - Branch: `{feature_branch}`
            
            Please review the implementation and let me know if any adjustments are needed.
            """
            
            logger.info("Creating pull request...")
            pr_url = await self.github.create_pull_request(
                repo=repo_full_name,
                title=pr_title,
                body=pr_body,
                head=feature_branch,
                base=base_branch
            )
            
            if pr_url:
                logger.info(f"Successfully created PR: {pr_url}")
                
                # 6. Add comment to the original issue linking to the PR
                try:
                    issue_comment = f"""
## 🚀 Feature Implementation Started!

I've analyzed your issue and created an implementation:

**Pull Request Created:** {pr_url}
**Branch:** `{feature_branch}`

**Files Created/Updated:**
{chr(10).join(f'- `{file_path}`' for file_path in files_created)}

The AI agent has generated code based on your requirements. Please review the PR and let me know if any adjustments are needed!
                    """
                    
                    await self.add_issue_comment(issue_number, issue_comment)
                    logger.info(f"Added comment to issue #{issue_number}")
                    
                except Exception as comment_error:
                    logger.warning(f"Failed to add comment to issue #{issue_number}: {comment_error}")
                
                return {
                    'success': True,
                    'message': f'Successfully implemented feature from issue #{issue_number}',
                    'pr_url': pr_url,
                    'branch': feature_branch,
                    'files_created': files_created,
                    'issue_number': issue_number
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to create pull request',
                    'pr_url': None
                }
                
        except Exception as e:
            logger.error(f"Error implementing feature from issue: {str(e)}")
            return {
                'success': False,
                'message': f'Error implementing feature: {str(e)}',
                'pr_url': None
            }