"""
Perplexity AI integration for the PR Agentic Workflow.
"""
import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class PerplexityIntegration:
    """Integration with Perplexity AI's API for text generation."""
    
    BASE_URL = "https://api.perplexity.ai"
    
    def __init__(self, api_key: str, model: str = "sonar-pro"):
        """Initialize the Perplexity AI integration.
        
        Args:
            api_key: Perplexity API key
            model: Model to use (default: sonar-pro)
        """
        if not api_key or api_key.strip() == "":
            raise ValueError("Perplexity API key is required")
        
        self.api_key = api_key.strip()
        self.model = model
        self._session = None
        logger.info(f"Initialized Perplexity model: {self.model}")
        
        # Validate API key format
        if not self.api_key.startswith("pplx-"):
            logger.warning("Perplexity API key should start with 'pplx-'. Please check your configuration.")
    
    @property
    def session(self):
        """Get or create an aiohttp client session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp client session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 2048, 
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using Perplexity AI.
        
        Args:
            prompt: The prompt to generate text from
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-2)
            **kwargs: Additional parameters for the API
            
        Returns:
            Generated text
        """
        url = f"{self.BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 401:
                    error_msg = "Perplexity API key is invalid or expired. Please check your configuration."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status == 403:
                    error_msg = "Perplexity API access denied. Please check your API key permissions."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status >= 400:
                    response_text = await response.text()
                    error_msg = f"Perplexity API error {response.status}: {response_text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content']
                
        except Exception as e:
            if "Perplexity API" in str(e):
                # Re-raise our custom error messages
                raise
            else:
                error_msg = f"Error generating text with Perplexity: {str(e)}"
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    try:
                        error_msg += f"\nResponse: {await e.response.text()}"
                    except:
                        pass
                logger.error(error_msg)
                raise Exception(f"Perplexity API error: {str(e)}")
    
