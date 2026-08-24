"""
OpenRouter AI integration for the PR Agentic Workflow.
"""
import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class OpenRouterIntegration:
    """Integration with OpenRouter AI's API for text generation."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key: str, model: str = "meta-llama/llama-3.1-70b-instruct"):
        """Initialize the OpenRouter AI integration.
        
        Args:
            api_key: OpenRouter API key
            model: Model to use (default: meta-llama/llama-3.1-70b-instruct)
                   Popular free models:
                   - meta-llama/llama-3.1-70b-instruct
                   - meta-llama/llama-3.1-8b-instruct
                   - mistralai/mistral-7b-instruct
                   - google/gemma-7b-it
        """
        if not api_key or api_key.strip() == "":
            raise ValueError("OpenRouter API key is required")
        
        self.api_key = api_key.strip()
        self.model = model
        self._session = None
        logger.info(f"Initialized OpenRouter model: {self.model}")
        
        # Validate API key format (OpenRouter keys start with 'sk-or-')
        if not self.api_key.startswith("sk-or-"):
            logger.warning("OpenRouter API key should start with 'sk-or-'. Please check your configuration.")
    
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
    
    def test_connection(self) -> bool:
        """Test if the OpenRouter API connection is working.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        import asyncio
        
        async def _test():
            try:
                result = await self.generate_text("Say 'ok'", max_tokens=5, temperature=0)
                return bool(result)
            except Exception as e:
                logger.error(f"OpenRouter connection test failed: {str(e)}")
                return False
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, just validate the key format
                return bool(self.api_key and self.api_key.startswith("sk-or-"))
            return loop.run_until_complete(_test())
        except RuntimeError:
            # No event loop exists yet
            return asyncio.run(_test())
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 2048, 
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text using OpenRouter AI.
        
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
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/CodeMateAI",  # Optional but recommended
            "X-Title": "CodeMateAI PR Agent"  # Optional but recommended
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
                    error_msg = "OpenRouter API key is invalid or expired. Please check your configuration."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status == 402:
                    error_msg = "OpenRouter API credits exhausted. Please add credits to your account."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status == 403:
                    error_msg = "OpenRouter API access denied. Please check your API key permissions."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status == 429:
                    error_msg = "OpenRouter API rate limit exceeded. Please try again later."
                    logger.error(error_msg)
                    raise Exception(error_msg)
                elif response.status >= 400:
                    response_text = await response.text()
                    error_msg = f"OpenRouter API error {response.status}: {response_text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                response.raise_for_status()
                result = await response.json()
                return result['choices'][0]['message']['content']
                
        except Exception as e:
            if "OpenRouter API" in str(e):
                # Re-raise our custom error messages
                raise
            else:
                error_msg = f"Error generating text with OpenRouter: {str(e)}"
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    try:
                        error_msg += f"\nResponse: {await e.response.text()}"
                    except:
                        pass
                logger.error(error_msg)
                raise Exception(f"OpenRouter API error: {str(e)}")
