from typing import List, Dict, Any, Optional
from crewai.tools import BaseTool
from pydantic import Field
from integrations.github_integration import GitHubIntegration

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
        return self.github.get_issue_info_dict(issue_number)

class GithubFileWriterTool(BaseTool):
    name: str = "github_file_writer"
    description: str = "Creates or updates a file on a specific branch in the GitHub repository."
    github: GitHubIntegration = Field(..., exclude=True)

    def _run(self, repo: str, path: str, content: str, message: str, branch: str) -> bool:
        return self.github.update_file(
            repo=repo,
            path=path,
            content=content,
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
