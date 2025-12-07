"""
LLM Service for handling AI chat interactions
Supports multiple LLM providers
"""

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class LLMService:
    """Base LLM service interface"""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        # Set Google API key in environment for google-genai library
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            os.environ["GOOGLE_API_KEY"] = gemini_key
    
    async def _chat_gemini(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str]
    ) -> str:
        """Chat using Google Gemini API with web search capability"""
        try:
            from google import genai
            from google.genai import types
            import asyncio
            
            # Get API key from environment
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return "GEMINI_API_KEY not found in environment variables. Please set it in your .env file."
            
            # Initialize client with API key
            client = genai.Client(api_key=api_key)
            
            # Set up Google Search grounding tool
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )
            
            # Configure with web search capability
            config = types.GenerateContentConfig(
                tools=[grounding_tool]
            )
            
            # Build the prompt - use simple string format for contents
            # For Gemini with tools, we can pass the message directly or build a conversation
            # Using the message directly works better with the grounding tool
            if conversation_history and len(conversation_history) > 0:
                # Build conversation history for context
                prompt_parts = []
                
                # Add system prompt if provided
                if system_prompt:
                    # Only remove backend/server mentions from non-portfolio parts to avoid breaking JSON
                    # Split by <Current_Portfolio> to preserve portfolio JSON
                    if "<Current_Portfolio>" in system_prompt:
                        parts = system_prompt.split("<Current_Portfolio>")
                        if len(parts) == 2:
                            # Clean the first part, keep portfolio section intact
                            cleaned_first = parts[0].replace("backend", "").replace("server", "")
                            prompt_parts.append(cleaned_first + "<Current_Portfolio>" + parts[1])
                        else:
                            prompt_parts.append(system_prompt)
                    else:
                        # No portfolio section, safe to clean
                        simplified_prompt = system_prompt.replace("backend", "").replace("server", "")
                        prompt_parts.append(simplified_prompt)
                
                # Add conversation history (filter out any error messages about backend)
                for msg in conversation_history[-10:]:  # Keep last 10 messages for context
                    # Skip messages that mention backend/server issues to avoid confusion
                    if "backend server" not in msg.get("content", "").lower():
                        role_label = "User" if msg["role"] == "user" else "Assistant"
                        prompt_parts.append(f"{role_label}: {msg['content']}")
                
                # Add current user message
                prompt_parts.append(f"User: {message}")
                
                # Combine all parts
                full_prompt = "\n\n".join(prompt_parts)
            else:
                # For first message, include system prompt if provided
                if system_prompt:
                    # Only remove backend/server mentions from non-portfolio parts
                    if "<Current_Portfolio>" in system_prompt:
                        parts = system_prompt.split("<Current_Portfolio>")
                        if len(parts) == 2:
                            cleaned_first = parts[0].replace("backend", "").replace("server", "")
                            full_prompt = f"{cleaned_first}<Current_Portfolio>{parts[1]}\n\nUser: {message}"
                        else:
                            full_prompt = f"{system_prompt}\n\nUser: {message}"
                    else:
                        simplified_prompt = system_prompt.replace("backend", "").replace("server", "")
                        full_prompt = f"{simplified_prompt}\n\nUser: {message}"
                else:
                    full_prompt = message
            
            # Get model name from environment or use default
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            
            # Run the synchronous Gemini call in a thread pool to avoid blocking async operations
            # Using config with web search capability
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=config,
                )
            )
            
            # Extract text from response (response.text should work based on our test)
            print(f"Gemini API call completed. Response type: {type(response)}")
            print(f"Response has 'text' attribute: {hasattr(response, 'text')}")
            if hasattr(response, 'text'):
                print(f"Response.text value: {response.text if response.text else 'None/Empty'}")
            
            if hasattr(response, 'text') and response.text:
                result_text = response.text
                print(f"Gemini response received (first 200 chars): {result_text[:200]}...")
                
                # Check if response mentions backend/server issues (this shouldn't happen with web search)
                if "backend server" in result_text.lower() or "cannot connect" in result_text.lower():
                    print("WARNING: Response mentions backend/server issues. This might indicate a problem.")
                    print(f"Full response: {result_text}")
                
                return result_text
            elif hasattr(response, 'candidates') and response.candidates:
                print(f"Extracting from candidates. Number of candidates: {len(response.candidates)}")
                # Fallback: extract from candidates
                candidate = response.candidates[0]
                print(f"Candidate type: {type(candidate)}")
                print(f"Candidate has 'content': {hasattr(candidate, 'content')}")
                
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    print(f"Content has 'parts': {hasattr(candidate.content, 'parts')}")
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                    print(f"Extracted {len(text_parts)} text parts")
                    if text_parts:
                        result_text = "".join(text_parts)
                        print(f"Gemini response extracted from candidates (first 200 chars): {result_text[:200]}...")
                        return result_text
                    else:
                        print("No text parts found in candidate content")
                else:
                    print(f"Candidate structure: {dir(candidate)}")
                    if hasattr(candidate, 'content'):
                        print(f"Content structure: {dir(candidate.content)}")
            
            # If we can't extract text, return an error message with more details
            print(f"Error: Could not extract response from Gemini API. Response type: {type(response)}")
            print(f"Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
            if hasattr(response, 'candidates'):
                print(f"Candidates: {response.candidates}")
            if hasattr(response, 'prompt_feedback'):
                print(f"Prompt feedback: {response.prompt_feedback}")
            
            # Try to get any error message from the response
            error_detail = "Unknown error"
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                if hasattr(response.prompt_feedback, 'block_reason'):
                    error_detail = f"Blocked: {response.prompt_feedback.block_reason}"
                elif hasattr(response.prompt_feedback, 'safety_ratings'):
                    error_detail = f"Safety ratings: {response.prompt_feedback.safety_ratings}"
            
            return f"Error: Could not extract response from Gemini API. {error_detail}. Please check the backend logs for more details."
            
        except ImportError:
            return "google-genai package not installed. Please run: pip install google-genai"
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = str(e)
            print(f"Gemini API Error: {error_msg}")
            print(f"Traceback: {error_details}")
            print(f"Model: {model_name}")
            print(f"API Key present: {bool(api_key)}")
            print(f"Prompt length: {len(full_prompt) if 'full_prompt' in locals() else 'N/A'}")
            
            # Check for specific error types
            error_lower = error_msg.lower()
            
            # Handle leaked API key error specifically
            if "leaked" in error_lower or ("403" in error_msg and "permission_denied" in error_lower):
                return "Your Gemini API key has been reported as leaked and is no longer valid. Please generate a new API key from Google AI Studio (https://aistudio.google.com/apikey) and update the GEMINI_API_KEY in your environment variables."
            elif "api key" in error_lower or "authentication" in error_lower or "permission_denied" in error_lower:
                return "I'm having trouble authenticating with the AI service. Please check that your GEMINI_API_KEY is correctly set in your environment variables and is valid."
            elif "quota" in error_lower or "rate limit" in error_lower:
                return "The AI service is currently rate-limited. Please try again in a moment."
            elif "timeout" in error_lower:
                return "The request timed out. Please try again with a shorter question."
            elif "content" in error_lower and "policy" in error_lower:
                return "I cannot process this request due to content policy restrictions. Please rephrase your question."
            else:
                # For debugging, include error type but not full details
                return f"I encountered an error while processing your request: {type(e).__name__}. Please check the backend logs for more details."
    
    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Send a message to the LLM and get a response
        
        Args:
            message: User's message
            conversation_history: Previous messages in the conversation
            system_prompt: System prompt for the LLM
            
        Returns:
            LLM response string
        """
        if self.provider == "gemini":
            return await self._chat_gemini(message, conversation_history, system_prompt)
        elif self.provider == "openai":
            return await self._chat_openai(message, conversation_history, system_prompt)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(message, conversation_history, system_prompt)
        elif self.provider == "ollama":
            return await self._chat_ollama(message, conversation_history, system_prompt)
        else:
            # Default placeholder response
            return await self._chat_placeholder(message, conversation_history, system_prompt)
    
    async def _chat_openai(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str]
    ) -> str:
        """Chat using OpenAI API"""
        try:
            # Uncomment and install openai package: pip install openai
            # from openai import AsyncOpenAI
            
            # client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # messages = []
            # if system_prompt:
            #     messages.append({"role": "system", "content": system_prompt})
            # else:
            #     messages.append({
            #         "role": "system",
            #         "content": "You are a helpful finance assistant. Help users manage their financial assets including stocks, mutual funds, bank accounts, and fixed deposits."
            #     })
            
            # if conversation_history:
            #     messages.extend(conversation_history)
            
            # messages.append({"role": "user", "content": message})
            
            # response = await client.chat.completions.create(
            #     model=os.getenv("OPENAI_MODEL", "gpt-4"),
            #     messages=messages,
            #     temperature=0.7,
            # )
            
            # return response.choices[0].message.content
            
            return "OpenAI integration not configured. Please set OPENAI_API_KEY in your .env file and install the openai package."
        except Exception as e:
            return f"Error with OpenAI: {str(e)}"
    
    async def _chat_anthropic(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str]
    ) -> str:
        """Chat using Anthropic Claude API"""
        try:
            # Uncomment and install anthropic package: pip install anthropic
            # import anthropic
            
            # client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            # system_message = system_prompt or "You are a helpful finance assistant."
            # messages = conversation_history or []
            # messages.append({"role": "user", "content": message})
            
            # response = await client.messages.create(
            #     model=os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
            #     max_tokens=1024,
            #     system=system_message,
            #     messages=messages,
            # )
            
            # return response.content[0].text
            
            return "Anthropic integration not configured. Please set ANTHROPIC_API_KEY in your .env file and install the anthropic package."
        except Exception as e:
            return f"Error with Anthropic: {str(e)}"
    
    async def _chat_ollama(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str]
    ) -> str:
        """Chat using Ollama (local LLM)"""
        try:
            # Uncomment and install ollama package: pip install ollama
            # import ollama
            
            # messages = []
            # if system_prompt:
            #     messages.append({"role": "system", "content": system_prompt})
            
            # if conversation_history:
            #     messages.extend(conversation_history)
            
            # messages.append({"role": "user", "content": message})
            
            # response = await ollama.chat(
            #     model=os.getenv("OLLAMA_MODEL", "llama2"),
            #     messages=messages,
            # )
            
            # return response["message"]["content"]
            
            return "Ollama integration not configured. Please ensure Ollama is running and set OLLAMA_MODEL in your .env file."
        except Exception as e:
            return f"Error with Ollama: {str(e)}"
    
    async def _chat_placeholder(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        system_prompt: Optional[str]
    ) -> str:
        """Placeholder response when no LLM is configured"""
        return f"I understand you said: '{message}'. To enable AI responses, please configure an LLM provider (OpenAI, Anthropic, or Ollama) in your backend settings."


# Global LLM service instance
llm_service = LLMService()

