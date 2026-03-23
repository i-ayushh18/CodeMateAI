import json
import re
from typing import List, Dict, Any, Optional
from crewai.tools import BaseTool
from pydantic import Field
from integrations.github_integration import GitHubIntegration

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
            if stripped.startswith('}') or stripped.startswith(']') or stripped.startswith(')'):
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

class GithubPRReaderTool(BaseTool):
    name: str = "github_pr_reader"
    description: str = "Reads pull request information, including the diff and the content of modified files."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, pr_number: int) -> Dict[str, Any]:
        diff = self.github.get_pr_diff(pr_number)
        files = self.github.get_pr_files(pr_number, include_content=True)
        return {
            "diff": diff,
            "files": files
        }

class GithubIssueReaderTool(BaseTool):
    name: str = "github_issue_reader"
    description: str = "Reads issue information, including title and description."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, issue_number: int) -> Dict[str, Any]:
        # Handle both string and integer inputs
        if isinstance(issue_number, str):
            try:
                issue_number = int(issue_number)
            except ValueError:
                return {"error": f"Invalid issue number: {issue_number}"}
    
        return self.github.get_issue_info_dict(issue_number)

class GithubFileWriterTool(BaseTool):
    name: str = "github_file_writer"
    description: str = "Creates or updates a file on a specific branch in the GitHub repository."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, repo: str, path: str, content: str, message: str, branch: str) -> bool:
        # Format the code content before writing
        formatted_content = format_code(content, path)
        return self.github.update_file(
            repo=repo,
            path=path,
            content=formatted_content,
            message=message,
            branch=branch
        )

class GithubPRCreatorTool(BaseTool):
    name: str = "github_pr_creator"
    description: str = "Creates a new pull request from a source branch to a target branch."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, repo: str, title: str, body: str, head: str, base: str) -> Optional[str]:
        return self.github.create_pull_request(
            repo=repo,
            title=title,
            body=body,
            head=head,
            base=base
        )

class GithubCommentTool(BaseTool):
    name: str = "github_comment_tool"
    description: str = "Adds a comment to a pull request or an issue."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, number: int, comment: str, is_issue: bool = False) -> bool:
        if is_issue:
            return self.github.add_issue_comment(number, comment)
        return self.github.add_comment(number, comment)

class GithubBranchCreatorTool(BaseTool):
    name: str = "github_branch_creator"
    description: str = "Creates a new branch in the GitHub repository."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, repo: str, branch: str, source_branch: str = "main") -> bool:
        return self.github.create_branch(branch, source_branch)
