#!/usr/bin/env python3
"""
Configuration Management

Handles loading and validation of configuration from TOML files.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# Try to import tomli (for Python < 3.11)
try:
    import tomli as toml
except ImportError:
    # For Python 3.11+
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
class LLMConfig:
    """LLM configuration."""
    provider: str = "gemini"
    api_key: str = ""
    model: str = "gemini-pro"
    temperature: float = 0.7
    max_tokens: int = 2000



@dataclass
class PerplexityConfig:
    """Perplexity AI configuration."""
    api_key: str = ""
    model: str = "sonar-pro"
    temperature: float = 0.7
    max_tokens: int = 2000

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

@dataclass
class CodeReviewConfig:
    """Code review configuration."""
    enabled: bool = True
    rules: List[str] = field(default_factory=lambda: [
        "check_code_style",
        "check_security",
        "check_performance"
    ])
    include_patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["**/node_modules/**", "**/*.d.ts"])

@dataclass
class Config:
    """Main configuration class."""
    github: GitHubConfig = field(default_factory=GitHubConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    perplexity: PerplexityConfig = field(default_factory=PerplexityConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    code_review: CodeReviewConfig = field(default_factory=CodeReviewConfig)

def load_config(config_path: str = "config.toml") -> Config:
    """
    Load configuration from a TOML file.
    
    Args:
        config_path: Path to the TOML configuration file
        
    Returns:
        Config: Loaded configuration
    """
    try:
        # Read the TOML file
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
        
        # LLM config
        if 'llm' in config_data:
            llm_data = config_data['llm']
            config.llm = LLMConfig(
                provider=llm_data.get('provider', 'gemini'),
                api_key=llm_data.get('api_key', ''),
                model=llm_data.get('model', 'gemini-pro'),
                temperature=float(llm_data.get('temperature', 0.7)),
                max_tokens=int(llm_data.get('max_tokens', 2000))
            )
        
        # Perplexity config
        if 'perplexity' in config_data:
            perplexity_data = config_data['perplexity']
            # Check for environment variable first, then config file
            perplexity_api_key = os.getenv('PERPLEXITY_API_KEY', perplexity_data.get('api_key', ''))
            config.perplexity = PerplexityConfig(
                api_key=perplexity_api_key,
                model=perplexity_data.get('model', 'sonar-pro'),
                temperature=float(perplexity_data.get('temperature', 0.7)),
                max_tokens=int(perplexity_data.get('max_tokens', 2000))
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
                enabled=cr_data.get('enabled', True),
                rules=cr_data.get('rules', [
                    "check_code_style",
                    "check_security",
                    "check_performance"
                ]),
                include_patterns=cr_data.get('include_patterns', ["**/*.py", "**/*.js", "**/*.ts"]),
                exclude_patterns=cr_data.get('exclude_patterns', ["**/node_modules/**", "**/*.d.ts"])
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