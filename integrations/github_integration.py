import logging
from typing import Dict, List, Any, Optional
from github import Github, Repository, PullRequest
from dataclasses import asdict
from config import GitHubConfig

logger = logging.getLogger(__name__)

class GitHubIntegration:
    """Integration with GitHub for repository and PR operations."""

    def __init__(self, github_config: GitHubConfig):
        """Initialize the GitHub integration.
        
        Args:
            github_config: GitHub configuration object containing token, repo_owner, etc.
        """
        self.config = github_config
        self.repo_owner = github_config.repo_owner
        self.repo_name = github_config.repo_name
        
        # Initialize GitHub client with token if provided
        self.github = Github(github_config.token) if github_config.token else Github()
        logger.info(f"Initialized GitHub integration for {self.repo_owner}/{self.repo_name}")

    def get_repository(self) -> Repository.Repository:
        """Get the GitHub repository.
        
        Returns:
            Repository: GitHub repository object
        """
        repo_full_name = f"{self.repo_owner}/{self.repo_name}"
        logger.info(f"Getting repository: {repo_full_name}")
        
        try:
            repo = self.github.get_repo(repo_full_name)
            logger.info(f"Successfully accessed repository: {repo_full_name}")
            return repo
            
        except Exception as e:
            logger.error(f"Error getting repository {repo_full_name}: {str(e)}")
            raise

    def get_pull_request(self, pr_number: int) -> Optional[PullRequest.PullRequest]:
        """Get a pull request by number.
        
        Args:
            pr_number: PR number
            
        Returns:
            PullRequest: Pull request or None if not found
        """
        logger.info(f"Getting pull request: {pr_number}")
        
        try:
            repo = self.get_repository()
            pr = repo.get_pull(pr_number)
            return pr
            
        except Exception as e:
            logger.error(f"Error getting pull request: {str(e)}")
            return None

    def get_pr_info_dict(self, pr_number: int) -> Optional[Dict[str, Any]]:
        """Get pull request information as a dictionary with the structure expected by the developer agent.
        
        Args:
            pr_number: PR number
            
        Returns:
            Dict: PR information in the expected format or None if not found
        """
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                return None
            
            # Convert PyGithub PR object to the expected dictionary format
            pr_info = {
                'number': pr.number,
                'title': pr.title,
                'body': pr.body or '',
                'html_url': pr.html_url,
                'base': {
                    'ref': pr.base.ref,
                    'repo': {
                        'full_name': pr.base.repo.full_name,
                        'name': pr.base.repo.name,
                        'owner': {
                            'login': pr.base.repo.owner.login
                        }
                    }
                },
                'head': {
                    'ref': pr.head.ref,
                    'repo': {
                        'full_name': pr.head.repo.full_name if pr.head.repo else None,
                        'name': pr.head.repo.name if pr.head.repo else None,
                        'owner': {
                            'login': pr.head.repo.owner.login if pr.head.repo else None
                        }
                    }
                },
                'user': {
                    'login': pr.user.login
                },
                'state': pr.state,
                'created_at': pr.created_at.isoformat() if pr.created_at else None,
                'updated_at': pr.updated_at.isoformat() if pr.updated_at else None
            }
            
            return pr_info
            
        except Exception as e:
            logger.error(f"Error getting PR info dict for PR #{pr_number}: {str(e)}")
            return None

    def get_open_pull_requests(self) -> List[PullRequest.PullRequest]:
        """Get all open pull requests.
        
        Returns:
            List[PullRequest]: List of open pull requests
        """
        logger.info("Getting open pull requests")
        
        try:
            repo = self.get_repository()
            prs = repo.get_pulls(state="open")
            return list(prs)
            
        except Exception as e:
            logger.error(f"Error getting open pull requests: {str(e)}")
            return []

    def add_comment(self, pr_number: int, comment: str) -> bool:
        """Add a comment to a pull request.
        
        Args:
            pr_number: PR number
            comment: Comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                logger.error(f"PR #{pr_number} not found")
                return False
                
            pr.create_issue_comment(comment)
            logger.info(f"Added comment to PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding comment to PR #{pr_number}: {str(e)}")
            return False

    def get_pr_diff(self, pr_number: int) -> str:
        """Get the unified diff for a pull request.
        
        Args:
            pr_number: PR number
            
        Returns:
            str: Unified diff text or empty string if not found
        """
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                logger.error(f"PR #{pr_number} not found")
                return ""
            
            # Get the diff URL from the PR object
            diff_url = f"https://patch-diff.githubusercontent.com/raw/{self.repo_owner}/{self.repo_name}/pull/{pr_number}.diff"
            
            # Make a direct HTTP request to get the diff
            import requests
            response = requests.get(diff_url)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error getting diff for PR #{pr_number}: {str(e)}", exc_info=True)
            return ""

    def get_pr_file_content(self, pr_number: int, filename: str) -> str:
        """Get the content of a specific file from a pull request.
        
        Args:
            pr_number: PR number
            filename: Name of the file to get content for
            
        Returns:
            str: File content or empty string if not found
        """
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                logger.error(f"PR #{pr_number} not found")
                return ""
            
            # Get the repository
            repo = self.get_repository()
            
            # Get the head branch (the branch with changes)
            head_branch = pr.head.ref
            head_sha = pr.head.sha
            
            try:
                # Try to get the file content from the head branch
                file_content = repo.get_contents(filename, ref=head_sha)
                if hasattr(file_content, 'decoded_content'):
                    return file_content.decoded_content.decode('utf-8')
                elif hasattr(file_content, 'content'):
                    return file_content.content
                else:
                    logger.error(f"Could not decode content for file {filename}")
                    return ""
                    
            except Exception as file_error:
                logger.warning(f"Could not get content for file {filename} from head branch: {str(file_error)}")
                return ""
                
        except Exception as e:
            logger.error(f"Error getting file content for {filename} in PR #{pr_number}: {str(e)}")
            return ""

    def get_pr_files(self, pr_number: int) -> List[Dict[str, Any]]:
        """Get the list of files changed in a pull request.
        
        Args:
            pr_number: PR number
            
        Returns:
            List[Dict]: List of file change information
        """
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                logger.error(f"PR #{pr_number} not found")
                return []
                
            files = pr.get_files()
            result = []
            
            for f in files:
                try:
                    file_info = {
                        'filename': f.filename,
                        'status': f.status,
                        'additions': f.additions,
                        'deletions': f.deletions,
                        'changes': f.changes,
                        'patch': f.patch if hasattr(f, 'patch') else ''
                    }
                    result.append(file_info)
                except Exception as file_err:
                    logger.warning(f"Could not get full info for file {f.filename}: {str(file_err)}")
                    # Add basic file info even if we can't get all details
                    result.append({
                        'filename': f.filename,
                        'status': 'unknown',
                        'additions': 0,
                        'deletions': 0,
                        'changes': 0,
                        'patch': ''
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting files for PR #{pr_number}: {str(e)}", exc_info=True)
            return []

    async def create_branch(self, repo: str, branch: str, base_branch: str) -> bool:
        """Create a new branch from an existing one.
        
        Args:
            repo: Repository full name (owner/repo)
            branch: Name of the new branch
            base_branch: Name of the base branch
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            github_repo = self.github.get_repo(repo)
            source = github_repo.get_branch(base_branch)
            github_repo.create_git_ref(ref=f'refs/heads/{branch}', sha=source.commit.sha)
            logger.info(f"Created branch {branch} from {base_branch} in {repo}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating branch {branch}: {str(e)}")
            return False

    async def create_pull_request(self, repo: str, title: str, body: str, head: str, base: str) -> Optional[str]:
        """Create a new pull request.
        
        Args:
            repo: Repository full name (owner/repo)
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            
        Returns:
            Optional[str]: PR URL if successful, None otherwise
        """
        try:
            github_repo = self.github.get_repo(repo)
            pr = github_repo.create_pull(title=title, body=body, head=head, base=base)
            
            logger.info(f"Created PR #{pr.number}: {pr.title}")
            return pr.html_url
            
        except Exception as e:
            logger.error(f"Error creating PR: {str(e)}")
            return None

    def commit_to_branch(self, branch_name: str, commit_message: str, files_to_commit: Optional[Dict[str, str]] = None) -> bool:
        logger.info(f"Committing to branch: {branch_name}")
        if not files_to_commit:
            logger.warning("No files provided to commit")
            return True
        try:
            repo = self.get_repository()
            for file_path, content in files_to_commit.items():
                try:
                    file = repo.get_contents(file_path, ref=branch_name)
                    repo.update_file(file_path, commit_message, content, file.sha, branch=branch_name)
                    logger.info(f"Updated file {file_path} in branch {branch_name}")
                except Exception:
                    repo.create_file(file_path, commit_message, content, branch=branch_name)
                    logger.info(f"Created file {file_path} in branch {branch_name}")
            return True
        except Exception as e:
            logger.error(f"Error committing to branch: {str(e)}")
            return False

    def get_pull_requests(self, state: str = "open", limit: int = 5) -> List[PullRequest.PullRequest]:
        logger.info(f"Getting {state} pull requests with limit {limit}")
        try:
            repo = self.get_repository()
            prs = repo.get_pulls(state=state)
            return list(prs)[:limit]
        except Exception as e:
            logger.error(f"Error getting pull requests: {str(e)}")
            return []

    def add_review_comment(self, pr: PullRequest.PullRequest, body: str, commit_id: str, path: str, position: int) -> bool:
        pr_number = getattr(pr, 'number', getattr(pr, 'id', 'Unknown'))
        logger.info(f"Adding review comment to PR: {pr_number}")
        try:
            pr.create_review_comment(body=body, commit_id=commit_id, path=path, position=position)
            return True
        except Exception as e:
            logger.error(f"Error adding review comment: {str(e)}")
            return False

    def submit_review(self, pr: PullRequest.PullRequest, body: str, event: str = "COMMENT") -> bool:
        pr_number = getattr(pr, 'number', getattr(pr, 'id', 'Unknown'))
        logger.info(f"Submitting review for PR: {pr_number}")
        try:
            pr.create_review(body=body, event=event)
            return True
        except Exception as e:
            logger.error(f"Error submitting review: {str(e)}")
            return False

    def get_pr_files(self, pr_number: int) -> List[Dict[str, Any]]:
        logger.info(f"Getting files for PR: {pr_number}")
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                logger.error(f"Pull request {pr_number} not found")
                return []
            head_ref = pr.head.ref if hasattr(pr, 'head') and hasattr(pr.head, 'ref') else 'main'
            files = pr.get_files()
            files_with_content = []
            for file in files:
                try:
                    repo = self.get_repository()
                    content = repo.get_contents(file.filename, ref=head_ref).decoded_content.decode('utf-8')
                    files_with_content.append({
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'changes': file.changes,
                        'content': content
                    })
                except Exception as e:
                    logger.warning(f"Could not get content for file {file.filename}: {str(e)}")
                    files_with_content.append({
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'changes': file.changes,
                        'content': f"Could not retrieve content: {str(e)}"
                    })
            return files_with_content
        except Exception as e:
            logger.error(f"Error getting PR files: {str(e)}")
            return []

    def post_review_comments(self, pr_number: int, review_feedback: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Posting review comments to PR: {pr_number}")
        try:
            pr = self.get_pull_request(pr_number)
            if not pr:
                return {"status": "error", "message": f"Pull request {pr_number} not found"}

            actual_pr_number = pr.number if hasattr(pr, 'number') else getattr(pr, 'id', pr_number)

            overall_assessment = review_feedback.get("overall_assessment", "")
            comments = review_feedback.get("comments", [])
            suggestions = review_feedback.get("suggestions", [])

            review_body = f"## Code Review\n\n{overall_assessment}\n\n"
            if suggestions:
                review_body += "## Suggestions\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    review_body += f"{i}. {suggestion}\n"
                review_body += "\n"

            event = "COMMENT"
            if any(keyword in overall_assessment.lower() for keyword in ["critical", "fail", "reject", "major issue"]):
                event = "REQUEST_CHANGES"

            review_submitted = self.submit_review(pr, review_body, event)
            comments_added = []

            commits = list(pr.get_commits())
            commit_id = commits[-1].sha if commits else None

            for comment in comments:
                if "file_path" in comment and "line" in comment and "body" in comment and commit_id:
                    comment_added = self.add_review_comment(
                        pr=pr,
                        body=comment["body"],
                        commit_id=commit_id,
                        path=comment["file_path"],
                        position=comment["line"]
                    )
                    if comment_added:
                        comments_added.append(comment)

            return {
                "status": "success" if review_submitted else "partial",
                "message": f"Review submitted with {len(comments_added)} comments",
                "review_id": f"review-{actual_pr_number}-{commit_id[-8:]}" if commit_id else f"review-{actual_pr_number}",
                "comments_added": len(comments_added)
            }

        except Exception as e:
            logger.error(f"Error posting review comments: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def update_file(
        self, 
        repo: str, 
        path: str, 
        content: str, 
        message: str, 
        branch: str = None
    ) -> bool:
        """Update a file in the repository.
        
        Args:
            repo: Repository full name (owner/repo)
            path: Path to the file in the repository
            content: New content of the file
            message: Commit message
            branch: Branch to update (default: repository's default branch)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            repo = self.github.get_repo(repo)
            
            # If branch is not provided, use the default branch
            if not branch:
                branch = repo.default_branch
            
            # Try to get the file to update
            try:
                file = repo.get_contents(path, ref=branch)
                # File exists, update it
                repo.update_file(
                    path=path,
                    message=message,
                    content=content,
                    sha=file.sha,
                    branch=branch
                )
                logger.info(f"Updated file {path} in {repo.full_name} on branch {branch}")
                return True
                
            except Exception as e:
                if "Not Found" in str(e):
                    # File doesn't exist, create it
                    repo.create_file(
                        path=path,
                        message=message,
                        content=content,
                        branch=branch
                    )
                    logger.info(f"Created new file {path} in {repo.full_name} on branch {branch}")
                    return True
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Error updating file {path} in {repo.full_name}: {str(e)}")
            return False

    async def merge_pull_request(
        self, 
        pr_number: int, 
        merge_method: str = "merge", 
        commit_title: str = None,
        commit_message: str = None
    ) -> Dict[str, Any]:
        """Merge a pull request.
        
        Args:
            pr_number: PR number to merge
            merge_method: Merge method ('merge', 'squash', or 'rebase')
            commit_title: Custom commit title (for squash and rebase)
            commit_message: Custom commit message (for squash and rebase)
            
        Returns:
            Dict containing merge result with success status and details
        """
        try:
            logger.info(f"Attempting to merge PR #{pr_number} using {merge_method} method")
            
            # Get the pull request
            pr = self.get_pull_request(pr_number)
            if not pr:
                return {
                    'success': False,
                    'error': f'Pull request #{pr_number} not found',
                    'merged': False
                }
            
            # Check if PR is already merged
            if pr.merged:
                return {
                    'success': True,
                    'message': f'PR #{pr_number} is already merged',
                    'merged': True,
                    'merge_commit_sha': pr.merge_commit_sha
                }
            
            # Check if PR is mergeable
            if pr.mergeable is False:
                return {
                    'success': False,
                    'error': f'PR #{pr_number} is not mergeable. State: {pr.mergeable_state}',
                    'merged': False,
                    'mergeable_state': pr.mergeable_state
                }
            
            # Check if PR is in a mergeable state
            if pr.mergeable_state not in ['clean', 'unstable']:
                return {
                    'success': False,
                    'error': f'PR #{pr_number} is not in a mergeable state. Current state: {pr.mergeable_state}',
                    'merged': False,
                    'mergeable_state': pr.mergeable_state
                }
            
            # Prepare merge parameters
            merge_params = {}
            if merge_method in ['squash', 'rebase'] and commit_title:
                merge_params['commit_title'] = commit_title
            if merge_method in ['squash', 'rebase'] and commit_message:
                merge_params['commit_message'] = commit_message
            
            # Attempt to merge
            if merge_method == 'merge':
                result = pr.merge(**merge_params)
            elif merge_method == 'squash':
                result = pr.merge(squash=True, **merge_params)
            elif merge_method == 'rebase':
                result = pr.merge(rebase=True, **merge_params)
            else:
                return {
                    'success': False,
                    'error': f'Invalid merge method: {merge_method}. Must be one of: merge, squash, rebase',
                    'merged': False
                }
            
            # Check if merge was successful
            if result.merged:
                logger.info(f"Successfully merged PR #{pr_number} using {merge_method} method")
                return {
                    'success': True,
                    'message': f'Successfully merged PR #{pr_number} using {merge_method} method',
                    'merged': True,
                    'merge_commit_sha': result.sha,
                    'merge_method': merge_method
                }
            else:
                return {
                    'success': False,
                    'error': f'Merge failed for PR #{pr_number}. Reason: {result.message}',
                    'merged': False,
                    'merge_message': result.message
                }
                
        except Exception as e:
            error_msg = f"Error merging PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'error': error_msg,
                'merged': False
            }

    def can_merge_pr(self, pr_number: int) -> Dict[str, Any]:
        """Check if a pull request can be merged.
        
        Args:
            pr_number: PR number to check
            
        Returns:
            Dict containing mergeability status and details
        """
        try:
            logger.info(f"Checking if PR #{pr_number} can be merged")
            
            # Get the pull request
            pr = self.get_pull_request(pr_number)
            if not pr:
                return {
                    'can_merge': False,
                    'reason': f'Pull request #{pr_number} not found',
                    'mergeable_state': None
                }
            
            # Check if already merged
            if pr.merged:
                return {
                    'can_merge': False,
                    'reason': 'Pull request is already merged',
                    'mergeable_state': 'merged'
                }
            
            # Check if PR is closed
            if pr.state == 'closed':
                return {
                    'can_merge': False,
                    'reason': 'Pull request is closed',
                    'mergeable_state': 'closed'
                }
            
            # Check mergeable state
            if pr.mergeable_state == 'clean':
                return {
                    'can_merge': True,
                    'reason': 'Pull request is ready to merge',
                    'mergeable_state': 'clean'
                }
            elif pr.mergeable_state == 'unstable':
                return {
                    'can_merge': True,
                    'reason': 'Pull request can be merged (unstable state)',
                    'mergeable_state': 'unstable'
                }
            elif pr.mergeable_state == 'dirty':
                return {
                    'can_merge': False,
                    'reason': 'Pull request has conflicts that need to be resolved',
                    'mergeable_state': 'dirty'
                }
            elif pr.mergeable_state == 'blocked':
                return {
                    'can_merge': False,
                    'reason': 'Pull request is blocked (e.g., missing reviews, failing checks)',
                    'mergeable_state': 'blocked'
                }
            else:
                return {
                    'can_merge': False,
                    'reason': f'Pull request is in unknown state: {pr.mergeable_state}',
                    'mergeable_state': pr.mergeable_state
                }
                
        except Exception as e:
            error_msg = f"Error checking mergeability for PR #{pr_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'can_merge': False,
                'reason': error_msg,
                'mergeable_state': None
            }

    def get_issues(self, state: str = "open", limit: int = 10) -> List[Any]:
        """Get issues from the repository.
        
        Args:
            state: Issue state ('open', 'closed', 'all')
            limit: Maximum number of issues to return
            
        Returns:
            List: List of issues
        """
        logger.info(f"Getting {state} issues with limit {limit}")
        try:
            repo = self.get_repository()
            issues = repo.get_issues(state=state)
            return list(issues)[:limit]
        except Exception as e:
            logger.error(f"Error getting issues: {str(e)}")
            return []

    def get_issue(self, issue_number: int) -> Optional[Any]:
        """Get a specific issue by number.
        
        Args:
            issue_number: Issue number
            
        Returns:
            Issue: Issue object or None if not found
        """
        logger.info(f"Getting issue: {issue_number}")
        try:
            repo = self.get_repository()
            issue = repo.get_issue(issue_number)
            return issue
        except Exception as e:
            logger.error(f"Error getting issue {issue_number}: {str(e)}")
            return None

    def get_issue_info_dict(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get issue information as a dictionary.
        
        Args:
            issue_number: Issue number
            
        Returns:
            Dict: Issue information or None if not found
        """
        try:
            issue = self.get_issue(issue_number)
            if not issue:
                return None
            
            issue_info = {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body or '',
                'html_url': issue.html_url,
                'state': issue.state,
                'user': {
                    'login': issue.user.login
                },
                'labels': [label.name for label in issue.labels],
                'created_at': issue.created_at.isoformat() if issue.created_at else None,
                'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
                'closed_at': issue.closed_at.isoformat() if issue.closed_at else None,
                'repository': {
                    'full_name': f"{self.repo_owner}/{self.repo_name}",
                    'name': self.repo_name,
                    'owner': {
                        'login': self.repo_owner
                    }
                }
            }
            
            return issue_info
            
        except Exception as e:
            logger.error(f"Error getting issue info dict for issue #{issue_number}: {str(e)}")
            return None

    def add_issue_comment(self, issue_number: int, comment: str) -> bool:
        """Add a comment to an issue.
        
        Args:
            issue_number: Issue number
            comment: Comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            issue = self.get_issue(issue_number)
            if not issue:
                logger.error(f"Issue #{issue_number} not found")
                return False
                
            issue.create_comment(comment)
            logger.info(f"Added comment to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding comment to issue #{issue_number}: {str(e)}")
            return False
