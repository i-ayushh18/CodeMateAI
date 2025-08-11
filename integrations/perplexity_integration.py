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
    
    async def generate_code(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        **kwargs
    ) -> str:
        """Generate code using Perplexity AI.
        
        Args:
            prompt: The prompt to generate code from
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-2)
            **kwargs: Additional parameters for the API
            
        Returns:
            Generated code
        """
        # For code generation, we can use a lower temperature for more deterministic output
        return await self.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )

    async def generate_code_with_files(
        self,
        task_description: str,
        max_tokens: int = 4000,
        temperature: float = 0.2,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate code with file paths for implementing features.
        
        Args:
            task_description: Description of the feature to implement
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-2)
            **kwargs: Additional parameters for the API
            
        Returns:
            Dict containing generated code with file paths
        """
        prompt = f"""
        Please implement the following feature:

        {task_description}

        Requirements:
        1. Generate clean, production-ready code
        2. Follow best practices for the language/framework
        3. Include proper error handling
        4. Add appropriate documentation
        5. Consider edge cases and validation

        IMPORTANT: You MUST format your response with clear file paths and code blocks.

        Use this EXACT format for each file:

        **File: filename.ext**
        ```language
        // Your code here
        ```

        For example:
        **File: src/main.py**
        ```python
        def main():
            print("Hello World")
        ```

        **File: tests/test_main.py**
        ```python
        def test_main():
            assert True
        ```

        Make sure to:
        - Use realistic file paths that make sense for the project structure
        - Include all necessary imports and dependencies
        - Write code that actually works and follows best practices
        - Consider the project context and existing patterns
        - ALWAYS use the **File: path** format before each code block
        """

        try:
            generated_code = await self.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            logger.info(f"Raw AI response received: {len(generated_code)} characters")
            
            # Extract file paths and code blocks with multiple patterns
            import re
            
            # Pattern 1: **File: path** followed by ```language...```
            file_pattern1 = r'\*\*File:\s*([^*]+)\*\*\s*```(?:\w+)?\s*\n(.*?)\n```'
            matches1 = re.findall(file_pattern1, generated_code, re.DOTALL)
            
            # Pattern 2: **File: path** followed by ```...``` (any language)
            file_pattern2 = r'\*\*File:\s*([^*]+)\*\*\s*```\s*\n(.*?)\n```'
            matches2 = re.findall(file_pattern2, generated_code, re.DOTALL)
            
            # Pattern 3: Look for any markdown code blocks with file hints
            file_pattern3 = r'```(?:\w+)?\s*\n(.*?)\n```'
            code_blocks3 = re.findall(file_pattern3, generated_code, re.DOTALL)
            
            # Combine all matches
            all_matches = matches1 + matches2
            
            code_blocks = {}
            
            # Process structured file matches
            for file_path, code_content in all_matches:
                clean_path = file_path.strip()
                clean_code = code_content.strip()
                
                if clean_path and clean_code:
                    # Remove common file path prefixes if they're too generic
                    if clean_path.startswith('file') or clean_path.startswith('code'):
                        clean_path = f"generated_{len(code_blocks) + 1}.py"
                    code_blocks[clean_path] = clean_code
            
            # If no structured matches, try to extract code blocks and assign generic names
            if not code_blocks and code_blocks3:
                logger.info("No structured file paths found, using generic names")
                for i, code_content in enumerate(code_blocks3):
                    clean_code = code_content.strip()
                    if clean_code and len(clean_code) > 10:  # Only include substantial code
                        # Try to detect language from content
                        if 'def ' in clean_code or 'import ' in clean_code or 'class ' in clean_code:
                            ext = '.py'
                        elif 'function ' in clean_code or 'const ' in clean_code or 'let ' in clean_code:
                            ext = '.js'
                        elif 'public class' in clean_code or 'public static void' in clean_code:
                            ext = '.java'
                        else:
                            ext = '.txt'
                        
                        filename = f"generated_file_{i+1}{ext}"
                        code_blocks[filename] = clean_code
            
            # If still no code blocks, try to extract any code-like content
            if not code_blocks:
                logger.info("Attempting to extract any code-like content")
                # Look for content that looks like code (has common programming patterns)
                lines = generated_code.split('\n')
                code_lines = []
                in_code_block = False
                
                for line in lines:
                    if '```' in line:
                        in_code_block = not in_code_block
                        continue
                    
                    if in_code_block:
                        code_lines.append(line)
                    elif any(pattern in line for pattern in ['def ', 'function ', 'class ', 'import ', 'const ', 'let ', 'public ']):
                        code_lines.append(line)
                
                if code_lines:
                    code_content = '\n'.join(code_lines).strip()
                    if code_content:
                        code_blocks['generated_code.py'] = code_content
            
            logger.info(f"Extracted {len(code_blocks)} code blocks from response")
            
            return {
                'success': True,
                'raw_response': generated_code,
                'code_blocks': code_blocks,
                'files_count': len(code_blocks)
            }
            
        except Exception as e:
            logger.error(f"Error generating code with files: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_response': '',
                'code_blocks': {},
                'files_count': 0
            }

    async def review_code(
        self,
        code: str,
        language: str,
        task_description: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Review code and provide feedback using Perplexity AI.
        
        Args:
            code: The code to review
            language: Programming language of the code
            task_description: Optional description of the task
            
        Returns:
            Dict containing review feedback
        """
        prompt = f"""
        Please review the following {language} code and provide feedback:
        
        Code:
        ```{language}
        {code}
        ```
        
        {"Task: " + task_description if task_description else ""}
        
        Please provide a code review with the following sections:
        1. Code Quality: Overall assessment of code quality
        2. Potential Issues: Any bugs, anti-patterns, or areas for improvement
        3. Security: Any security vulnerabilities
        4. Performance: Potential performance optimizations
        5. Best Practices: Suggestions for following language/framework best practices
        6. Suggested Changes: Specific code changes with explanations
        """

        try:
            response = await self.generate_text(
                prompt=prompt,
                max_tokens=2048,
                temperature=0.3  # Lower temperature for more focused, deterministic output
            )
            
            # Now extract suggested changes
            changes_prompt = f"""
            Based on the following code review, identify specific code changes that should be made.
            
            Review:
            {response}
            
            Please provide a JSON array of changes in this exact format:
            [
                {{
                    "file_path": "path/to/file.ext",
                    "description": "Brief description of the change",
                    "new_content": "The complete new content for the file or section",
                    "change_type": "modify"
                }}
            ]
            
            Only include changes that are clearly actionable and would improve the code.
            If no specific changes are needed, return an empty array [].
            """
            
            try:
                changes_response = await self.generate_text(
                    prompt=changes_prompt,
                    max_tokens=1024,
                    temperature=0.2
                )
                
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\[.*\]', changes_response, re.DOTALL)
                if json_match:
                    import json
                    suggested_changes = json.loads(json_match.group())
                else:
                    suggested_changes = []
                    
            except Exception as json_error:
                logger.warning(f"Failed to parse suggested changes JSON: {json_error}")
                suggested_changes = []
            
            # Parse the response into a structured format
            return {
                'success': True,
                'feedback': response,
                'suggested_changes': suggested_changes,
                'language': language,
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error in review_code: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'feedback': "",
                'suggested_changes': []
            }
