"""
Chat/LLM API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import uuid
import asyncio
from pathlib import Path
from auth import get_current_user, security
from services.llm_service import LLMService
from database.supabase_client import supabase_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize LLM service instance
llm_service = LLMService()

# Get the directory where this file is located
_BACKEND_DIR = Path(__file__).parent.parent
_PROMPTS_DIR = _BACKEND_DIR / "prompts"

# Prompt file paths
ASSETS_PROMPT_FILE = _PROMPTS_DIR / "assets_prompt.txt"
EXPENSES_PROMPT_FILE = _PROMPTS_DIR / "expenses_prompt.txt"


def _load_prompt_template(file_path: Path) -> str:
    """Load a prompt template from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading prompt file {file_path}: {str(e)}")


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = "assets"  # "assets" or "expenses" to determine which system prompt to use
    temperature: Optional[float] = None  # Temperature for LLM (0.0 to 2.0, default depends on provider)
    max_tokens: Optional[int] = None  # Maximum tokens for LLM response (default depends on provider)


class ChatResponse(BaseModel):
    response: str
    message_id: str


class ChatHistoryResponse(BaseModel):
    messages: List[Dict[str, Any]]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
        
        # Get context from request (default to "assets")
        # Handle both None and empty string cases
        context_value = request.context
        if not context_value or context_value == "":
            context = "assets"
        else:
            context = str(context_value).lower().strip()  # Normalize to lowercase and strip whitespace
        
        
        # Fetch user's portfolio from database (only if context is "assets")
        portfolio_data = {}
        if context == "assets":
            try:
                # Fetch family members first
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members = {str(member["id"]): member for member in (family_members_response.data if family_members_response.data else [])}
                
                # Use service role client (bypasses RLS, user already validated via get_current_user)
                # This avoids JWT expiration issues
                # Fetch all assets (similar to assets endpoint - fetch all and filter in Python)
                # This handles NULL is_active values for backward compatibility
                response = supabase_service.table("assets").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
                all_assets = response.data if response.data else []
                
                # Filter by is_active - include assets where is_active is True or NULL (NULL treated as active)
                assets = [a for a in all_assets if a.get("is_active") is True or a.get("is_active") is None]
                
                # Organize assets by market (currency) and then by type
                # Also organize by family member for better context
                portfolio_data = {
                    "india": {
                        "currency": "INR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}  # Will be populated after processing all assets
                    },
                    "europe": {
                        "currency": "EUR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}  # Will be populated after processing all assets
                    }
                }
                
                for asset in assets:
                    currency = asset.get("currency", "USD")
                    # Determine market based on currency
                    market = "india" if currency == "INR" else "europe" if currency == "EUR" else "other"
                    
                    # Skip assets with other currencies (or add to a separate section if needed)
                    if market == "other":
                        continue
                    
                    # Get family member information
                    family_member_id = asset.get("family_member_id")
                    family_member_info = None
                    if family_member_id:
                        member = family_members.get(str(family_member_id))
                        if member:
                            family_member_info = {
                                "id": member.get("id"),
                                "name": member.get("name"),
                                "relationship": member.get("relationship")
                            }
                    
                    asset_info = {
                        "id": asset.get("id"),
                        "name": asset.get("name"),
                        "currency": currency,
                        "current_value": float(asset.get("current_value", 0)) if asset.get("current_value") else 0,
                        "created_at": asset.get("created_at"),
                        "updated_at": asset.get("updated_at"),
                        "family_member": family_member_info if family_member_info else {"name": "Self", "relationship": "Self"}
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
                            "mutual_fund_code": asset.get("mutual_fund_code"),
                            "fund_house": asset.get("fund_house"),
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
                    elif asset_type == "insurance_policy":
                        asset_info.update({
                            "insurance_name": asset.get("name"),
                            "policy_number": asset.get("policy_number"),
                            "amount_insured": float(asset.get("amount_insured", 0)) if asset.get("amount_insured") else 0,
                            "issue_date": asset.get("issue_date"),
                            "date_of_maturity": asset.get("date_of_maturity"),
                            "premium": float(asset.get("premium", 0)) if asset.get("premium") else 0,
                            "nominee": asset.get("nominee"),
                            "premium_payment_date": asset.get("premium_payment_date")
                        })
                        portfolio_data[market]["insurance_policies"].append(asset_info)
                    elif asset_type == "commodity":
                        asset_info.update({
                            "commodity_name": asset.get("commodity_name"),
                            "form": asset.get("form"),
                            "quantity": float(asset.get("commodity_quantity", 0)) if asset.get("commodity_quantity") else 0,
                            "units": asset.get("commodity_units"),
                            "purchase_date": asset.get("commodity_purchase_date"),
                            "purchase_price": float(asset.get("commodity_purchase_price", 0)) if asset.get("commodity_purchase_price") else 0,
                            "current_value": float(asset.get("current_value", 0)) if asset.get("current_value") else 0
                        })
                        portfolio_data[market]["commodities"].append(asset_info)
                
                # Organize assets by family member for better LLM context
                for market in ["india", "europe"]:
                    family_member_assets = {}
                    for asset_type in ["stocks", "mutual_funds", "bank_accounts", "fixed_deposits", "insurance_policies", "commodities"]:
                        for asset in portfolio_data[market][asset_type]:
                            family_member_name = asset.get("family_member", {}).get("name", "Self")
                            if family_member_name not in family_member_assets:
                                family_member_assets[family_member_name] = {
                                    "stocks": [],
                                    "mutual_funds": [],
                                    "bank_accounts": [],
                                    "fixed_deposits": [],
                                    "insurance_policies": [],
                                    "commodities": []
                                }
                            family_member_assets[family_member_name][asset_type].append(asset)
                    portfolio_data[market]["by_family_member"] = family_member_assets
                    
                
                # Add family members list to portfolio_data for system prompt
                portfolio_data["family_members"] = [
                    {"id": str(fm.get("id")), "name": fm.get("name"), "relationship": fm.get("relationship")}
                    for fm in family_members.values()
                ]
            except Exception as portfolio_error:
                # If portfolio fetch fails, continue without portfolio data
                portfolio_data = {
                    "india": {
                        "currency": "INR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}
                    },
                    "europe": {
                        "currency": "EUR",
                        "stocks": [],
                        "mutual_funds": [],
                        "bank_accounts": [],
                        "fixed_deposits": [],
                        "insurance_policies": [],
                        "commodities": [],
                        "by_family_member": {}
                    },
                    "family_members": []
                }
        
        # Fetch user's expenses from database (only if context is "expenses")
        expenses_data = []
        if context == "expenses":
            try:
                # Fetch family members first
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members = {str(member["id"]): member for member in (family_members_response.data if family_members_response.data else [])}
                
                # Use service role client (bypasses RLS, user already validated via get_current_user)
                # This avoids JWT expiration issues
                expenses_response = supabase_service.table("expenses").select("*").eq("user_id", user_id).order("expense_date", desc=True).execute()
                expenses = expenses_response.data if expenses_response.data else []
                
                
                # Limit expenses to most recent 500 to avoid prompt size issues
                # This prevents rate limiting from very large prompts
                max_expenses = 500
                if len(expenses) > max_expenses:
                    expenses = expenses[:max_expenses]
                
                # Format expenses for LLM context
                for expense in expenses:
                    # Get family member information
                    family_member_id = expense.get("family_member_id")
                    family_member_info = None
                    if family_member_id:
                        member = family_members.get(str(family_member_id))
                        if member:
                            family_member_info = {
                                "id": member.get("id"),
                                "name": member.get("name"),
                                "relationship": member.get("relationship")
                            }
                    
                    expense_info = {
                        "id": expense.get("id"),
                        "description": expense.get("description"),
                        "amount": float(expense.get("amount", 0)) if expense.get("amount") else 0,
                        "currency": expense.get("currency", "USD"),
                        "category": expense.get("category"),
                        "expense_date": expense.get("expense_date"),
                        "notes": expense.get("notes"),
                        "created_at": expense.get("created_at"),
                        "family_member": family_member_info if family_member_info else {"name": "Self", "relationship": "Self"}
                    }
                    expenses_data.append(expense_info)
                
                # Group expenses by currency and family member for easier analysis
                expenses_by_currency = {}
                expenses_by_family_member = {}
                for expense in expenses_data:
                    currency = expense.get("currency", "USD")
                    if currency not in expenses_by_currency:
                        expenses_by_currency[currency] = []
                    expenses_by_currency[currency].append(expense)
                    
                    # Group by family member
                    family_member_name = expense.get("family_member", {}).get("name", "Self")
                    if family_member_name not in expenses_by_family_member:
                        expenses_by_family_member[family_member_name] = []
                    expenses_by_family_member[family_member_name].append(expense)
                
                    
            except Exception as expenses_error:
                # If expenses fetch fails, continue without expense data
                expenses_data = []
        
        # Convert portfolio to JSON string (only if context is "assets")
        portfolio_json = ""
        if context == "assets":
            portfolio_json = json.dumps(portfolio_data, indent=2, default=str)
        
        # Convert expenses to JSON string (only if context is "expenses")
        expenses_json = ""
        if context == "expenses":
            # Organize expenses by family member for better LLM context
            expenses_by_family_member = {}
            for expense in expenses_data:
                family_member_name = expense.get("family_member", {}).get("name", "Self")
                if family_member_name not in expenses_by_family_member:
                    expenses_by_family_member[family_member_name] = []
                expenses_by_family_member[family_member_name].append(expense)
            
            expenses_data_with_grouping = {
                "all_expenses": expenses_data,
                "by_family_member": expenses_by_family_member
            }
            
            expenses_json = json.dumps(expenses_data_with_grouping, indent=2, default=str)
        
        # Get current message order (max message_order + 1 for this user and context)
        try:
            max_order_response = supabase_service.table("chat_messages").select("message_order").eq("user_id", user_id).eq("context", context).order("message_order", desc=True).limit(1).execute()
            if max_order_response.data and len(max_order_response.data) > 0:
                max_order = max_order_response.data[0].get("message_order", -1)
                # Safety check: if max_order is too large (timestamp-based), reset to 0
                # PostgreSQL INTEGER max is 2,147,483,647, but timestamps are ~1.7 trillion
                if max_order and max_order > 1000000000:  # If it's a timestamp (milliseconds), reset
                    current_order = 0
                else:
                    current_order = (max_order if max_order is not None else -1) + 1
            else:
                current_order = 0
        except Exception as e:
            current_order = 0
        
        # Save user message to database
        try:
            user_message_data = {
                "user_id": user_id,
                "role": "user",
                "content": request.message,
                "message_order": current_order,
                "context": context  # Store context with message
            }
            insert_response = supabase_service.table("chat_messages").insert(user_message_data).execute()
            current_order += 1
        except Exception as e:
            # Continue even if save fails - don't break the chat flow
            pass
        
        # Create system prompt based on context
        if context == "assets":
            # Load assets prompt template from file
            prompt_template = _load_prompt_template(ASSETS_PROMPT_FILE)
            # Format the template with portfolio data (always fresh from database - fetched on each request)
            system_prompt = prompt_template.format(portfolio_json=portfolio_json)
        
        elif context == "expenses":
            # Load expenses prompt template from file
            prompt_template = _load_prompt_template(EXPENSES_PROMPT_FILE)
            # Format the template with expenses data
            system_prompt = prompt_template.format(expenses_json=expenses_json)
        
        else:
            # Default/fallback prompt
            system_prompt = "You are FinAI, a helpful financial assistant. How can I help you today?"
        
        # Load conversation history from database before calling LLM
        # This ensures we use the database as the source of truth, not in-memory history
        try:
            history_response = supabase_service.table("chat_messages").select("*").eq("user_id", user_id).eq("context", context).order("message_order", desc=False).execute()
            db_messages = history_response.data if history_response.data else []
            
            # Clear LLMService's in-memory history and populate it with database history
            await llm_service.clear_history()
            for msg in db_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Only add messages that aren't the current one we're about to send
                if content != request.message:
                    await llm_service.add_to_history(role, content)
        except Exception as e:
            # If loading history fails, just clear in-memory history to be safe
            await llm_service.clear_history()
        
        # Get LLM response
        # Retry logic for rate limit errors
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        llm_response = None
        
        for attempt in range(max_retries):
            try:
                llm_response = await llm_service.chat(
                    system_prompt=system_prompt,
                    message=request.message,
                    temperature=0.7,
                    max_tokens=10000
                )
                
                # Check if the response is an error message (LLM service returns error strings)
                if llm_response and isinstance(llm_response, str):
                    error_lower = llm_response.lower()
                    is_rate_limit = "rate-limited" in error_lower or "rate limit" in error_lower
                    
                    if is_rate_limit and attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = retry_delay * (2 ** attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    elif is_rate_limit and attempt == max_retries - 1:
                        # Max retries reached, return the error message
                        break
                
                # Success or non-rate-limit error, exit retry loop
                break
                
            except Exception as llm_error:
                error_msg = str(llm_error)
                error_lower = error_msg.lower()
                
                # Check if it's a rate limit error
                is_rate_limit = "quota" in error_lower or "rate limit" in error_lower or "429" in error_msg
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = retry_delay * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Not a rate limit error, or max retries reached
                    # Re-raise to let the LLM service handle it
                    raise
        
        if llm_response is None:
            raise HTTPException(status_code=500, detail="Failed to get LLM response after retries")
        
        # Save assistant response to database
        try:
            assistant_message_data = {
                "user_id": user_id,
                "role": "assistant",
                "content": llm_response,
                "message_order": current_order,
                "context": context  # Store context with message
            }
            insert_response = supabase_service.table("chat_messages").insert(assistant_message_data).execute()
            message_id = insert_response.data[0]["id"] if insert_response.data else f"msg_{user_id}_{uuid.uuid4().hex}"
        except Exception as e:
            message_id = f"msg_{user_id}_{uuid.uuid4().hex}"
        
        return ChatResponse(
            response=llm_response,
            message_id=message_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    context: Optional[str] = Query("assets", description="Context filter: 'assets' or 'expenses'"),
    current_user=Depends(get_current_user)
):
    """
    Fetch chat history for the current user, filtered by context
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
        
        # Normalize context
        if not context or context == "":
            context = "assets"
        else:
            context = str(context).lower().strip()
        
        
        # Fetch chat messages from database, filtered by context and ordered by message_order
        try:
            response = supabase_service.table("chat_messages").select("*").eq("user_id", user_id).eq("context", context).order("message_order", desc=False).execute()
            messages = response.data if response.data else []
            
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
            raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chat history: {str(e)}")


@router.delete("/history", status_code=204)
async def clear_chat_history(
    context: Optional[str] = Query("assets", description="Context filter: 'assets' or 'expenses'"),
    current_user=Depends(get_current_user)
):
    """
    Clear chat messages for the current user, filtered by context
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
        
        # Normalize context
        if not context or context == "":
            context = "assets"
        else:
            context = str(context).lower().strip()
        
        
        # Delete chat messages for this user and context
        try:
            delete_response = supabase_service.table("chat_messages").delete().eq("user_id", user_id).eq("context", context).execute()
            
            # Clear the in-memory conversation history in LLMService
            # This ensures that old messages are not sent to the LLM after clearing
            await llm_service.clear_history()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
