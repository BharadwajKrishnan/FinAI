"""
Chat/LLM API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from auth import get_current_user
from services.llm_service import llm_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    message_id: str


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user)
):
    """
    Handle chat messages and return LLM response
    """
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        
        # Convert conversation history to dict format for LLM service
        history = None
        if request.conversation_history:
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
        
        # System prompt for finance assistant
        system_prompt = (
            "You are a helpful finance assistant with access to real-time web search capabilities. "
            "Help users manage their financial assets including stocks, mutual funds, bank accounts, and fixed deposits. "
            "You can search the web for current information about financial markets, stock prices, and other real-time data. "
            "When users ask about current prices, market data, or recent events, use your web search capability to provide accurate, up-to-date information. "
            "Provide clear, accurate, and helpful responses about financial management."
        )
        
        # Get LLM response
        llm_response = await llm_service.chat(
            message=request.message,
            conversation_history=history,
            system_prompt=system_prompt
        )
        
        return ChatResponse(
            response=llm_response,
            message_id=f"msg_{user_id}_{len(request.message)}"
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Chat endpoint error: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")

