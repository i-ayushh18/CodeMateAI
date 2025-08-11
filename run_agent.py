#!/usr/bin/env python3
"""
PR Agentic Workflow - Single Command Interface

This script provides a single command to run the PR agent with all functionality.
Usage: python run_agent.py [options]

Options:
    --help, -h          Show this help message
    --pr <number>       Process a specific PR number
    --issue <number>    Process a specific issue number
    --repo <owner/repo> Specify repository (default: from config)
    --test              Run in test mode (creates test PR and processes it)
    --review            Review mode (analyze only, no changes)
    --developer         Developer mode (analyze and apply changes)
    --notify            Enable notifications (default: enabled)
    --no-notify         Disable notifications
    --verbose, -v       Enable verbose logging
    --quiet, -q         Enable quiet mode (minimal output)
"""
import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))

from config import load_config
from integrations.github_integration import GitHubIntegration
from integrations.perplexity_integration import PerplexityIntegration
from agents.developer_agent import DeveloperAgent
from agents.notification_manager import NotificationManager
from services.pr_processor import PRProcessor

def setup_logging(verbose=False, quiet=False):
    """Setup logging configuration."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    # Use a format that's compatible with Windows
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pr_agent.log', encoding='utf-8')
        ]
    )

async def run_agent(pr_number=None, issue_number=None, repo=None, test_mode=False, review_mode=False, developer_mode=False, notifications=True, verbose=False):
    """Run the PR agent with the specified options."""
    llm = None
    try:
        # Load configuration
        logger = logging.getLogger(__name__)
        logger.info("Starting PR Agentic Workflow...")
        
        config = load_config()
        
        # Override repository if specified
        if repo:
            owner, repo_name = repo.split('/')
            config.github.repo_owner = owner
            config.github.repo_name = repo_name
        
        # Initialize components
        logger.info("Initializing components...")
        
        github = GitHubIntegration(github_config=config.github)
        llm = PerplexityIntegration(
            api_key=config.perplexity.api_key,
            model=config.perplexity.model
        )
        
        notification_manager = None
        if notifications:
            notification_manager = NotificationManager(config.notifications)
            logger.info("Notifications enabled")
        else:
            logger.info("Notifications disabled")
        
        # Test repository access
        repo_obj = github.get_repository()
        logger.info(f"Repository access: {repo_obj.full_name}")
        
        # Check permissions - handle cases where permissions might be None
        if hasattr(repo_obj, 'permissions') and repo_obj.permissions:
            if not repo_obj.permissions.push:
                logger.error("No write access to repository")
                return False
        else:
            logger.warning("Could not determine repository permissions - proceeding with limited functionality")
            # Continue with limited functionality (review mode should still work)
        
        # Initialize agents
        developer_agent = DeveloperAgent(
            llm_integration=llm,
            github_integration=github,
            notification_manager=notification_manager,
            workspace_dir="./workspace",
            config=config
        )
        
        pr_processor = PRProcessor(
            config=config,
            github_integration=github,
            notification_manager=notification_manager,
            llm_integration=llm
        )
        
        logger.info("All components initialized")
        
        if test_mode:
            return await run_test_mode(github, pr_processor, notification_manager, config)
        elif issue_number:
            # Handle issue processing
            if review_mode:
                return await process_specific_issue_review(github, developer_agent, issue_number, notification_manager)
            elif developer_mode:
                return await process_specific_issue_developer(github, developer_agent, issue_number, notification_manager)
            else:
                # Default to developer mode if no mode specified
                return await process_specific_issue_developer(github, developer_agent, issue_number, notification_manager)
        elif pr_number:
            if review_mode:
                return await process_specific_pr_review(github, pr_processor, pr_number, notification_manager)
            elif developer_mode:
                return await process_specific_pr_developer(github, pr_processor, pr_number, notification_manager)
            else:
                # Default to developer mode if no mode specified
                return await process_specific_pr_developer(github, pr_processor, pr_number, notification_manager)
        else:
            if review_mode:
                return await process_all_items_review(github, pr_processor, developer_agent, notification_manager, config)
            elif developer_mode:
                return await process_all_items_developer(github, pr_processor, developer_agent, notification_manager, config)
            else:
                # Default to developer mode if no mode specified
                return await process_all_items_developer(github, pr_processor, developer_agent, notification_manager, config)
            
    except Exception as e:
        logger.error(f"Agent failed: {str(e)}", exc_info=True)
        if 'notification_manager' in locals() and notification_manager:
            await notification_manager.send_notification(
                message=f"PR Agent failed: {str(e)}",
                level="error"
            )
        return False
    finally:
        if llm:
            try:
                await llm.close()
                logger.info("LLM session closed")
            except Exception as close_error:
                logger.warning(f"Error closing LLM session: {close_error}")

async def run_test_mode(github, pr_processor, notification_manager, config):
    """Run the agent in test mode - create a test PR and process it."""
    logger = logging.getLogger(__name__)
    
    if notification_manager:
        await notification_manager.send_notification(
            message="Starting PR Agent in test mode",
            level="info"
        )
    
    # Create test implementation
    test_content = '''
def hello_world():
    """Simple test function."""
    print("Hello, World!")
    return "Hello, World!"

if __name__ == "__main__":
    hello_world()
'''
    
    # Create test branch and file
    test_branch = f"test-agent-{int(asyncio.get_event_loop().time())}"
    
    logger.info(f"Creating test branch: {test_branch}")
    
    branch_created = await github.create_branch(
        repo=f"{config.github.repo_owner}/{config.github.repo_name}",
        branch=test_branch,
        base_branch="main"
    )
    
    if not branch_created:
        logger.error("Failed to create test branch")
        return False
    
    # Create test file
    file_created = await github.update_file(
        repo=f"{config.github.repo_owner}/{config.github.repo_name}",
        path="test_agent.py",
        content=test_content,
        message="Test file for PR Agent",
        branch=test_branch
    )
    
    if not file_created:
        logger.error("Failed to create test file")
        return False
    
    # Create PR
    pr_url = await github.create_pull_request(
        repo=f"{config.github.repo_owner}/{config.github.repo_name}",
        title="Test PR: Agent Test",
        body="This is a test PR for the PR Agent.",
        head=test_branch,
        base="main"
    )
    
    if not pr_url:
        logger.error("Failed to create test PR")
        return False
    
    logger.info(f"Test PR created: {pr_url}")
    
    # Process the PR
    pr_number = int(pr_url.split('/')[-1])
    pr_info = github.get_pr_info_dict(pr_number)
    
    if not pr_info:
        logger.error("Could not get PR info")
        return False
    
    logger.info(f"Processing test PR #{pr_number}")
    
    result = await pr_processor.process_pr(pr_info)
    
    if result.success:
        logger.info("Test completed successfully!")
        if notification_manager:
            await notification_manager.send_notification(
                message=f"Test completed successfully! Processed PR #{pr_number}",
                level="info"
            )
        return True
    else:
        logger.error(f"Test failed: {result.message}")
        return False

async def process_specific_pr_review(github, pr_processor, pr_number, notification_manager):
    """Process a specific PR in review mode (analyze only, no changes)."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Reviewing PR #{pr_number} (review mode)")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Starting to review PR #{pr_number} (review mode)",
            level="info"
        )
    
    pr_info = github.get_pr_info_dict(pr_number)
    
    if not pr_info:
        logger.error(f"Could not get PR #{pr_number} info")
        return False
    
    logger.info(f"PR Title: {pr_info.get('title', 'No title')}")
    logger.info(f"PR URL: {pr_info.get('html_url', 'No URL')}")
    
    # Use the review-only method
    result = await pr_processor.review_pr_only(pr_info)
    
    if result.success:
        logger.info("PR reviewed successfully!")
        logger.info(f"Actions taken: {len(result.actions_taken)}")
        
        for action in result.actions_taken:
            logger.info(f"   - {action.get('action', 'unknown')}: {action.get('details', 'No details')}")
        
        if notification_manager:
            await notification_manager.send_notification(
                message=f"Successfully reviewed PR #{pr_number}. Actions: {len(result.actions_taken)}",
                level="info"
            )
        
        return True
    else:
        logger.error(f"Failed to review PR: {result.message}")
        return False

async def process_specific_pr_developer(github, pr_processor, pr_number, notification_manager):
    """Process a specific PR in developer mode (analyze and apply changes)."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Processing PR #{pr_number} (developer mode)")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Starting to process PR #{pr_number} (developer mode)",
            level="info"
        )
    
    pr_info = github.get_pr_info_dict(pr_number)
    
    if not pr_info:
        logger.error(f"Could not get PR #{pr_number} info")
        return False
    
    logger.info(f"PR Title: {pr_info.get('title', 'No title')}")
    logger.info(f"PR URL: {pr_info.get('html_url', 'No URL')}")
    
    # Use the full processing method
    result = await pr_processor.process_pr(pr_info)
    
    if result.success:
        logger.info("PR processed successfully!")
        logger.info(f"Actions taken: {len(result.actions_taken)}")
        
        for action in result.actions_taken:
            logger.info(f"   - {action.get('action', 'unknown')}: {action.get('details', 'No details')}")
            if 'pr_url' in action:
                logger.info(f"     New PR: {action['pr_url']}")
        
        if notification_manager:
            await notification_manager.send_notification(
                message=f"Successfully processed PR #{pr_number}. Actions: {len(result.actions_taken)}",
                level="info"
            )
        
        return True
    else:
        logger.error(f"Failed to process PR: {result.message}")
        return False

async def process_all_prs_review(github, pr_processor, notification_manager, config):
    """Process all available PRs in review mode."""
    logger = logging.getLogger(__name__)
    
    logger.info("Fetching all PRs for review...")
    
    if notification_manager:
        await notification_manager.send_notification(
            message="Starting to review all PRs",
            level="info"
        )
    
    # Get all PRs
    prs = github.get_pull_requests(limit=config.github.pr_fetch_limit)
    
    if not prs:
        logger.info("No PRs found to review")
        return True
    
    logger.info(f"Found {len(prs)} PRs to review")
    
    success_count = 0
    for pr in prs:
        pr_info = github.get_pr_info_dict(pr.number)
        if pr_info:
            logger.info(f"Reviewing PR #{pr.number}: {pr.title}")
            
            result = await pr_processor.review_pr_only(pr_info)
            
            if result.success:
                success_count += 1
                logger.info(f"PR #{pr.number} reviewed successfully")
            else:
                logger.warning(f"PR #{pr.number} review failed: {result.message}")
    
    logger.info(f"Review completed! {success_count}/{len(prs)} PRs reviewed successfully")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Review completed! {success_count}/{len(prs)} PRs reviewed successfully",
            level="info"
        )
    
    return success_count > 0

async def process_all_prs_developer(github, pr_processor, notification_manager, config):
    """Process all available PRs in developer mode."""
    logger = logging.getLogger(__name__)
    
    logger.info("Fetching all PRs for processing...")
    
    if notification_manager:
        await notification_manager.send_notification(
            message="Starting to process all PRs",
            level="info"
        )
    
    # Get all PRs
    prs = github.get_pull_requests(limit=config.github.pr_fetch_limit)
    
    if not prs:
        logger.info("No PRs found to process")
        return True
    
    logger.info(f"Found {len(prs)} PRs to process")
    
    success_count = 0
    for pr in prs:
        pr_info = github.get_pr_info_dict(pr.number)
        if pr_info:
            logger.info(f"Processing PR #{pr.number}: {pr.title}")
            
            result = await pr_processor.process_pr(pr_info)
            
            if result.success:
                success_count += 1
                logger.info(f"PR #{pr.number} processed successfully")
            else:
                logger.warning(f"PR #{pr.number} processing failed: {result.message}")
    
    logger.info(f"Processing completed! {success_count}/{len(prs)} PRs processed successfully")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Processing completed! {success_count}/{len(prs)} PRs processed successfully",
            level="info"
        )
    
    return success_count > 0

async def process_specific_issue_review(github, developer_agent, issue_number, notification_manager):
    """Process a specific issue in review mode (analyze only, no changes)."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Reviewing issue #{issue_number} (review mode)")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Starting to review issue #{issue_number} (review mode)",
            level="info"
        )
    
    issue_info = github.get_issue_info_dict(issue_number)
    
    if not issue_info:
        logger.error(f"Could not get issue #{issue_number} info")
        return False
    
    logger.info(f"Issue Title: {issue_info.get('title', 'No title')}")
    logger.info(f"Issue URL: {issue_info.get('html_url', 'No URL')}")
    
    # Review the issue
    try:
        review_result = await developer_agent.review_code(
            code=issue_info.get('body', ''),
            language='markdown',
            task_description=f"Review issue #{issue_number}: {issue_info.get('title', '')}"
        )
        
        if review_result.get('success', False):
            logger.info("Issue reviewed successfully!")
            
            # Add review comment to the issue
            if review_result.get('feedback'):
                comment_result = await developer_agent.add_issue_comment(
                    issue_number=issue_number,
                    comment=f"## Issue Review\n\n{review_result['feedback']}"
                )
                
                if comment_result.get('success', False):
                    logger.info("Review comment added to issue successfully")
                else:
                    logger.warning("Failed to add review comment to issue")
            
            if notification_manager:
                await notification_manager.send_notification(
                    message=f"Successfully reviewed issue #{issue_number}",
                    level="info"
                )
            
            return True
        else:
            logger.error(f"Failed to review issue: {review_result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error reviewing issue: {str(e)}")
        return False

async def process_specific_issue_developer(github, developer_agent, issue_number, notification_manager):
    """Process a specific issue in developer mode (analyze and create PR with implementation)."""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Processing issue #{issue_number} (developer mode)")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Starting to process issue #{issue_number} (developer mode)",
            level="info"
        )
    
    issue_info = github.get_issue_info_dict(issue_number)
    
    if not issue_info:
        logger.error(f"Could not get issue #{issue_number} info")
        return False
    
    logger.info(f"Issue Title: {issue_info.get('title', 'No title')}")
    logger.info(f"Issue URL: {issue_info.get('html_url', 'No URL')}")
    
    # Process the issue by implementing the feature
    try:
        logger.info("Implementing feature from issue requirements...")
        
        # Use the new implement_feature_from_issue method
        implementation_result = await developer_agent.implement_feature_from_issue(issue_info)
        
        if implementation_result.get('success', False):
            logger.info("Feature implementation completed successfully!")
            
            pr_url = implementation_result.get('pr_url')
            branch = implementation_result.get('branch')
            files_created = implementation_result.get('files_created', [])
            
            logger.info(f"Pull Request created: {pr_url}")
            logger.info(f"Feature branch: {branch}")
            logger.info(f"Files created/updated: {len(files_created)}")
            
            # Send success notification
            if notification_manager:
                await notification_manager.send_notification(
                    message=f"Successfully implemented feature from issue #{issue_number}. PR: {pr_url}",
                    level="info"
                )
            
            return True
        else:
            error_msg = f"Failed to implement feature from issue: {implementation_result.get('message', 'Unknown error')}"
            logger.error(error_msg)
            
            # Add error comment to the issue
            try:
                error_comment = f"""
## ❌ Feature Implementation Failed

The AI agent encountered an error while trying to implement your feature:

**Error:** {implementation_result.get('message', 'Unknown error')}

Please check the issue description and try again, or contact the development team for assistance.
                """
                
                await developer_agent.add_issue_comment(issue_number, error_comment)
                logger.info(f"Added error comment to issue #{issue_number}")
                
            except Exception as comment_error:
                logger.warning(f"Failed to add error comment to issue #{issue_number}: {comment_error}")
            
            if notification_manager:
                await notification_manager.send_notification(
                    message=f"Failed to implement feature from issue #{issue_number}: {error_msg}",
                    level="error"
                )
            
            return False
            
    except Exception as e:
        logger.error(f"Error processing issue: {str(e)}")
        
        # Add error comment to the issue
        try:
            error_comment = f"""
## ❌ Feature Implementation Failed

The AI agent encountered an unexpected error:

**Error:** {str(e)}

Please try again or contact the development team for assistance.
            """
            
            await developer_agent.add_issue_comment(issue_number, error_comment)
            logger.info(f"Added error comment to issue #{issue_number}")
            
        except Exception as comment_error:
            logger.warning(f"Failed to add error comment to issue #{issue_number}: {comment_error}")
        
        if notification_manager:
            await notification_manager.send_notification(
                message=f"Error processing issue #{issue_number}: {str(e)}",
                level="error"
            )
        
        return False

async def process_all_items_review(github, pr_processor, developer_agent, notification_manager, config):
    """Process all available PRs and issues in review mode."""
    logger = logging.getLogger(__name__)
    
    logger.info("Fetching all PRs and issues for review...")
    
    if notification_manager:
        await notification_manager.send_notification(
            message="Starting to review all PRs and issues",
            level="info"
        )
    
    # Get all PRs and issues
    prs = github.get_pull_requests(limit=getattr(config.github, 'pr_fetch_limit', 5))
    issues = github.get_issues(limit=getattr(config.github, 'issue_fetch_limit', 5))
    
    if not prs and not issues:
        logger.info("No PRs or issues found to review")
        return True
    
    logger.info(f"Found {len(prs)} PRs and {len(issues)} issues to review")
    
    success_count = 0
    
    # Review PRs
    for pr in prs:
        pr_info = github.get_pr_info_dict(pr.number)
        if pr_info:
            logger.info(f"Reviewing PR #{pr.number}: {pr.title}")
            result = await pr_processor.review_pr_only(pr_info)
            if result.success:
                success_count += 1
                logger.info(f"PR #{pr.number} reviewed successfully")
            else:
                logger.warning(f"PR #{pr.number} review failed: {result.message}")
    
    # Review issues
    for issue in issues:
        issue_info = github.get_issue_info_dict(issue.number)
        if issue_info:
            logger.info(f"Reviewing Issue #{issue.number}: {issue.title}")
            result = await process_specific_issue_review(github, developer_agent, issue.number, notification_manager)
            if result:
                success_count += 1
                logger.info(f"Issue #{issue.number} reviewed successfully")
            else:
                logger.warning(f"Issue #{issue.number} review failed")
    
    total_items = len(prs) + len(issues)
    logger.info(f"Review completed! {success_count}/{total_items} items reviewed successfully")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Review completed! {success_count}/{total_items} items reviewed successfully",
            level="info"
        )
    
    return success_count > 0

async def process_all_items_developer(github, pr_processor, developer_agent, notification_manager, config):
    """Process all available PRs and issues in developer mode."""
    logger = logging.getLogger(__name__)
    
    logger.info("Fetching all PRs and issues for processing...")
    
    if notification_manager:
        await notification_manager.send_notification(
            message="Starting to process all PRs and issues",
            level="info"
        )
    
    # Get all PRs and issues
    prs = github.get_pull_requests(limit=getattr(config.github, 'pr_fetch_limit', 5))
    issues = github.get_issues(limit=getattr(config.github, 'issue_fetch_limit', 5))
    
    if not prs and not issues:
        logger.info("No PRs or issues found to process")
        return True
    
    logger.info(f"Found {len(prs)} PRs and {len(issues)} issues to process")
    
    success_count = 0
    
    # Process PRs
    for pr in prs:
        pr_info = github.get_pr_info_dict(pr.number)
        if pr_info:
            logger.info(f"Processing PR #{pr.number}: {pr.title}")
            result = await pr_processor.process_pr(pr_info)
            if result.success:
                success_count += 1
                logger.info(f"PR #{pr.number} processed successfully")
            else:
                logger.warning(f"PR #{pr.number} processing failed: {result.message}")
    
    # Process issues
    for issue in issues:
        issue_info = github.get_issue_info_dict(issue.number)
        if issue_info:
            logger.info(f"Processing Issue #{issue.number}: {issue.title}")
            result = await process_specific_issue_developer(github, developer_agent, issue.number, notification_manager)
            if result:
                success_count += 1
                logger.info(f"Issue #{issue.number} processed successfully")
            else:
                logger.warning(f"Issue #{issue.number} processing failed")
    
    total_items = len(prs) + len(issues)
    logger.info(f"Processing completed! {success_count}/{total_items} items processed successfully")
    
    if notification_manager:
        await notification_manager.send_notification(
            message=f"Processing completed! {success_count}/{total_items} items processed successfully",
            level="info"
        )
    
    return success_count > 0

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PR Agentic Workflow - AI-powered PR review and improvement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py                    # Process all PRs and issues (developer mode)
  python run_agent.py --pr 123          # Process specific PR (developer mode)
  python run_agent.py --issue 123       # Process specific issue (developer mode)
  python run_agent.py --review --pr 123 # Review specific PR (analyze only)
  python run_agent.py --review --issue 123 # Review specific issue (analyze only)
  python run_agent.py --developer --pr 123 # Process specific PR (analyze and apply changes)
  python run_agent.py --developer --issue 123 # Process specific issue (analyze and apply changes)
  python run_agent.py --review          # Review all PRs and issues (analyze only)
  python run_agent.py --developer       # Process all PRs and issues (analyze and apply changes)
  python run_agent.py --test            # Run in test mode
  python run_agent.py --repo owner/repo # Use different repository
  python run_agent.py --verbose         # Enable verbose logging
  python run_agent.py --no-notify       # Disable notifications
        """
    )
    
    parser.add_argument('--pr', type=int, help='Process specific PR number')
    parser.add_argument('--issue', type=int, help='Process specific issue number')
    parser.add_argument('--repo', help='Repository in format owner/repo')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--review', action='store_true', help='Review mode (analyze only, no changes)')
    parser.add_argument('--developer', action='store_true', help='Developer mode (analyze and apply changes)')
    parser.add_argument('--notify', action='store_true', help='Enable notifications (default)')
    parser.add_argument('--no-notify', action='store_true', help='Disable notifications')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true', help='Enable quiet mode')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    
    # Determine notification setting
    notifications = not args.no_notify  # Default to True unless --no-notify is specified
    
    # Determine modes
    review_mode = args.review
    developer_mode = args.developer
    test_mode = args.test
    
    # Validate mode arguments
    if review_mode and developer_mode:
        print("Error: Cannot use both --review and --developer modes at the same time")
        sys.exit(1)
    
    # Run the agent
    success = asyncio.run(run_agent(
        pr_number=args.pr,
        issue_number=args.issue,
        repo=args.repo,
        test_mode=test_mode,
        review_mode=review_mode,
        developer_mode=developer_mode,
        notifications=notifications,
        verbose=args.verbose
    ))
    
    if success:
        print("PR Agent completed successfully!")
        sys.exit(0)
    else:
        print("PR Agent failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 