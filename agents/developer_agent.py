import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from integrations.github_integration import GitHubIntegration
from integrations.perplexity_integration import PerplexityIntegration
from agents.notification_manager import NotificationManager
from config import Config
from .tools import (
    GithubPRReaderTool, 
    GithubIssueReaderTool, 
    GithubFileWriterTool, 
    GithubPRCreatorTool, 
    GithubCommentTool
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

class FileImplementation(BaseModel):
    file_path: str = Field(..., description="The path where the file should be created or updated")
    content: str = Field(..., description="The full source code content for the file")

class FeatureImplementation(BaseModel):
    title: str = Field(..., description="Title of the implementation")
    description: str = Field(..., description="Summary of what was implemented")
    files: List[FileImplementation] = Field(..., description="List of files created or updated")
    test_plan: str = Field(..., description="How to verify the implementation")

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
            if hasattr(self.config, 'perplexity') and hasattr(self.config.perplexity, 'api_key'):
                self.llm = PerplexityIntegration(
                    api_key=self.config.perplexity.api_key,
                    model=getattr(self.config.perplexity, 'model', 'sonar-pro')
                )
        
        # Initialize tools
        self.github_tools = {
            "pr_reader": GithubPRReaderTool(github=self.github),
            "issue_reader": GithubIssueReaderTool(github=self.github),
            "file_writer": GithubFileWriterTool(github=self.github),
            "pr_creator": GithubPRCreatorTool(github=self.github),
            "comment_tool": GithubCommentTool(github=self.github)
        }

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
            llm=f"perplexity/{self.llm.model}" if hasattr(self.llm, 'model') else 'perplexity/sonar-pro',
            verbose=True,
            allow_delegation=False
        )
        
        self.coder_agent = Agent(
            role='Senior Software Engineer',
            goal='Implement robust, efficient, and well-tested code features',
            backstory=(
                'You are a brilliant software engineer known for writing elegant and self-documenting code. '
                'You translate high-level requirements into concrete, functional implementations '
                'across various languages and frameworks.'
            ),
            tools=[self.github_tools["file_writer"]],
            llm=f"perplexity/{self.llm.model}" if hasattr(self.llm, 'model') else 'perplexity/sonar-pro',
            verbose=True,
            allow_delegation=False
        )
        
        self.coordinator_agent = Agent(
            role='DevOps Coordinator',
            goal='Manage the software development workflow and repository actions',
            backstory=(
                'You ensure that all code changes are properly integrated, branches are managed correctly, '
                'and communication with stakeholders (via PR comments/descriptions) is clear and professional.'
            ),
            tools=[self.github_tools["pr_creator"], self.github_tools["comment_tool"], self.github_tools["issue_reader"]],
            llm=f"perplexity/{self.llm.model}" if hasattr(self.llm, 'model') else 'perplexity/sonar-pro',
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
    
    async def implement_feature_from_issue(self, issue_info: Dict[str, Any]) -> Dict[str, Any]:
        try:
            issue_number = issue_info.get('number')
            issue_title = issue_info.get('title', 'No title')
            repo_full_name = issue_info.get('repository', {}).get('full_name') or f"{self.github.repo_owner}/{self.github.repo_name}"
            
            logger.info(f"Implementing feature for issue #{issue_number} using CrewAI...")

            # 1. Design Task: Analyze and generate code
            implementation_task = Task(
                description=(
                    f"Analyze issue #{issue_number}: '{issue_title}'. "
                    "Use the issue_reader tool if needed for more context. "
                    "Generate a complete, production-ready implementation. "
                    "Output a list of files with their paths and full content."
                ),
                agent=self.coder_agent,
                expected_output="A structured feature implementation with multiple files.",
                output_pydantic=FeatureImplementation
            )

            head_branch = f"feature/issue-{issue_number}-{int(time.time())}"
            target_branch = self.config.agent.target_branch if self.config and hasattr(self.config, 'agent') else "main"

            devops_task = Task(
                description=(
                    f"Take the implementation generated and apply it to a new branch '{head_branch}'. "
                    "Use the file_writer tool to save each file. "
                    f"Then create a detailed Pull Request back to '{target_branch}'. "
                    "Finally, comment on the original issue with the PR link."
                ),
                agent=self.coordinator_agent,
                context=[implementation_task],
                expected_output=f"Success confirmation that the PR was created and the issue was updated."
            )

            implementation_crew = Crew(
                agents=[self.coder_agent, self.coordinator_agent],
                tasks=[implementation_task, devops_task],
                process=Process.sequential,
                verbose=True
            )

            result = implementation_crew.kickoff()
            
            implementation_data = implementation_task.output.pydantic if hasattr(implementation_task.output, 'pydantic') else None
            
            if implementation_data:
                return {
                    'success': True,
                    'message': f'Successfully implemented feature from issue #{issue_number}',
                    'pr_url': "Check GitHub for the newly created PR",
                    'branch': head_branch,
                    'files_created': [f.file_path for f in implementation_data.files],
                    'issue_number': issue_number
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to get structured implementation output',
                    'pr_url': None
                }

        except Exception as e:
            logger.error(f"Error implementing feature from issue: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error implementing feature: {str(e)}',
                'pr_url': None
            }

    async def add_issue_comment(self, issue_number: int, comment: str) -> bool:
        """Add a comment to an issue. Wrapper for compatibility."""
        return self.github_tools["comment_tool"]._run(number=issue_number, comment=comment, is_issue=True)

    async def add_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a pull request. Wrapper for compatibility."""
        return self.github_tools["comment_tool"]._run(number=pr_number, comment=comment, is_issue=False)