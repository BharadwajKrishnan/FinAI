# LLM Integration Setup Guide

The chat functionality is now handled in the backend. You can integrate with various LLM providers.

## Supported LLM Providers

1. **OpenAI** (GPT-4, GPT-3.5, etc.)
2. **Anthropic** (Claude models)
3. **Ollama** (Local LLM models)

## Setup Instructions

### Option 1: OpenAI

1. **Install the package:**
   ```bash
   pip install openai
   ```

2. **Add to your `.env` file:**
   ```bash
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4  # or gpt-3.5-turbo
   ```

3. **Uncomment the OpenAI code in `backend/services/llm_service.py`**
   - Find the `_chat_openai` method
   - Uncomment the OpenAI integration code

### Option 2: Anthropic (Claude)

1. **Install the package:**
   ```bash
   pip install anthropic
   ```

2. **Add to your `.env` file:**
   ```bash
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ANTHROPIC_MODEL=claude-3-sonnet-20240229
   ```

3. **Uncomment the Anthropic code in `backend/services/llm_service.py`**
   - Find the `_chat_anthropic` method
   - Uncomment the Anthropic integration code

### Option 3: Ollama (Local LLM)

1. **Install Ollama:**
   - Download from: https://ollama.ai
   - Install and start Ollama service

2. **Install the Python package:**
   ```bash
   pip install ollama
   ```

3. **Add to your `.env` file:**
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama2  # or any model you have installed
   ```

4. **Uncomment the Ollama code in `backend/services/llm_service.py`**
   - Find the `_chat_ollama` method
   - Uncomment the Ollama integration code

## Current Status

By default, the system uses a placeholder response. To enable real LLM responses:

1. Choose your LLM provider
2. Install the required package
3. Add API keys to `.env`
4. Uncomment the relevant code in `llm_service.py`
5. Restart your backend server

## Testing

Once configured, test the chat by:

1. Starting the backend: `python main.py`
2. Logging in to the frontend
3. Going to `/assets` page
4. Sending a message in the chat window

The message will be sent to your configured LLM provider and you'll get a real AI response.

## API Endpoint

The chat endpoint is available at:
```
POST http://localhost:8000/api/chat/
```

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "What are my total assets?",
  "conversation_history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi! How can I help?"}
  ]
}
```

**Response:**
```json
{
  "response": "Based on your portfolio...",
  "message_id": "msg_123_45"
}
```

