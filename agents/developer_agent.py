import logging
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from integrations.github_integration import GitHubIntegration
from integrations.perplexity_integration import PerplexityIntegration
from agents.notification_manager import NotificationManager
from config import Config
from agents.tools import (
    GithubPRReaderTool,
    GithubIssueReaderTool,
    GithubFileWriterTool,
    GithubPRCreatorTool,
    GithubCommentTool,
    GithubBranchCreatorTool
)

logger = logging.getLogger(__name__)

def format_code(content: str, file_path: str) -> str:
    """Format code content with proper indentation and line breaks."""
    if not content:
        return content
    
    # Handle JavaScript/React files
    if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
        # Basic JavaScript formatting
        content = re.sub(r'}\s*{', '}\n{', content)
        content = re.sub(r'{\s*', '{\n  ', content)
        content = re.sub(r'}\s*', '\n}', content)
        content = re.sub(r';\s*', ';\n', content)
        content = re.sub(r',\s*', ',\n  ', content)
        
        # Fix React component formatting
        content = re.sub(r'return\s*\(', 'return (\n    ', content)
        content = re.sub(r'\)\s*;', '\n  );', content)
        
        # Add proper indentation for JSX
        lines = content.split('\n')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue
                
            # Decrease indent for closing braces
            if stripped.startswith('}') or stripped.startsWith(']') or stripped.startswith(')'):
                indent_level = max(0, indent_level - 1)
            
            # Add current indentation
            formatted_line = '  ' * indent_level + stripped
            formatted_lines.append(formatted_line)
            
            # Increase indent for opening braces
            if stripped.endswith('{') or stripped.endswith('[') or stripped.endswith('('):
                indent_level += 1
        
        return '\n'.join(formatted_lines)
    
    # Handle CSS files
    elif file_path.endswith('.css'):
        content = re.sub(r'{\s*', ' {\n  ', content)
        content = re.sub(r'}\s*', '\n}\n', content)
        content = re.sub(r';\s*', ';\n  ', content)
        return content
    
    # Handle JSON files
    elif file_path.endswith('.json'):
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2)
        except:
            return content
    
    return content

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

class FileImplementation(BaseModel):
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
                    model=getattr(self.config.perplexity, 'model', 'llama-3.1-70b-instruct')
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

        # Create the Perplexity LLM instance once
        perplexity_llm = f"perplexity/{self.llm.model}" if hasattr(self.llm, 'model') else 'perplexity/llama-3.1-70b-instruct'
        
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
            llm=perplexity_llm,
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
            llm=perplexity_llm,
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
            llm=perplexity_llm,
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
            try:
                logger.info(f"Implementing feature for issue #{issue_number} using CrewAI...")
            
                # 1. Design Task: Analyze and generate code
                implementation_task = Task(
                    description=(
                        f"Analyze issue #{issue_number}: '{issue_title}'. "
                        "Generate a working implementation for this issue. "
                        "Focus on creating a minimal, functional solution that solves the core requirement. "
                        "Output the implementation details as plain text, not complex JSON. "
                        "Create simple, working code that can be immediately useful."
                    ),
                    agent=self.coder_agent,
                    expected_output="Working implementation code."
                )

                head_branch = f"feature/issue-{issue_number}-{int(time.time())}"
                target_branch = self.config.agent.target_branch if self.config and hasattr(self.config, 'agent') else "main"
            
                # 2. Implementation Task: Apply code to repository
                devops_task = Task(
                    description=(
                        f"Take the implementation generated and apply it to a NEW branch '{head_branch}'. "
                        f"Use the file_writer tool to save each file to repository '{repo_full_name}'. "
                        f"Then create a NEW Pull Request from '{head_branch}' to '{target_branch}'. "
                        "Finally, comment on the original issue with the NEW PR link. "
                        "IMPORTANT: Always create NEW branches and NEW PRs - do not reference existing ones. "
                        "Generate fresh implementation for this specific issue."
                    ),
                    agent=self.coordinator_agent,
                    context=[implementation_task],
                    expected_output=f"Success confirmation that a NEW PR was created and issue was updated."
                )

                implementation_crew = Crew(
                    agents=[self.coder_agent, self.coordinator_agent],
                    tasks=[implementation_task, devops_task],
                    process=Process.sequential,
                    verbose=True
                )

                # Retry logic for better reliability
                max_retries = 3
                retry_delay = 2  # seconds
            
                for attempt in range(max_retries):
                    try:
                        result = implementation_crew.kickoff()
                    
                        # Check if result indicates success
                        if hasattr(result, 'raw') and result.raw:
                            logger.info(f"Implementation completed successfully on attempt {attempt + 1}")
                            return {
                                'success': True,
                                'result': result,
                                'attempt': attempt + 1
                            }
                    
                    except Exception as e:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"All {max_retries} attempts failed")
                            return {
                                'success': False,
                                'error': str(e),
                                'attempts': attempt + 1
                            }
            
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
                'message': f'Error implementing feature from issue: {str(e)}',
                'pr_url': None
            }