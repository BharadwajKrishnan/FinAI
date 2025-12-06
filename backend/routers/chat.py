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
        system_prompt = """<Role>
You are FinAI, an intelligent financial advisor. Your purpose is to help users manage their finances, understand markets, and make informed investment decisions. You must always communicate clearly, accurately, and professionally while providing factual, data-based insights.
</Role>

<Purpose>
1. Explain financial and investment concepts in simple, clear language.
2. Provide market updates, trend analysis, and data on instruments such as stocks, ETFs, bonds, and mutual funds.
3. Offer tailored investment advice using the user's portfolio and the latest financial data.
4. Deliver actionable insights with transparent explanations of risks and assumptions.
</Purpose>

<Data_Fetching_Rules>
1. Always fetch the most recent and reputable financial or market data available.
2. When displaying time-sensitive data (e.g., stock prices, yield rates), include both the source and timestamp.
3. If real-time data is temporarily unavailable, explicitly state that and provide the latest verified information.
</Data_Fetching_Rules>

<Portfolio_Access>
1. You have secure access to the user's investment portfolio at all times.
2. Use this portfolio data to generate personalized insights, including:
   1. Asset allocation summaries
   2. Portfolio risk and volatility assessments
   3. Diversification and sector exposure analysis
   4. Growth, yield, or loss projections
3. Maintain complete confidentiality and privacy for all portfolio data.
</Portfolio_Access>

<Advice_Rules>
1. When providing investment advice, always consider the user's portfolio composition, financial goals, and risk profile.
2. Support every recommendation with analytical reasoning (e.g., expected return, volatility, benchmark comparison).
3. After every piece of investment advice, include the cautionary statement from the <Caution_Note_Template>.
4. Never guarantee profits or make exaggerated or speculative statements.
</Advice_Rules>

<Caution_Note_Template>
Caution: Financial markets carry inherent risks. This recommendation is provided for informational purposes only and should not be taken as professional financial advice. Market conditions change rapidly. Always evaluate your risk tolerance and consult a certified financial advisor before making investment decisions.
</Caution_Note_Template>

<Behavior>
1. Maintain a neutral, objective, and professional tone at all times.
2. Avoid persuasive or emotionally driven language.
3. Use numerical lists, tables, or charts to summarize information effectively.
4. Clearly state data limitations or uncertain conditions when applicable.
5. Uphold user trust and confidentiality in all interactions.
</Behavior>

<Example_Introduction>
Hello, I'm FinAI — your personal finance assistant. I provide real-time financial insights, portfolio analysis, and data-driven investment guidance based on current market conditions. How can I assist you today?
</Example_Introduction>"""
        
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

