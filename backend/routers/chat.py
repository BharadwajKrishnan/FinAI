"""
Chat/LLM API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import time
import random
import uuid
from auth import get_current_user
from services.llm_service import llm_service
from database.supabase_client import supabase, supabase_service

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


class ChatHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user)
):
    """
    Handle chat messages and return LLM response
    """
    try:
        # Extract user_id safely (matching pattern from assets router)
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Fetch user's portfolio from database
        portfolio_data = {}
        try:
            print(f"Fetching portfolio for user_id: {user_id}")
            # Fetch all assets (both active and inactive, but prefer active)
            # First try with is_active filter
            response = supabase.table("assets").select("*").eq("user_id", user_id).eq("is_active", True).order("created_at", desc=False).execute()
            assets = response.data if response.data else []
            
            # If no active assets found, try without the filter (in case is_active is not set)
            if len(assets) == 0:
                print(f"No active assets found, trying without is_active filter...")
                response = supabase.table("assets").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
                assets = response.data if response.data else []
            
            print(f"Found {len(assets)} assets for user {user_id}")
            if len(assets) > 0:
                print(f"Sample asset: {json.dumps(assets[0], indent=2, default=str)}")
            
            # Organize assets by market (currency) and then by type
            portfolio_data = {
                "india": {
                    "currency": "INR",
                    "stocks": [],
                    "mutual_funds": [],
                    "bank_accounts": [],
                    "fixed_deposits": []
                },
                "europe": {
                    "currency": "EUR",
                    "stocks": [],
                    "mutual_funds": [],
                    "bank_accounts": [],
                    "fixed_deposits": []
                }
            }
            
            for asset in assets:
                currency = asset.get("currency", "USD")
                # Determine market based on currency
                market = "india" if currency == "INR" else "europe" if currency == "EUR" else "other"
                
                # Skip assets with other currencies (or add to a separate section if needed)
                if market == "other":
                    continue
                
                asset_info = {
                    "id": asset.get("id"),
                    "name": asset.get("name"),
                    "currency": currency,
                    "current_value": float(asset.get("current_value", 0)) if asset.get("current_value") else 0,
                    "created_at": asset.get("created_at"),
                    "updated_at": asset.get("updated_at")
                }
                
                asset_type = asset.get("type")
                if asset_type == "stock":
                    asset_info.update({
                        "symbol": asset.get("stock_symbol"),
                        "quantity": float(asset.get("quantity", 0)) if asset.get("quantity") else 0,
                        "purchase_price": float(asset.get("purchase_price", 0)) if asset.get("purchase_price") else 0,
                        "current_price": float(asset.get("current_price", 0)) if asset.get("current_price") else 0,
                        "purchase_date": asset.get("purchase_date")
                    })
                    portfolio_data[market]["stocks"].append(asset_info)
                elif asset_type == "mutual_fund":
                    asset_info.update({
                        "nav": float(asset.get("nav", 0)) if asset.get("nav") else 0,
                        "units": float(asset.get("units", 0)) if asset.get("units") else 0,
                        "nav_purchase_date": asset.get("nav_purchase_date")
                    })
                    portfolio_data[market]["mutual_funds"].append(asset_info)
                elif asset_type == "bank_account":
                    asset_info.update({
                        "bank_name": asset.get("bank_name"),
                        "account_number": asset.get("account_number"),
                        "account_type": asset.get("account_type"),
                        "balance": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                    })
                    portfolio_data[market]["bank_accounts"].append(asset_info)
                elif asset_type == "fixed_deposit":
                    asset_info.update({
                        "bank_name": asset.get("name"),
                        "principal_amount": float(asset.get("principal_amount", 0)) if asset.get("principal_amount") else 0,
                        "interest_rate": float(asset.get("fd_interest_rate", 0)) if asset.get("fd_interest_rate") else 0,
                        "start_date": asset.get("start_date"),
                        "maturity_date": asset.get("maturity_date"),
                        "maturity_amount": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                    })
                    portfolio_data[market]["fixed_deposits"].append(asset_info)
        except Exception as portfolio_error:
            # If portfolio fetch fails, continue without portfolio data
            import traceback
            print(f"Warning: Could not fetch portfolio data: {str(portfolio_error)}")
            print(f"Traceback: {traceback.format_exc()}")
            portfolio_data = {
                "india": {
                    "currency": "INR",
                    "stocks": [],
                    "mutual_funds": [],
                    "bank_accounts": [],
                    "fixed_deposits": []
                },
                "europe": {
                    "currency": "EUR",
                    "stocks": [],
                    "mutual_funds": [],
                    "bank_accounts": [],
                    "fixed_deposits": []
                }
            }
        
        # Convert portfolio to JSON string
        portfolio_json = json.dumps(portfolio_data, indent=2, default=str)
        print(f"Portfolio JSON length: {len(portfolio_json)} characters")
        print(f"Portfolio summary - India: {len(portfolio_data['india']['stocks'])} stocks, {len(portfolio_data['india']['mutual_funds'])} mutual funds, {len(portfolio_data['india']['bank_accounts'])} bank accounts, {len(portfolio_data['india']['fixed_deposits'])} fixed deposits")
        print(f"Portfolio summary - Europe: {len(portfolio_data['europe']['stocks'])} stocks, {len(portfolio_data['europe']['mutual_funds'])} mutual funds, {len(portfolio_data['europe']['bank_accounts'])} bank accounts, {len(portfolio_data['europe']['fixed_deposits'])} fixed deposits")
        
        # Get current message order (max message_order + 1 for this user)
        try:
            max_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).order("message_order", desc=True).limit(1).execute()
            if max_order_response.data and len(max_order_response.data) > 0:
                current_order = max_order_response.data[0].get("message_order", -1) + 1
            else:
                current_order = 0
        except Exception as e:
            print(f"Warning: Could not get max message order: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            current_order = 0
        
        # Save user message to database
        try:
            user_message_data = {
                "user_id": user_id,
                "role": "user",
                "content": request.message,
                "message_order": current_order
            }
            insert_response = supabase_service.table("chat_messages").insert(user_message_data).execute()
            print(f"Successfully saved user message to database. Message ID: {insert_response.data[0]['id'] if insert_response.data else 'N/A'}")
            current_order += 1
        except Exception as e:
            print(f"ERROR: Could not save user message to database: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Continue even if save fails - don't break the chat flow
        
        # Convert conversation history to dict format for LLM service
        history = None
        if request.conversation_history:
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]
        
        # System prompt for finance assistant with portfolio data
        # Log portfolio data before creating system prompt
        print(f"Creating system prompt with portfolio data...")
        print(f"Portfolio JSON preview (first 500 chars): {portfolio_json[:500]}")
        
        system_prompt = f"""<Role>
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
</Example_Introduction>

<Current_Portfolio>
The user's current portfolio data is provided below in JSON format. Use this data to provide personalized insights and recommendations:

```json
{portfolio_json}
```

The portfolio is organized by market (India/Europe) and then by asset type. Each market has its own currency (INR for India, EUR for Europe).

When analyzing the portfolio:
1. Consider the asset allocation across different types (stocks, mutual funds, bank accounts, fixed deposits) within each market
2. Analyze the distribution across different markets/currencies (INR for India, EUR for Europe)
3. Calculate total portfolio value and breakdown by asset type for each market separately
4. Provide insights on diversification, risk exposure, and potential improvements for each market
5. Reference specific assets by name and market when making recommendations
6. Note that India and Europe markets are separate - assets in one market do not affect the other
</Current_Portfolio>"""
        
        # Get LLM response
        llm_response = await llm_service.chat(
            message=request.message,
            conversation_history=history,
            system_prompt=system_prompt
        )
        
        # Save assistant response to database
        try:
            assistant_message_data = {
                "user_id": user_id,
                "role": "assistant",
                "content": llm_response,
                "message_order": current_order
            }
            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
            print(f"Successfully saved assistant message to database. Message ID: {message_id}")
        except Exception as e:
            print(f"ERROR: Could not save assistant message to database: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
        
        return ChatResponse(
            response=llm_response,
            message_id=message_id
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Chat endpoint error: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    current_user=Depends(get_current_user)
):
    """
    Fetch chat history for the current user
    """
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Fetch chat messages from database, ordered by message_order
        try:
            response = supabase_service.table("chat_messages").select("*").eq("user_id", user_id).order("message_order", desc=False).execute()
            messages = response.data if response.data else []
            print(f"Successfully fetched {len(messages)} chat messages for user {user_id}")
            
            # Format messages for frontend
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "id": msg.get("id"),
                    "role": msg.get("role"),
                    "content": msg.get("content"),
                    "timestamp": msg.get("created_at")
                })
            
            return ChatHistoryResponse(messages=formatted_messages)
        except Exception as e:
            print(f"Error fetching chat history: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Chat history endpoint error: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")


@router.delete("/history", status_code=204)
async def clear_chat_history(
    current_user=Depends(get_current_user)
):
    """
    Clear all chat messages for the current user
    """
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Ensure user_id is a valid UUID string
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID format")
        
        # Delete all chat messages for this user
        try:
            delete_response = supabase_service.table("chat_messages").delete().eq("user_id", user_id).execute()
            print(f"Successfully deleted chat messages for user {user_id}")
        except Exception as e:
            print(f"Error clearing chat history: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Clear chat history endpoint error: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")

