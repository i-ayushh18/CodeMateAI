#!/usr/bin/env python3
"""
PR Fetcher Service

This module handles fetching and processing pull requests from GitHub.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from integrations.github_integration import GitHubIntegration
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class PRInfo:
    """Data class to store PR information."""
    number: int
    title: str
    body: str
    html_url: str
    created_at: datetime
    updated_at: datetime
    user_login: str
    state: str
    labels: List[str]
    draft: bool
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    review_comments: int = 0
    comments: int = 0


class PRFetcher:
    """Service for fetching and processing pull requests from GitHub."""
    
    def __init__(self, github_integration: GitHubIntegration, config: Config):
        """Initialize the PR fetcher.
        
        Args:
            github_integration: GitHub integration instance
            config: Application configuration
        """
        self.github = github_integration
        self.config = config
        self.processed_prs = self._load_processed_prs()
    
    def _load_processed_prs(self) -> set:
        """Load the set of already processed PRs.
        
        Returns:
            set: Set of processed PR numbers
        """
        # In a real implementation, this would load from a persistent storage
        # For now, we'll just return an empty set
        return set()
    
    def _pr_needs_processing(self, pr_info: PRInfo) -> bool:
        """Determine if a PR needs processing.
        
        Args:
            pr_info: PR information
            
        Returns:
            bool: True if the PR needs processing, False otherwise
        """
        # Skip draft PRs
        if pr_info.draft:
            logger.debug(f"Skipping draft PR #{pr_info.number}: {pr_info.title}")
            return False
            
        # Skip already processed PRs unless they've been updated
        if pr_info.number in self.processed_prs:
            # In a real implementation, we'd check the last processed timestamp
            # For now, we'll just skip already seen PRs
            logger.debug(f"Skipping already processed PR #{pr_info.number}")
            return False
            
        # Add any additional filtering logic here
        return True
    
    async def fetch_open_prs(self, limit: int = 10) -> List[PRInfo]:
        """Fetch open pull requests that need processing.
        
        Args:
            limit: Maximum number of PRs to return
            
        Returns:
            List[PRInfo]: List of PR information
        """
        logger.info(f"Fetching up to {limit} open pull requests")
        prs = self.github.get_pull_requests(state="open", limit=limit)
        
        # Filter out already processed PRs and drafts if needed
        to_process = []
        for pr in prs:
            include_drafts = getattr(self.config.github, 'include_drafts', False)
            if pr.number not in self.processed_prs and (include_drafts or not pr.draft):
                pr_info = PRInfo(
                    number=pr.number,
                    title=pr.title,
                    body=pr.body or "",
                    html_url=pr.html_url,
                    created_at=pr.created_at,
                    updated_at=pr.updated_at,
                    user_login=pr.user.login,
                    state=pr.state,
                    labels=[label.name for label in pr.labels],
                    draft=pr.draft,
                    mergeable=pr.mergeable,
                    mergeable_state=pr.mergeable_state,
                    review_comments=pr.review_comments,
                    comments=pr.comments
                )
                to_process.append(pr_info)
        
        logger.info(f"Found {len(to_process)} PRs that need processing")
        return to_process
    
    def _create_pr_info(self, pr) -> PRInfo:
        """Create a PRInfo object from a GitHub PR object.
        
        Args:
            pr: GitHub PR object
            
        Returns:
            PRInfo: PR information
        """
        return PRInfo(
            number=pr.number,
            title=pr.title,
            body=pr.body or "",
            html_url=pr.html_url,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            user_login=pr.user.login if pr.user else "unknown",
            state=pr.state,
            labels=[label.name for label in pr.labels],
            draft=pr.draft,
            mergeable=pr.mergeable,
            mergeable_state=pr.mergeable_state,
            review_comments=pr.review_comments,
            comments=pr.comments
        )
    
    async def mark_as_processed(self, pr_number: int):
        """Mark a PR as processed.
        
        Args:
            pr_number: The PR number to mark as processed
        """
        self.processed_prs.add(pr_number)
        logger.debug(f"Marked PR #{pr_number} as processed")

    async def is_processed(self, pr_number: int) -> bool:
        """Check if a PR has been processed.
        
        Args:
            pr_number: The PR number to check
            
        Returns:
            bool: True if the PR has been processed, False otherwise
        """
        return pr_number in self.processed_prs

    def mark_pr_as_processed(self, pr_number: int):
        """Mark a PR as processed.
        
        Args:
            pr_number: PR number to mark as processed
        """
        self.processed_prs.add(pr_number)
        # In a real implementation, we would save this to persistent storage


def create_pr_fetcher(config: Config) -> PRFetcher:
    """Create and initialize a PRFetcher instance.
    
    Args:
        config: Application configuration
        
    Returns:
        PRFetcher: Initialized PRFetcher instance
    """
    try:
        github_integration = GitHubIntegration(config=config)
        return PRFetcher(github_integration, config)
    except Exception as e:
        logger.error(f"Failed to initialize GitHub integration: {str(e)}")
        raise
