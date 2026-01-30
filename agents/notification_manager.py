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
        if isinstance(config, NotificationConfig):
            self.config = config
        else:
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
        if not to_emails:
            logger.warning("No recipients specified for email")
            return False
            
        if self.config.email_provider.lower() == 'curl' and self.config.curl_command:
            return await self._send_via_curl(to_emails, subject, message)
        else:
            return await self._send_via_smtp(to_emails, subject, message)
    
    async def send_notification(self, message: str, level: str = 'info', to_emails: Optional[List[str]] = None) -> bool:
        if to_emails is None:
            to_emails = getattr(self.config, 'email_to', [])
            if not to_emails:
                logger.warning("No email recipients configured")
                return False
        
        subject = f"PR Agent Notification - {level.upper()}"
        
        formatted_message = f"""
PR Agent Notification

Level: {level.upper()}
Message: {message}

---
Sent by PR Agentic Workflow
        """
        
        return await self.send_email(to_emails, subject, formatted_message)
    
    async def _send_via_curl(self, to_emails: List[str], subject: str, message: str) -> bool:
        try:
            import json
            import platform
            
            payload = {
                "email": to_emails[0] if to_emails else "",
                "subject": subject,
                "email_body": message
            }
            
            json_payload = json.dumps(payload)
            
            if platform.system() == "Windows":
                cmd = [
                    "curl",
                    "-X", "POST",
                    "https://your-notification-service.com/api/send-email",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
            else:
                cmd = [
                    "curl",
                    "-X", "POST",
                    "https://your-notification-service.com/api/send-email",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
            
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
        required_fields = ['smtp_server', 'smtp_port', 'email_from']
        missing_fields = [field for field in required_fields if not getattr(self.config, field, None)]
        
        if missing_fields:
            logger.error(f"SMTP configuration is incomplete. Missing: {', '.join(missing_fields)}")
            return False
            
        if self.config.smtp_username and not self.config.smtp_password:
            logger.error("SMTP username provided but password is missing")
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))
            
            logger.info(f"Connecting to SMTP server: {self.config.smtp_server}:{self.config.smtp_port}")
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()

                if self.config.smtp_username and self.config.smtp_password:
                    logger.info(f"Authenticating with username: {self.config.smtp_username}")
                    server.login(self.config.smtp_username, self.config.smtp_password)
                else:
                    logger.warning("No SMTP credentials provided - attempting unauthenticated connection")
                
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {', '.join(to_emails)}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            logger.error("For Gmail, make sure you're using an App Password, not your regular password")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email via SMTP: {str(e)}")
            return False
