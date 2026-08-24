import logging
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from integrations.github_integration import GitHubIntegration
from integrations.openrouter_integration import OpenRouterIntegration
from agents.notification_manager import NotificationManager
from config import Config
from agents.tools import (
    GithubPRReaderTool,
    GithubIssueReaderTool,
    GithubFileWriterTool,
    GithubPRCreatorTool,
    GithubCommentTool,
    GithubBranchCreatorTool,
    format_code
)

logger = logging.getLogger(__name__)


class SuggestedChange(BaseModel):
    file_path: str = Field(..., description="Path to the file to be changed")
    description: str = Field(..., description="Description of why this change is needed")
    new_content: str = Field(..., description="The complete new content for the file")
    change_type: str = Field(..., description="Type of change: 'modify', 'add', or 'delete'")

class CodeReviewOutput(BaseModel):
    overall_assessment: str = Field(..., description="Overall summary of the PR quality")
    is_mergeable: bool = Field(..., description="Whether the PR is ready to merge from a quality perspective")
    quality_issues: List[str] = Field(default_factory=list, description="List of code quality concerns")
    security_concerns: List[str] = Field(default_factory=list, description="List of security vulnerabilities or risks")
    performance_issues: List[str] = Field(default_factory=list, description="List of performance bottlenecks")
    suggested_changes: List[SuggestedChange] = Field(default_factory=list, description="Specific actionable code improvements")
    
    class Config:
        extra = "ignore"  # Allow extra fields in JSON

class FileImplementation(BaseModel):
    file_path: str = Field(..., description="The path where the file should be created or updated")
    content: str = Field(..., description="The full source code content for the file")
    
    class Config:
        extra = "ignore"  # Allow extra fields in JSON

def sanitize_output(output: str) -> str:
    """Sanitize LLM output to remove control characters that break JSON parsing."""
    import re
    # Remove control characters that break JSON
    output = re.sub(r'[\u0000-\u001F]', '', output)
    # Normalize quotes and escape characters
    output = output.replace('\\"', '"')
    output = output.replace('\\n', '\\n')
    output = output.replace('\\t', '\\t')
    output = output.replace('\\r', '\\r')
    return output

class ImplementationPlan(BaseModel):
    title: str = Field(..., description="Title of the implementation")
    description: str = Field(..., description="Summary of what was implemented")
    files: List[FileImplementation] = Field(..., description="List of files created or updated")
    test_plan: str = Field(..., description="How to verify the implementation")
    
    class Config:
        extra = "ignore"  # Allow extra fields in JSON

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
            llm_integration: Initialized LLM integration (OpenRouter, etc.)
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
            if hasattr(self.config, 'openrouter') and hasattr(self.config.openrouter, 'api_key'):
                self.llm = OpenRouterIntegration(
                    api_key=self.config.openrouter.api_key,
                    model=getattr(self.config.openrouter, 'model', 'meta-llama/llama-3.1-70b-instruct')
                )
        
        # Initialize tools
        self.github_tools = {
            "pr_reader": GithubPRReaderTool(github=self.github),
            "issue_reader": GithubIssueReaderTool(github=self.github),
            "file_writer": GithubFileWriterTool(github=self.github),
            "pr_creator": GithubPRCreatorTool(github=self.github),
            "comment_tool": GithubCommentTool(github=self.github),
            "branch_creator": GithubBranchCreatorTool(github=self.github)
        }

        # Create the OpenRouter LLM instance once
        openrouter_llm = f"openrouter/{self.llm.model}" if hasattr(self.llm, 'model') else 'openrouter/meta-llama/llama-3.1-70b-instruct'
        
        # Initialize specialized agents for the new orchestration
        self.reviewer_agent = Agent(
            role='Expert Code Reviewer',
            goal='Ensure code quality, security, and maintainability in pull requests',
            backstory=(
                'You are a veteran software architect with an eagle eye for bugs, security holes, '
                'and performance bottlenecks. You provide constructive, highly technical feedback '
                'and focus on production-readiness.'
            ),
            tools=[self.github_tools["pr_reader"]],
            llm=openrouter_llm,
            verbose=True,
            allow_delegation=False
        )
     
        self.coder_agent = Agent(
            role='Senior Software Engineer',
            goal='Implement robust, efficient, and well-tested code features',
            backstory=(
                'You are a brilliant software engineer known for writing elegant and self-documenting code. '
                'You translate high-level requirements into concrete, functional implementations '
                'without using any tools - just output the implementation directly.'
            ),
            tools=[],  # No tools - just generate code
            llm=openrouter_llm,
            verbose=True,
            allow_delegation=False
        )
        
        self.coordinator_agent = Agent(
            role='DevOps Coordinator',
            goal='Manage the software development workflow and repository actions',
            backstory=(
                'You ensure that all code changes are properly integrated, branches are managed correctly, '
                'and communication with stakeholders (via PR comments/descriptions) is clear and professional. '
                'You ALWAYS create NEW branches and NEW PRs - never reference existing ones.'
            ),
            tools=[
                self.github_tools["pr_creator"],
                self.github_tools["comment_tool"], 
                self.github_tools["branch_creator"],
                self.github_tools["file_writer"]  # Add file writer for coordinator
            ],
            llm=openrouter_llm,
            verbose=True,
            allow_delegation=False
        )
        
        logger.info("DeveloperAgent initialized with CrewAI components and GitHub Tools")
    
    async def review_pr(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        try:
            pr_number = pr_info.get('number')
            logger.info(f"Reviewing PR #{pr_number} using CrewAI...")

            # Define the review task with structured output
            review_task = Task(
                description=(
                    f"Review Pull Request #{pr_number}. "
                    "Use the pr_reader tool to get the diff and file contents. "
                    "Analyze the code for quality, security, and performance. "
                    "Provide a detailed assessment and specific suggested changes."
                ),
                agent=self.reviewer_agent,
                expected_output="A structured code review with specific suggested changes.",
                output_pydantic=CodeReviewOutput
            )

            review_crew = Crew(
                agents=[self.reviewer_agent],
                tasks=[review_task],
                verbose=True
            )

            # Run in thread pool to avoid async issues
            import asyncio
            import concurrent.futures
            if asyncio.get_event_loop().is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(review_crew.kickoff)
                    result = future.result(timeout=300)
            else:
                result = review_crew.kickoff()
        
            feedback_data = result.pydantic if hasattr(result, 'pydantic') else result
            
            if isinstance(feedback_data, CodeReviewOutput):
                review_dict = feedback_data.model_dump()
                return {
                    'success': True,
                    'review': review_dict['overall_assessment'],
                    'suggested_changes': review_dict['suggested_changes'],
                    'should_comment': True,
                    'comment': f"## AI Code Review\n\n{review_dict['overall_assessment']}"
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to get structured review output',
                    'should_comment': True,
                    'comment': 'Error: Failed to generate structured code review.'
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
    
    async def review_code(self, code: str, language: str = '', task_description: str = '') -> Dict[str, Any]:
        """Review a piece of code (used for issue review mode).
        
        Args:
            code: The code or text to review
            language: Programming language of the code
            task_description: Description of what this review is about
            
        Returns:
            Dict with review results
        """
        try:
            logger.info(f"Reviewing code: {task_description}")
            
            review_task = Task(
                description=(
                    f"Review the following content and provide feedback.\n"
                    f"Task: {task_description}\n"
                    f"Language: {language}\n"
                    f"Content:\n{code}\n\n"
                    "Provide a detailed assessment covering quality, potential issues, "
                    "and suggestions for improvement."
                ),
                agent=self.reviewer_agent,
                expected_output="A structured code review with feedback and suggestions."
            )
            
            review_crew = Crew(
                agents=[self.reviewer_agent],
                tasks=[review_task],
                verbose=True
            )
            
            # Run in thread pool to avoid async issues
            import asyncio
            import concurrent.futures
            if asyncio.get_event_loop().is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(review_crew.kickoff)
                    result = future.result(timeout=300)
            else:
                result = review_crew.kickoff()
            
            feedback = result.raw if hasattr(result, 'raw') else str(result)
            
            return {
                'success': True,
                'feedback': feedback,
                'message': 'Review completed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error reviewing code: {str(e)}", exc_info=True)
            return {
                'success': False,
                'feedback': None,
                'message': f'Error reviewing code: {str(e)}'
            }
    
    async def implement_feature_from_issue(self, issue_info: Dict[str, Any]) -> Dict[str, Any]:
        try:
            issue_number = issue_info.get('number')
            issue_title = issue_info.get('title', 'No title')
            issue_body = issue_info.get('body', '')
            repo_full_name = issue_info.get('repository', {}).get('full_name')
            if not repo_full_name:
                if self.github is None:
                    raise ValueError(
                        "Cannot determine repository name: GitHub integration is not initialized "
                        "and issue payload does not contain repository info."
                    )
                repo_full_name = f"{self.github.repo_owner}/{self.github.repo_name}"
            
            logger.info(f"Implementing feature for issue #{issue_number} using AI + Direct GitHub API...")
            
            # Step 1: Use AI to generate code implementation
            prompt = f"""You are a senior software engineer. Generate a complete implementation for this GitHub issue.

Issue #{issue_number}: {issue_title}
Description: {issue_body}

Generate a JSON response with this structure:
{{
    "files": [
        {{
            "path": "relative/path/to/file.js",
            "content": "complete file content here"
        }}
    ],
    "pr_title": "Brief PR title",
    "pr_body": "Detailed description of changes"
}}

Generate WORKING, COMPLETE code. Include all necessary files."""

            logger.info("Generating code implementation with AI...")
            ai_response = await self.llm.generate_text(prompt, max_tokens=3000, temperature=0.7)
            
            # Extract JSON from response - handle markdown code blocks
            import json
            import re
            
            # Try to find JSON in code blocks first
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', ai_response)
            if not json_match:
                # Try to find raw JSON
                json_match = re.search(r'(\{[\s\S]*?"files"[\s\S]*?\})', ai_response)
            
            if not json_match:
                logger.error(f"AI response: {ai_response}")
                raise Exception("AI did not generate valid JSON response")
            
            json_str = json_match.group(1) if json_match.lastindex else json_match.group(0)
            
            try:
                implementation = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"JSON string: {json_str}")
                raise Exception(f"Failed to parse AI JSON response: {e}")
            files = implementation.get('files', [])
            pr_title = implementation.get('pr_title', f'Implement: {issue_title}')
            pr_body = implementation.get('pr_body', f'Implementation for issue #{issue_number}')
            
            if not files:
                raise Exception("No files generated by AI")
            
            logger.info(f"AI generated {len(files)} files")
            
            # Step 2: Create branch directly via GitHub API
            head_branch = f"feature/issue-{issue_number}-{int(time.time())}"
            target_branch = self.config.agent.target_branch if self.config and hasattr(self.config, 'agent') else "main"
            
            logger.info(f"Creating branch: {head_branch}")
            branch_created = self.github.create_branch(
                repo=repo_full_name,
                branch=head_branch,
                base_branch=target_branch
            )
            
            if not branch_created:
                raise Exception(f"Failed to create branch {head_branch}")
            
            # Step 3: Write files directly via GitHub API
            files_created = []
            for file_info in files:
                file_path = file_info.get('path')
                file_content = file_info.get('content')
                
                if not file_path or not file_content:
                    logger.warning(f"Skipping invalid file: {file_info}")
                    continue
                
                logger.info(f"Writing file: {file_path}")
                file_written = self.github.update_file(
                    repo=repo_full_name,
                    path=file_path,
                    content=file_content,
                    message=f"Add {file_path} for issue #{issue_number}",
                    branch=head_branch
                )
                
                if file_written:
                    files_created.append(file_path)
                    logger.info(f"Successfully wrote: {file_path}")
                else:
                    logger.error(f"Failed to write: {file_path}")
            
            if not files_created:
                raise Exception("No files were successfully created")
            
            # Step 4: Create PR directly via GitHub API
            logger.info(f"Creating PR from {head_branch} to {target_branch}")
            pr_url = self.github.create_pull_request(
                repo=repo_full_name,
                title=pr_title,
                body=f"{pr_body}\n\nCloses #{issue_number}\n\nFiles created:\n" + "\n".join([f"- {f}" for f in files_created]),
                head=head_branch,
                base=target_branch
            )
            
            if not pr_url:
                raise Exception("Failed to create pull request")
            
            logger.info(f"PR created successfully: {pr_url}")
            
            # Step 5: Comment on issue directly via GitHub API
            comment_text = f"✅ Implementation complete!\n\nPull Request: {pr_url}\n\nFiles created:\n" + "\n".join([f"- `{f}`" for f in files_created])
            comment_added = self.github.add_issue_comment(issue_number, comment_text)
            
            if comment_added:
                logger.info(f"Comment added to issue #{issue_number}")
            
            return {
                'success': True,
                'message': f'Successfully implemented feature from issue #{issue_number}',
                'pr_url': pr_url,
                'branch': head_branch,
                'files_created': files_created,
                'issue_number': issue_number
            }

        except Exception as e:
            logger.error(f"Error implementing feature from issue: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error implementing feature from issue: {str(e)}',
                'pr_url': None
            }