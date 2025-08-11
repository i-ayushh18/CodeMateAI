#!/usr/bin/env python3
"""
Notification Manager

Handles sending notifications via email using either SMTP or curl.
"""
import logging
import subprocess
import json
from dataclasses import dataclass
from typing import Dict, List, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    email_provider: str  # 'smtp' or 'curl'
    curl_command: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None

class NotificationManager:
    """Manages sending notifications via email."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        # If config is already a NotificationConfig object, use it directly
        if isinstance(config, NotificationConfig):
            self.config = config
        else:
            # For backward compatibility with dictionary configs
            self.config = NotificationConfig(
                email_provider=getattr(config, 'email_provider', 'smtp'),
                curl_command=getattr(config, 'curl_command', None),
                smtp_server=getattr(config, 'smtp_server', None),
                smtp_port=getattr(config, 'smtp_port', 587),
                smtp_username=getattr(config, 'smtp_username', None),
                smtp_password=getattr(config, 'smtp_password', None),
                email_from=getattr(config, 'email_from', None)
            )
    
    async def send_email(self, to_emails: List[str], subject: str, message: str) -> bool:
        """
        Send an email using the configured provider.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email body
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not to_emails:
            logger.warning("No recipients specified for email")
            return False
            
        if self.config.email_provider.lower() == 'curl' and self.config.curl_command:
            return await self._send_via_curl(to_emails, subject, message)
        else:
            return await self._send_via_smtp(to_emails, subject, message)
    
    async def send_notification(self, message: str, level: str = 'info', to_emails: Optional[List[str]] = None) -> bool:
        """
        Send a notification message.
        
        Args:
            message: The notification message
            level: Notification level ('info', 'warning', 'error')
            to_emails: Optional list of email addresses to send to (uses config default if None)
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        # For now, we'll use the email_to from config
        # In a real implementation, you might want to get this from config
        if to_emails is None:
            # This would need to be passed from the config
            to_emails = ["vermaayushbly@gmail.com"]  # Default for testing
        
        subject = f"PR Agent Notification - {level.upper()}"
        
        # Format the message with level
        formatted_message = f"""
PR Agent Notification

Level: {level.upper()}
Message: {message}

---
Sent by PR Agentic Workflow
        """
        
        return await self.send_email(to_emails, subject, formatted_message)
    
    async def _send_via_curl(self, to_emails: List[str], subject: str, message: str) -> bool:
        """Send email using curl command."""
        try:
            import json
            import platform
            
            # Construct the JSON payload
            payload = {
                "email": to_emails[0] if to_emails else "vermaayushbly@gmail.com",
                "subject": subject,
                "email_body": message
            }
            
            # Convert to JSON string
            json_payload = json.dumps(payload)
            
            # Construct the curl command based on the platform
            if platform.system() == "Windows":
                # Windows-friendly curl command
                cmd = [
                    "curl",
                    "-X", "POST",
                    "https://bytelyst-notification-fastapi-522468355655.europe-west1.run.app/api/send-email",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
            else:
                # Unix-friendly curl command
                cmd = [
                    "curl",
                    "-X", "POST",
                    "https://bytelyst-notification-fastapi-522468355655.europe-west1.run.app/api/send-email",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
            
            # Execute the curl command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Email sent successfully to {', '.join(to_emails)}")
                return True
            else:
                logger.error(f"Failed to send email via curl: {result.stderr}")
                logger.debug(f"Executed command: {' '.join(cmd)}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email via curl: {str(e)}")
            return False
    
    async def _send_via_smtp(self, to_emails: List[str], subject: str, message: str) -> bool:
        """Send email using SMTP."""
        if not all([self.config.smtp_server, self.config.email_from]):
            logger.error("SMTP configuration is incomplete")
            return False
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))
            
            # Connect to server and send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_username and self.config.smtp_password:
                    server.starttls()
                    server.login(self.config.smtp_username, self.config.smtp_password)
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {str(e)}")
            return False
