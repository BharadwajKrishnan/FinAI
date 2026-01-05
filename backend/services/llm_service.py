"""
LLM Service for handling AI chat interactions using Google Gemini
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

load_dotenv()


class LLMService:
    """LLM service for Google Gemini"""
    
    def __init__(self):
        """
        Initialize the LLMService instance for Google Gemini chat interactions.
        
        This constructor sets up:
            - The conversation history used to keep track of chat exchanges.
            - The system prompt, which can be changed between calls to provide different context or instructions to the LLM.
            - An asyncio-compatible lock for thread-safe use of conversation history when running in async environments.
            - The necessary environment variables (API key and model name) for accessing Google Gemini, with sensible defaults.
            - A Grounding Tool to enable web search grounding for LLM responses (static across calls).
            - A reusable client object for all Gemini API interactions.
        """
        # List to store conversation history as a sequence of role-content dicts.
        self.conversation_history: List[Dict[str, str]] = []
        
        # Current system prompt (settable between conversations).
        self.system_prompt: str = ""
        
        # Lock to ensure async thread safety when accessing/modifying conversation history.
        self._history_lock = asyncio.Lock()
        
        # Get Gemini API Key and model name from environment variables.
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Set up static Google Search grounding tool for enhanced LLM capabilities.
        if types is not None:
            try:
                self.grounding_tool = types.Tool(google_search=types.GoogleSearch())
            except Exception as e:
                self.grounding_tool = None
        else:
            self.grounding_tool = None
        
        # Instantiate Gemini client instance for API calls (reusable between requests).
        self.client = genai.Client(api_key=self.api_key)
    
    async def chat(
        self,
        system_prompt: str,
        message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        Send system prompt and user message to Google Gemini and get a response
        
        Args:
            system_prompt: System prompt for the LLM (required)
            message: User's message/prompt (required)
            temperature: Temperature for LLM (0.0 to 2.0, default: 0.7)
            max_tokens: Maximum tokens for LLM response (default: 4096)
            
        Returns:
            LLM response string
        """
        try:
            # Build tools list with Google Search only
            tools_list = []
            
            # Add Google Search tool if available
            if self.grounding_tool is not None:
                tools_list.append(self.grounding_tool)
            
            # Build configuration with default parameters and tools
            if tools_list:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    tools=tools_list)
            else:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens)
            
            # Thread-safe access to conversation history
            async with self._history_lock:
                # Update system prompt if provided
                if system_prompt:
                    self.system_prompt = system_prompt
                
                # Build conversation history list for Gemini API within the function
                contents: List[Dict] = []
                
                # Always include system prompt as first message
                if self.system_prompt:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": self.system_prompt}]})
                
                # Add previous conversation history
                for msg in self.conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    
                    # Convert role to Gemini format (assistant -> model, user -> user)
                    gemini_role = "model" if role == "assistant" else "user"
                    
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": content}]})
                
                # Add current user message to contents (not to history yet)
                contents.append({
                    "role": "user",
                    "parts": [{"text": message}]})
            
            # Run the synchronous Gemini call in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config))
            
            # Extract text from response
            response_text = None
            
            # Try direct text attribute first
            if hasattr(response, 'text') and response.text:
                response_text = response.text
            
            # If no direct text, try extracting from candidates
            if not response_text and hasattr(response, 'candidates') and response.candidates:
                if len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if candidate:
                        # Try to get content from candidate
                        content = None
                        if hasattr(candidate, 'content'):
                            content = candidate.content
                        elif hasattr(candidate, 'parts'):
                            # Some response formats have parts directly on candidate
                            content = type('obj', (object,), {'parts': candidate.parts})()
                        
                        if content:
                            # Get parts from content
                            parts = None
                            if hasattr(content, 'parts'):
                                parts = content.parts
                            elif hasattr(content, '__iter__'):
                                # Content might be iterable directly
                                parts = content
                            
                            if parts is not None:
                                text_parts = []
                                try:
                                    for part in parts:
                                        if part is None:
                                            continue
                                        # Extract text content
                                        if hasattr(part, 'text') and part.text:
                                            text_parts.append(str(part.text))
                                    if text_parts:
                                        response_text = "".join(text_parts)
                                except Exception as extract_error:
                                    # Try to get any string representation
                                    try:
                                        response_text = str(response)
                                    except:
                                        pass
            
            # Only add to conversation history if we got a successful response
            if response_text:
                async with self._history_lock:
                    # Add user message and assistant response together
                    self.conversation_history.append({
                        "role": "user",
                        "content": message})
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": response_text})
                
                return response_text
            
            return "Error: Could not extract response from Gemini API."
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def clear_history(self):
        """
        Clear the conversation history in memory.
        This should be called when the user clears their chat history in the database.
        """
        async with self._history_lock:
            self.conversation_history = []
            self.system_prompt = ""
    
    async def add_to_history(self, role: str, content: str):
        """
        Add a message to conversation history.
        Used to populate history from database.
        """
        async with self._history_lock:
            self.conversation_history.append({
                "role": role,
                "content": content
            })
    
    def _extract_text_from_response(self, response) -> Optional[str]:
        """
        Extract text from Gemini API response.
        This is a helper method used internally by chat() and generate_json().
        
        Args:
            response: Gemini API response object
        
        Returns:
            Extracted text string, or None if extraction fails
        """
        response_text = None
        
        # Try direct text attribute first
        if hasattr(response, 'text') and response.text:
            response_text = response.text
        
        # If no direct text, try extracting from candidates
        if not response_text and hasattr(response, 'candidates') and response.candidates:
            if len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate:
                    # Try to get content from candidate
                    content = None
                    if hasattr(candidate, 'content'):
                        content = candidate.content
                    elif hasattr(candidate, 'parts'):
                        # Some response formats have parts directly on candidate
                        content = type('obj', (object,), {'parts': candidate.parts})()
                    
                    if content:
                        # Get parts from content
                        parts = None
                        if hasattr(content, 'parts'):
                            parts = content.parts
                        elif hasattr(content, '__iter__'):
                            # Content might be iterable directly
                            parts = content
                        
                        if parts is not None:
                            text_parts = []
                            try:
                                for part in parts:
                                    if part is None:
                                        continue
                                    # Extract text content
                                    if hasattr(part, 'text') and part.text:
                                        text_parts.append(str(part.text))
                                if text_parts:
                                    response_text = "".join(text_parts)
                            except Exception as extract_error:
                                # Try to get any string representation
                                try:
                                    response_text = str(response)
                                except:
                                    pass
        
        return response_text
    
    async def generate_json(
        self,
        contents: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """
        Generate JSON response from Gemini API using JSON mode.
        This method does not use conversation history - it's for one-off JSON generation.
        
        Args:
            contents: List of message dictionaries in Gemini format
            temperature: Temperature for LLM (0.0 to 2.0, default: 0.7)
            max_tokens: Maximum tokens for LLM response (default: 4096)
        
        Returns:
            Extracted text response (JSON string), or None if generation fails
        """
        try:
            # Build configuration with JSON mode
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                max_output_tokens=max_tokens
            )
            
            # Run the synchronous Gemini call in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config))
            
            # Extract text from response
            return self._extract_text_from_response(response)
            
        except Exception as e:
            return None

