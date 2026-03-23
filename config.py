"""
Configuration Management

Handles loading and validation of configuration from TOML files.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

try:
    import tomli as toml
except ImportError:
    import tomllib as toml

logger = logging.getLogger(__name__)

@dataclass
class GitHubConfig:
    """GitHub API configuration."""
    token: str = ""
    repo_owner: str = ""
    repo_name: str = ""
    pr_fetch_limit: int = 10
    include_drafts: bool = False

@dataclass
class PerplexityConfig:
    """Perplexity AI configuration."""
    api_key: str = ""
    model: str = "llama-3.1-70b-instruct"
    temperature: float = 0.7
    max_tokens: int = 4000

@dataclass
class NotificationConfig:
    """Notification configuration."""
    enabled: bool = True
    email_to: List[str] = field(default_factory=list)
    email_provider: str = "curl"  # 'smtp' or 'curl'
    curl_command: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "pr_workflow.log"

@dataclass
class AgentConfig:
    """Agent configuration."""
    workspace_dir: str = "./workspace"
    max_retries: int = 3
    timeout_seconds: int = 300
    auto_commit: bool = False
    target_branch: str = "main"

# Simplified CodeReviewConfig - removed unused fields
@dataclass
class CodeReviewConfig:
    """Code review configuration."""
    enabled: bool = True

@dataclass
class Config:
    """Main configuration class."""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    perplexity: PerplexityConfig = field(default_factory=PerplexityConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    code_review: CodeReviewConfig = field(default_factory=CodeReviewConfig)

def load_config(config_path: str = "config.toml") -> Config:
    """
    Load configuration from a TOML file.
    
    Args:
        config_path: Path to TOML configuration file
        
    Returns:
        Config: Loaded configuration
    """
    try:
        # Read TOML file
        with open(config_path, "rb") as f:
            config_data = toml.load(f)
        
        # Create configuration objects
        config = Config()
        
        # GitHub config
        if 'github' in config_data:
            github_data = config_data['github']
            # Check for environment variable first, then config file
            github_token = os.getenv('GITHUB_TOKEN', github_data.get('token', ''))
            config.github = GitHubConfig(
                token=github_token,
                repo_owner=github_data.get('repo_owner', ''),
                repo_name=github_data.get('repo_name', ''),
                pr_fetch_limit=github_data.get('pr_fetch_limit', 10),
                include_drafts=github_data.get('include_drafts', False)
            )
        
        # Perplexity config
        if 'perplexity' in config_data:
            perplexity_data = config_data['perplexity']
            perplexity_api_key = os.getenv('PERPLEXITY_API_KEY', perplexity_data.get('api_key', ''))
            config.perplexity = PerplexityConfig(
                api_key=perplexity_api_key,
                model=perplexity_data.get('model', 'llama-3.1-70b-instruct'),
                temperature=float(perplexity_data.get('temperature', 0.7)),
                max_tokens=int(perplexity_data.get('max_tokens', 4000))
            )
        
        # Notifications config
        if 'notifications' in config_data:
            notif_data = config_data['notifications']
            config.notifications = NotificationConfig(
                enabled=notif_data.get('enabled', True),
                email_to=notif_data.get('email_to', []),
                email_provider=notif_data.get('email_provider', 'curl'),
                curl_command=notif_data.get('curl_command', ''),
                smtp_server=notif_data.get('smtp_server', ''),
                smtp_port=int(notif_data.get('smtp_port', 587)),
                smtp_username=notif_data.get('smtp_username', ''),
                smtp_password=notif_data.get('smtp_password', ''),
                email_from=notif_data.get('email_from', '')
            )
        
        # Logging config
        if 'logging' in config_data:
            log_data = config_data['logging']
            config.logging = LoggingConfig(
                level=log_data.get('level', 'INFO'),
                file=log_data.get('file', 'pr_workflow.log')
            )
        
        # Agent config
        if 'agent' in config_data:
            agent_data = config_data['agent']
            config.agent = AgentConfig(
                workspace_dir=agent_data.get('workspace_dir', './workspace'),
                max_retries=int(agent_data.get('max_retries', 3)),
                timeout_seconds=int(agent_data.get('timeout_seconds', 300)),
                auto_commit=agent_data.get('auto_commit', False),
                target_branch=agent_data.get('target_branch', 'main')
            )
        
        # Code review config
        if 'code_review' in config_data:
            cr_data = config_data['code_review']
            config.code_review = CodeReviewConfig(
                enabled=cr_data.get('enabled', True)
            )
        
        return config
        
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except toml.TOMLDecodeError as e:
        logger.error(f"Invalid TOML configuration: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise
