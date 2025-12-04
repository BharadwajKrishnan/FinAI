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
                
                # Add system prompt if provided (but keep it concise to avoid confusion)
                if system_prompt:
                    # Simplify system prompt to avoid mentioning backend/server
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
                    # Simplify system prompt
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
            if hasattr(response, 'text') and response.text:
                result_text = response.text
                print(f"Gemini response received (first 200 chars): {result_text[:200]}...")
                
                # Check if response mentions backend/server issues (this shouldn't happen with web search)
                if "backend server" in result_text.lower() or "cannot connect" in result_text.lower():
                    print("WARNING: Response mentions backend/server issues. This might indicate a problem.")
                    print(f"Full response: {result_text}")
                
                return result_text
            elif hasattr(response, 'candidates') and response.candidates:
                # Fallback: extract from candidates
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                    if text_parts:
                        result_text = "".join(text_parts)
                        print(f"Gemini response extracted from candidates (first 200 chars): {result_text[:200]}...")
                        return result_text
            
            # If we can't extract text, return an error message
            print(f"Error: Could not extract response from Gemini API. Response type: {type(response)}")
            print(f"Response attributes: {dir(response)}")
            if hasattr(response, 'candidates'):
                print(f"Candidates: {response.candidates}")
            return f"Error: Could not extract response from Gemini API. Response type: {type(response)}"
            
        except ImportError:
            return "google-genai package not installed. Please run: pip install google-genai"
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Gemini API Error: {str(e)}")
            print(f"Traceback: {error_details}")
            # Don't return error messages that might confuse the user
            # Instead, return a helpful message
            return f"I encountered an error while processing your request. Please try again or rephrase your question."
    
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

