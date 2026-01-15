"""
Assets API endpoints
"""

# Standard library imports
import asyncio
import io
import json
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Third-party imports
import pdfplumber
import PyPDF2
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials
from PyPDF2 import PdfWriter

# Local application imports
from auth import get_current_user, security
from database.supabase_client import supabase, supabase_service
from models import Asset, AssetCreate, AssetUpdate, AssetType
from services.llm_service import LLMService
from services.stock_price_service import stock_price_service

router = APIRouter(prefix="/api/assets", tags=["assets"])

# Initialize separate LLMService instances for each asset type
_fixed_deposit_llm_service = LLMService()
_stock_llm_service = LLMService()
_bank_account_llm_service = LLMService()
_mutual_fund_llm_service = LLMService()


def load_prompt(prompt_filename: str) -> str:
    """Load a prompt from the prompts directory"""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompt_path = prompts_dir / prompt_filename
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"Prompt file not found: {prompt_filename}"
        )


def build_contents_list(instruction_prompt: str, previous_contexts: List, page_content: str, page_idx: int, asset_type: str) -> List[Dict]:
    """
    Build contents list for Gemini API call, following llm_service.py pattern.
    
    Args:
        instruction_prompt: The system/instruction prompt
        previous_contexts: List of (input, output) tuples from previous pages
        page_content: Current page content
        page_idx: Current page index (0-based)
        asset_type: Type of asset being processed (for context in messages)
    
    Returns:
        List of message dictionaries in Gemini format
    """
    contents = []
    
    # Map asset type to label for messages
    asset_type_label = {
        "fixed_deposit": "fixed deposits",
        "stock": "stock/equity",
        "bank_account": "bank accounts",
        "mutual_fund": "mutual funds"
    }.get(asset_type, "assets")
    
    # Add instruction as first user message
    contents.append({
        "role": "user",
        "parts": [{"text": instruction_prompt}]
    })
    
    # Add previous context as conversation history (user-assistant pairs)
    if page_idx > 0 and previous_contexts:
        for prev_idx, (prev_input, prev_output) in enumerate(previous_contexts):
            # Add previous user message (page content)
            contents.append({
                "role": "user",
                "parts": [{"text": f"Here is a summary of all the {asset_type_label} from page {prev_idx + 1}:\n\n{prev_input}"}]
            })
            # Add previous assistant response (LLM output)
            contents.append({
                "role": "model",
                "parts": [{"text": prev_output}]
            })
    
    # Add current page as user message
    contents.append({
        "role": "user",
        "parts": [{"text": f"Here is a summary of all the {asset_type_label} from page {page_idx + 1}:\n\n{page_content}"}]
    })
    
    return contents




def clean_json_response(text_response: str) -> str:
    """
    Clean JSON response by removing markdown code blocks.
    
    Args:
        text_response: Raw text response from LLM
    
    Returns:
        Cleaned JSON string
    """
    import re
    cleaned_response = text_response.strip()
    
    # Remove opening markdown code block (handle both ```json and ```)
    # Use regex to handle multiple occurrences and variations
    cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.MULTILINE)
    
    # Remove closing markdown code block (handle multiple occurrences)
    cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response, flags=re.MULTILINE)
    
    # Remove any remaining ``` blocks in the middle (shouldn't happen, but just in case)
    cleaned_response = re.sub(r'```(?:json)?', '', cleaned_response)
    
    cleaned_response = cleaned_response.strip()
    return cleaned_response


def clean_and_parse_json_response(text_response: str) -> tuple[List[Dict], str]:
    """
    Clean JSON response and parse it, handling markdown code blocks.
    
    Args:
        text_response: Raw text response from LLM
    
    Returns:
        Tuple of (parsed JSON as a list of dictionaries, cleaned response string)
    """
    cleaned_response = clean_json_response(text_response)
    
    parsed_data = json.loads(cleaned_response)
    # Handle both single object and array
    if not isinstance(parsed_data, list):
        parsed_data = [parsed_data]
    
    return parsed_data, cleaned_response


@router.get("/", response_model=List[Asset])
async def get_assets(
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user=Depends(get_current_user)
):
    """Get all assets for the current user with optional filters"""
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
        
        # Use service role client (bypasses RLS, user already validated via get_current_user)
        # This avoids JWT expiration issues
        supabase_client = supabase_service
        query = supabase_client.table("assets").select("*").eq("user_id", user_id)
        
        if asset_type:
            query = query.eq("type", asset_type.value)
        if is_active is not None:
            query = query.eq("is_active", is_active)
        else:
            # Default to only active assets if not specified
            # For backward compatibility, also include assets where is_active is NULL
            # We'll filter in Python to handle NULL values
            pass  # Don't filter by is_active - we'll handle NULL in Python
        
        query = query.order("created_at", desc=True)
        
        response = query.execute()
        all_assets = response.data if response.data else []
        
        # Filter by is_active if not explicitly specified
        # Include assets where is_active is True or NULL (NULL treated as active for backward compatibility)
        if is_active is None:
            assets = [a for a in all_assets if a.get("is_active") is True or a.get("is_active") is None]
        else:
            assets = all_assets
        
        return assets
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching assets: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch assets: {str(e)}")


@router.post("/")
async def create_asset(
    asset: AssetCreate, 
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new asset"""
    try:
        # Get user's access token for RLS
        access_token = credentials.credentials
        
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Convert Pydantic model to dict, handling Decimal serialization
        try:
            asset_data = asset.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        except AttributeError:
            # Fallback for older Pydantic versions
            asset_data = asset.dict(exclude_unset=True, exclude_none=True)
        
        asset_data["user_id"] = user_id
        
        # Ensure is_active is set to True by default if not provided
        if "is_active" not in asset_data:
            asset_data["is_active"] = True
        
        # Convert date objects to strings for Supabase
        date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date', 
                       'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
        for field in date_fields:
            if field in asset_data and asset_data[field]:
                asset_data[field] = asset_data[field].isoformat() if hasattr(asset_data[field], 'isoformat') else asset_data[field]
        
        # Convert Decimal to string for Supabase
        decimal_fields = [
            'current_value', 'quantity', 'purchase_price', 'current_price',
            'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
            'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price'
        ]
        for field in decimal_fields:
            if field in asset_data and asset_data[field] is not None:
                asset_data[field] = str(asset_data[field])
        
        # Check for duplicate bank accounts before inserting
        duplicate_message = None
        if asset_data.get("type") == "bank_account":
            account_number = asset_data.get("account_number")
            bank_name = asset_data.get("bank_name")
            
            if account_number:
                # Normalize account number for comparison (case-insensitive, strip whitespace)
                normalized_account_number = str(account_number).strip().lower()
                
                # Check if account number already exists in database
                try:
                    # Fetch all bank accounts (including NULL is_active for backward compatibility)
                    existing_response = supabase_service.table("assets").select("id, account_number, bank_name, is_active").eq("user_id", user_id).eq("type", "bank_account").execute()
                    all_existing_accounts = existing_response.data if existing_response.data else []
                    # Filter to only active accounts (is_active = True or NULL)
                    existing_accounts = [acc for acc in all_existing_accounts if acc.get("is_active") is True or acc.get("is_active") is None]
                    
                    for existing_account in existing_accounts:
                        existing_account_num = existing_account.get("account_number")
                        if existing_account_num:
                            existing_normalized = str(existing_account_num).strip().lower()
                            if normalized_account_number == existing_normalized:
                                # Fetch the complete existing asset from database
                                existing_asset_id = existing_account.get("id")
                                if existing_asset_id:
                                    full_asset_response = supabase_service.table("assets").select("*").eq("id", existing_asset_id).execute()
                                    if full_asset_response.data and len(full_asset_response.data) > 0:
                                        existing_asset = full_asset_response.data[0]
                                        existing_bank_name = existing_asset.get("bank_name", "")
                                        duplicate_message = f"Bank account with account number '{account_number}' was not added because it already exists in your portfolio. Bank: {existing_bank_name or 'Unknown'}"
                                        # Add message and duplicate flag to the response
                                        existing_asset["message"] = duplicate_message
                                        existing_asset["duplicate"] = True
                                        logger = logging.getLogger(__name__)
                                        logger.info(f"Duplicate bank account detected: {account_number}. Returning existing asset with message.")
                                        return existing_asset
                except Exception as check_error:
                    # Log error but continue - don't block creation if check fails
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error checking for duplicate bank account: {str(check_error)}")
        
        elif asset_data.get("type") == "fixed_deposit":
            bank_name = asset_data.get("name")  # Fixed deposit uses "name" field for bank name
            principal_amount = asset_data.get("principal_amount")
            
            if bank_name and principal_amount:
                # Normalize for comparison (case-insensitive, strip whitespace)
                normalized_bank_name = str(bank_name).strip().lower()
                normalized_amount = str(principal_amount).strip().lower()
                
                # Check if fixed deposit already exists in database (same bank name and principal amount)
                try:
                    # Fetch all fixed deposits (including NULL is_active for backward compatibility)
                    existing_response = supabase_service.table("assets").select("id, name, principal_amount, is_active").eq("user_id", user_id).eq("type", "fixed_deposit").execute()
                    all_existing_fds = existing_response.data if existing_response.data else []
                    # Filter to only active fixed deposits (is_active = True or NULL)
                    existing_fds = [fd for fd in all_existing_fds if fd.get("is_active") is True or fd.get("is_active") is None]
                    
                    for existing_fd in existing_fds:
                        existing_bank_name = existing_fd.get("name", "")
                        existing_amount = existing_fd.get("principal_amount", "")
                        if existing_bank_name and existing_amount:
                            existing_normalized_name = str(existing_bank_name).strip().lower()
                            existing_normalized_amount = str(existing_amount).strip().lower()
                            if normalized_bank_name == existing_normalized_name and normalized_amount == existing_normalized_amount:
                                # Fetch the complete existing asset from database
                                existing_asset_id = existing_fd.get("id")
                                if existing_asset_id:
                                    full_asset_response = supabase_service.table("assets").select("*").eq("id", existing_asset_id).execute()
                                    if full_asset_response.data and len(full_asset_response.data) > 0:
                                        existing_asset = full_asset_response.data[0]
                                        duplicate_message = f"Fixed deposit with bank name '{bank_name}' and amount '{principal_amount}' was not added because it already exists in your portfolio."
                                        # Add message and duplicate flag to the response
                                        existing_asset["message"] = duplicate_message
                                        existing_asset["duplicate"] = True
                                        logger = logging.getLogger(__name__)
                                        logger.info(f"Duplicate fixed deposit detected: {bank_name}, Amount: {principal_amount}. Returning existing asset with message.")
                                        return existing_asset
                except Exception as check_error:
                    # Log error but continue - don't block creation if check fails
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error checking for duplicate fixed deposit: {str(check_error)}")
        
        elif asset_data.get("type") == "stock":
            stock_symbol = asset_data.get("stock_symbol")
            stock_name = asset_data.get("name")
            purchase_date = asset_data.get("purchase_date")
            
            # Check if stock already exists in database by symbol/name (regardless of purchase date)
            if stock_symbol or stock_name:
                # Normalize for comparison (case-insensitive, strip whitespace)
                normalized_symbol = str(stock_symbol).strip().lower() if stock_symbol else ""
                normalized_name = str(stock_name).strip().lower() if stock_name else ""
                check_symbol = normalized_symbol if normalized_symbol else normalized_name
                
                try:
                    # Fetch all stocks (including NULL is_active for backward compatibility)
                    existing_response = supabase_service.table("assets").select("id, stock_symbol, name, purchase_date, is_active").eq("user_id", user_id).eq("type", "stock").execute()
                    all_existing_stocks = existing_response.data if existing_response.data else []
                    # Filter to only active stocks (is_active = True or NULL)
                    existing_stocks = [s for s in all_existing_stocks if s.get("is_active") is True or s.get("is_active") is None]
                    
                    for existing_stock in existing_stocks:
                        existing_symbol = str(existing_stock.get("stock_symbol", "")).strip().lower()
                        existing_name = str(existing_stock.get("name", "")).strip().lower()
                        existing_date = existing_stock.get("purchase_date", "")
                        
                        # Check if stock with same symbol/name already exists (regardless of purchase date)
                        existing_check_symbol = existing_symbol if existing_symbol else existing_name
                        if check_symbol and existing_check_symbol and check_symbol == existing_check_symbol:
                            # Fetch the complete existing asset from database
                            existing_asset_id = existing_stock.get("id")
                            if existing_asset_id:
                                full_asset_response = supabase_service.table("assets").select("*").eq("id", existing_asset_id).execute()
                                if full_asset_response.data and len(full_asset_response.data) > 0:
                                    existing_asset = full_asset_response.data[0]
                                    duplicate_message = f"Stock '{stock_symbol or stock_name}' was not added because it already exists in your portfolio."
                                    # Add message and duplicate flag to the response
                                    existing_asset["message"] = duplicate_message
                                    existing_asset["duplicate"] = True
                                    logger = logging.getLogger(__name__)
                                    logger.info(f"Duplicate stock detected: {stock_symbol or stock_name}. Returning existing asset with message.")
                                    return existing_asset
                        
                        # Also check by symbol + purchase date for backward compatibility
                        if stock_symbol and purchase_date and existing_symbol and existing_date:
                            normalized_date = str(purchase_date).strip().lower()
                            existing_normalized_date = str(existing_date).strip().lower()
                            if normalized_symbol == existing_symbol and normalized_date == existing_normalized_date:
                                # Fetch the complete existing asset from database
                                existing_asset_id = existing_stock.get("id")
                                if existing_asset_id:
                                    full_asset_response = supabase_service.table("assets").select("*").eq("id", existing_asset_id).execute()
                                    if full_asset_response.data and len(full_asset_response.data) > 0:
                                        existing_asset = full_asset_response.data[0]
                                        duplicate_message = f"Stock with symbol '{stock_symbol}' and purchase date '{purchase_date}' was not added because it already exists in your portfolio."
                                        # Add message and duplicate flag to the response
                                        existing_asset["message"] = duplicate_message
                                        existing_asset["duplicate"] = True
                                        logger = logging.getLogger(__name__)
                                        logger.info(f"Duplicate stock detected: {stock_symbol}, Purchase Date: {purchase_date}. Returning existing asset with message.")
                                        return existing_asset
                except Exception as check_error:
                    # Log error but continue - don't block creation if check fails
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error checking for duplicate stock: {str(check_error)}")
        
        # Use service role client for backend operations
        # We've already validated the user via JWT and set user_id correctly
        # Service role bypasses RLS, but we're enforcing security at the application level
        try:
            response = supabase_service.table("assets").insert(asset_data).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                # RLS is blocking - this means service role key is not set or not working
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file. "
                           "Get it from Supabase Dashboard -> Settings -> API -> service_role key (secret). "
                           "This key bypasses RLS for backend operations."
                )
            raise
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create asset")
        
        created_asset = response.data[0]
        return created_asset
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create asset: {str(e)}")


@router.get("/{asset_id}", response_model=Asset)
async def get_asset(asset_id: str, current_user=Depends(get_current_user)):
    """Get a specific asset"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        response = supabase.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Asset not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching asset {asset_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch asset: {str(e)}")


@router.put("/{asset_id}", response_model=Asset)
async def update_asset(asset_id: str, asset: AssetUpdate, current_user=Depends(get_current_user)):
    """Update an asset"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Convert Pydantic model to dict
        try:
            update_data = asset.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        except AttributeError:
            # Fallback for older Pydantic versions
            update_data = asset.dict(exclude_unset=True, exclude_none=True)
        
        # Handle family_member_id explicitly - it needs to be included even if None
        # Check if family_member_id was set in the request (even if None)
        try:
            # Get all fields including None values to check if family_member_id was set
            all_data = asset.model_dump(exclude_unset=True, mode='json')
        except AttributeError:
            all_data = asset.dict(exclude_unset=True)
        
        if "family_member_id" in all_data:
            # family_member_id was explicitly set in the request, include it in update
            if all_data["family_member_id"] is None:
                update_data["family_member_id"] = None
            else:
                update_data["family_member_id"] = str(all_data["family_member_id"])
        
        # Convert date objects to strings
        date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date',
                       'issue_date', 'date_of_maturity', 'premium_payment_date', 'commodity_purchase_date']
        for field in date_fields:
            if field in update_data and update_data[field]:
                update_data[field] = update_data[field].isoformat() if hasattr(update_data[field], 'isoformat') else update_data[field]
        
        # Convert Decimal to string
        decimal_fields = [
            'current_value', 'quantity', 'purchase_price', 'current_price',
            'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate',
            'amount_insured', 'premium', 'commodity_quantity', 'commodity_purchase_price'
        ]
        for field in decimal_fields:
            if field in update_data and update_data[field] is not None:
                update_data[field] = str(update_data[field])
        
        # Use service role client (bypasses RLS, user already validated via get_current_user)
        # We've already validated the user via JWT and set user_id correctly
        # Service role bypasses RLS, but we're enforcing security at the application level
        try:
            response = supabase_service.table("assets").update(update_data).eq("id", asset_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                # RLS is blocking - this means service role key is not set or not working
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file."
                )
            raise
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Asset not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update asset: {str(e)}")


@router.delete("/{asset_id}")
async def delete_asset(asset_id: str, current_user=Depends(get_current_user)):
    """Delete an asset"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Use service role client for backend operations
        # We've already validated the user via JWT and set user_id correctly
        # Service role bypasses RLS, but we're enforcing security at the application level
        try:
            response = supabase_service.table("assets").delete().eq("id", asset_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                # RLS is blocking - this means service role key is not set or not working
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file."
                )
            raise
        
        # Check if asset was actually deleted
        # Supabase delete returns empty array if nothing was deleted
        if response.data is None or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        return {"message": "Asset deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete asset: {str(e)}")


@router.get("/summary/total", response_model=dict)
async def get_total_portfolio_value(current_user=Depends(get_current_user)):
    """Get total portfolio value across all assets"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        response = supabase.table("assets").select("current_value").eq("user_id", user_id).eq("is_active", True).execute()
        
        total_value = sum(float(asset.get("current_value", 0)) for asset in response.data)
        
        return {
            "total_value": total_value,
            "currency": "USD",  # Could be made dynamic based on user preference
            "asset_count": len(response.data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate portfolio value: {str(e)}")


@router.get("/summary/by-type", response_model=dict)
async def get_assets_by_type(current_user=Depends(get_current_user)):
    """Get summary of assets grouped by type"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        response = supabase.table("assets").select("type, current_value").eq("user_id", user_id).eq("is_active", True).execute()
        
        summary = {
            "stock": {"count": 0, "total_value": 0.0},
            "mutual_fund": {"count": 0, "total_value": 0.0},
            "bank_account": {"count": 0, "total_value": 0.0},
            "fixed_deposit": {"count": 0, "total_value": 0.0}
        }
        
        for asset in response.data:
            asset_type = asset.get("type")
            value = float(asset.get("current_value", 0))
            if asset_type in summary:
                summary[asset_type]["count"] += 1
                summary[asset_type]["total_value"] += value
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assets summary: {str(e)}")


@router.post("/update-prices", response_model=dict)
async def update_stock_prices(current_user=Depends(get_current_user)):
    """Update current prices for all stocks and recalculate current_value"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Get all stock assets
        response = supabase.table("assets").select("*").eq("user_id", user_id).eq("type", "stock").eq("is_active", True).execute()
        
        if not response.data:
            return {"updated": 0, "message": "No stocks found"}
        
        updated_count = 0
        errors = []
        
        for asset in response.data:
            try:
                symbol = asset.get("stock_symbol")
                currency = asset.get("currency", "USD")
                quantity = float(asset.get("quantity", 0))
                
                if not symbol:
                    continue
                
                # Determine market based on currency
                market = "IN" if currency == "INR" else ("EU" if currency == "EUR" else "US")
                
                # Fetch current price
                current_price = await stock_price_service.get_stock_price(symbol, asset.get("stock_exchange"), market)
                
                if current_price:
                    # Calculate current value
                    current_value = float(current_price) * quantity
                    
                    # Update asset in database
                    update_data = {
                        "current_price": str(current_price),
                        "current_value": str(current_value)
                    }
                    
                    supabase.table("assets").update(update_data).eq("id", asset["id"]).execute()
                    updated_count += 1
                else:
                    errors.append(f"Could not fetch price for {symbol}")
            
            except Exception as e:
                errors.append(f"Error updating {asset.get('name', 'unknown')}: {str(e)}")
        
        return {
            "updated": updated_count,
            "total": len(response.data),
            "errors": errors
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update stock prices: {str(e)}")


@router.get("/prices/{asset_id}", response_model=dict)
async def get_stock_price(asset_id: str, current_user=Depends(get_current_user)):
    """Get current price for a specific stock asset"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Get the asset
        response = supabase.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).eq("type", "stock").execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Stock asset not found")
        
        asset = response.data[0]
        symbol = asset.get("stock_symbol")
        currency = asset.get("currency", "USD")
        quantity = float(asset.get("quantity", 0))
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Stock symbol not found")
        
        # Determine market based on currency
        market = "IN" if currency == "INR" else ("EU" if currency == "EUR" else "US")
        
        # Fetch current price
        current_price = await stock_price_service.get_stock_price(symbol, asset.get("stock_exchange"), market)
        
        if current_price is None:
            raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
        
        # Calculate current value
        current_value = float(current_price) * quantity
        
        return {
            "symbol": symbol,
            "current_price": float(current_price),
            "quantity": quantity,
            "current_value": current_value,
            "currency": currency
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stock price: {str(e)}")


@router.post("/fix-currency/{asset_id}")
async def fix_asset_currency(asset_id: str, current_user=Depends(get_current_user)):
    """Fix currency for an asset based on stock symbol/name (helper endpoint)"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Get the asset
        asset_response = supabase_service.table("assets").select("*").eq("id", asset_id).eq("user_id", user_id).execute()
        if not asset_response.data:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        asset = asset_response.data[0]
        
        # Only fix stocks
        if asset.get("type") != "stock":
            raise HTTPException(status_code=400, detail="Currency fix is only available for stocks")
        
        stock_symbol = asset.get("stock_symbol", "").upper()
        asset_name = asset.get("name", "").lower()
        current_currency = asset.get("currency", "USD")
        
        # Indian stock indicators
        indian_stocks = ["reliance", "tcs", "infosys", "hdfc", "icici", "sbi", "wipro", "bharti", "itc", "lt"]
        
        # Check if it's an Indian stock
        is_indian = (
            any(ind in asset_name for ind in indian_stocks) or
            any(ind in stock_symbol.lower() for ind in indian_stocks) or
            stock_symbol.endswith(".NS") or stock_symbol.endswith(".BO")
        )
        
        new_currency = "INR" if is_indian else current_currency
        
        if new_currency != current_currency:
            # Update the currency
            update_response = supabase_service.table("assets").update({"currency": new_currency}).eq("id", asset_id).eq("user_id", user_id).execute()
            if update_response.data:
                return {
                    "message": f"Currency updated from {current_currency} to {new_currency}",
                    "asset_id": asset_id,
                    "old_currency": current_currency,
                    "new_currency": new_currency
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to update currency")
        else:
            return {
                "message": f"Currency is already correct: {current_currency}",
                "asset_id": asset_id,
                "currency": current_currency
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fix currency: {str(e)}")


def parse_pdf_file(file_content: bytes, password: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Parse PDF file and extract text using PdfPlumber. Returns list of page texts."""
    try:
        pdf_stream = io.BytesIO(file_content)
        
        # Handle password-protected PDFs by decrypting with PyPDF2 first if password is provided
        if password:
            try:
                pdf_reader = PyPDF2.PdfReader(pdf_stream)
                if pdf_reader.is_encrypted:
                    if not pdf_reader.decrypt(password):
                        raise HTTPException(
                            status_code=400,
                            detail="Incorrect password for PDF file. Please check the password and try again."
                        )
                    # Create a new stream with decrypted content
                    writer = PdfWriter()
                    for page in pdf_reader.pages:
                        writer.add_page(page)
                    decrypted_stream = io.BytesIO()
                    writer.write(decrypted_stream)
                    decrypted_stream.seek(0)
                    pdf_stream = decrypted_stream
            except ImportError:
                pass
            except Exception as e:
                if "Incorrect password" in str(e) or isinstance(e, HTTPException):
                    raise
        
        # Parse PDF using PdfPlumber - return list of page texts
        text_content = []
        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                text_content.append(text if text is not None else "")
        
        # Check if we extracted any text
        if text_content and any(page_text.strip() for page_text in text_content):
            return {
                "type": "pdf",
                "pages": text_content,
                "text": "\n\n".join(text_content)  # Also provide concatenated version for backward compatibility
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from PDF file. Please ensure the PDF contains readable text."
            )
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="PDF parsing library not installed. Please install pdfplumber by running: pip install pdfplumber"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing PDF: {str(e)}"
        )


@router.post("/upload-pdf")
async def upload_pdf_for_asset_type(
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    market: Optional[str] = Form(None),
    pdf_password: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Upload a PDF file and extract assets of a specific type"""
    logger = logging.getLogger(__name__)
    logger.info(f"=== PDF UPLOAD REQUEST: asset_type={asset_type}, market={market} ===")
    print(f"=== PDF UPLOAD REQUEST: asset_type={asset_type}, market={market} ===")
    
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        logger.info(f"User ID extracted: {user_id}")
        
        # Validate file type
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        if file_extension != 'pdf':
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        logger.info(f"PDF file read. Size: {len(file_content)} bytes")
        
        # Parse PDF
        extracted_data = parse_pdf_file(file_content, password=pdf_password)
        if not extracted_data:
            raise HTTPException(
                status_code=400, 
                detail="Could not extract data from PDF file. Please ensure the PDF contains readable text and is not password-protected."
            )
        
        # Get pages list from extracted data
        pdf_pages = extracted_data.get("pages", [])
        if not pdf_pages:
            raise HTTPException(
                status_code=400,
                detail="No pages extracted from PDF file."
            )
        
        logger.info(f"PDF parsed successfully. Extracted {len(pdf_pages)} pages")
        
        # Fetch family members for owner name mapping
        family_members_map = {}
        try:
            family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
            family_members_list = family_members_response.data if family_members_response.data else []
            for fm in family_members_list:
                family_members_map[fm.get("name", "").lower()] = str(fm.get("id"))
        except Exception as e:
            pass
        
        # Process each page separately
        created_assets = []
        errors = []
        skipped_account_numbers = []  # Track account numbers skipped due to duplicates (for bank accounts)
        skipped_fd_keys = []  # Track fixed deposits skipped due to duplicates (for fixed deposits)
        skipped_stocks = []  # Track stocks skipped due to duplicates (for stocks)
        skipped_mutual_funds = []  # Track mutual funds skipped due to duplicates (for mutual funds)
        
        # Process fixed deposits or stocks
        if asset_type == "fixed_deposit":
            logger = logging.getLogger(__name__)
            logger.info("=== FIXED DEPOSIT PROCESSING STARTED ===")
            print("=== FIXED DEPOSIT PROCESSING STARTED ===")
            
            if not _fixed_deposit_llm_service.api_key:
                logger.error("GEMINI_API_KEY not found")
                print("ERROR: GEMINI_API_KEY not found")
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            logger.info("API key found, proceeding with fixed deposit extraction")
            print("API key found, proceeding with fixed deposit extraction")
            
            # Fetch family members for the user
            logger.info("Fetching family members...")
            print("Fetching family members...")
            family_members_list = []
            try:
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members_list = family_members_response.data if family_members_response.data else []
                logger.info(f"Found {len(family_members_list)} family members")
                print(f"Found {len(family_members_list)} family members")
            except Exception as e:
                logger.warning(f"Failed to fetch family members: {str(e)}")
                print(f"Warning: Failed to fetch family members: {str(e)}")
            
            # Format family members for the prompt and create mapping
            family_members_text = ""
            family_members_map = {}
            if family_members_list:
                family_members_lines = []
                for fm in family_members_list:
                    name = fm.get("name", "")
                    relationship = fm.get("relationship", "")
                    notes = fm.get("notes", "")
                    fm_id = fm.get("id", "")
                    if name:
                        line = f"- Name: {name}, Relationship: {relationship}"
                        if notes:
                            line += f", Notes: {notes}"
                        family_members_lines.append(line)
                        # Create mapping for owner name matching
                        if fm_id:
                            family_members_map[name.lower()] = str(fm_id)
                if family_members_lines:
                    family_members_text = "\n".join(family_members_lines)
            
            logger.info(f"Family members formatted. Text length: {len(family_members_text)}")
            print(f"Family members formatted. Text length: {len(family_members_text)}")
            
            # Combine all PDF pages into a single document
            complete_pdf_content = "\n\n--- Page Separator ---\n\n".join(pdf_pages)
            logger.info(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            print(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            
            # Process the complete PDF document
            all_fixed_deposits = []
            
            logger.info(f"Starting fixed deposit extraction. PDF has {len(pdf_pages)} pages. Total content length: {len(complete_pdf_content)} chars")
            print(f"Starting fixed deposit extraction. PDF has {len(pdf_pages)} pages")
            
            try:
                # Load prompt from file and replace placeholders with actual content
                logger.info("Loading prompt from file...")
                print("Loading prompt from file...")
                prompt_template = load_prompt("fixed_deposit_prompt.txt")
                logger.info("Prompt loaded successfully")
                print("Prompt loaded successfully")
                
                logger.info("Formatting prompt with PDF content and family members...")
                print("Formatting prompt...")
                instruction_prompt = prompt_template.format(
                    page=complete_pdf_content,
                    family_members=family_members_text if family_members_text else "No family members have been added yet."
                )
                logger.info(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                print(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                
                # Use chat function from LLMService - LLM will return a JSON object/array
                logger.info("Calling LLM for fixed deposit extraction...")
                print("Calling LLM for fixed deposit extraction...")
                
                # Track timing for LLM call
                import time
                llm_start_time = time.time()
                logger.info(f"LLM call started at {llm_start_time}")
                print(f"LLM call started - this may take 30-120 seconds for large PDFs...")
                
                # Increased max_tokens to 30000 to handle large PDFs without truncation
                text_response = await _fixed_deposit_llm_service.chat(
                    system_prompt="<Role>You are a helpful financial assistant that extracts fixed deposit information from a document.</Role>",
                    message=instruction_prompt, 
                    max_tokens=30000,  # Increased to handle large responses without truncation
                    temperature=0.7
                )
                
                llm_end_time = time.time()
                llm_duration = llm_end_time - llm_start_time
                logger.info(f"LLM call completed in {llm_duration:.2f} seconds ({llm_duration/60:.2f} minutes)")
                print(f"LLM call completed in {llm_duration:.2f} seconds")

                print(f"Text response: {text_response}")
                logger.info(f"LLM response type: {type(text_response)}, length: {len(text_response) if text_response else 0}")
                
                if not text_response:
                    errors.append("No response from LLM")
                    logger.error("LLM returned empty response")
                elif text_response.startswith("Error:"):
                    errors.append(f"LLM returned error: {text_response}")
                    logger.error(f"LLM error: {text_response}")
                    # If it's a "Could not extract response" error, provide more context
                    if "Could not extract response" in text_response:
                        logger.error("This usually means the API call succeeded but the response format was unexpected. The model might be overloaded or returning an unexpected format.")
                        errors.append("The AI service returned an unexpected response format. This may be due to service overload. Please try again in a few moments.")
                else:
                    # Parse JSON response - LLM returns a JSON object or array
                    try:
                        # Clean the response - remove markdown code blocks if present
                        cleaned_response = clean_json_response(text_response)
                        
                        print(f"Cleaned response: {cleaned_response}")
                        
                        # Check if response looks complete (should end with ] or })
                        if not (cleaned_response.rstrip().endswith(']') or cleaned_response.rstrip().endswith('}')):
                            logger.warning("Response may be incomplete - doesn't end with ] or }")
                            print("WARNING: Response may be incomplete")
                        
                        # Parse the JSON response
                        logger.info("Parsing JSON...")
                        print("Parsing JSON...")
                        fixed_deposit_obj = json.loads(cleaned_response)
                        logger.info(f"JSON parsed successfully. Type: {type(fixed_deposit_obj).__name__}")
                        print(f"JSON parsed successfully. Type: {type(fixed_deposit_obj).__name__}")
                        
                        # Handle different response formats
                        if isinstance(fixed_deposit_obj, list):
                            logger.info(f"Processing list with {len(fixed_deposit_obj)} items")
                            print(f"Processing list with {len(fixed_deposit_obj)} items")
                            for idx, item in enumerate(fixed_deposit_obj):
                                logger.info(f"Processing item {idx + 1}: {item}")
                                print(f"Processing item {idx + 1}: {item}")
                                if item and isinstance(item, dict) and len(item) > 0:
                                    # Check if it has required fields
                                    if item.get("Bank Name") or item.get("Amount Invested"):
                                        all_fixed_deposits.append(item)
                                        logger.info(f"Added fixed deposit from list: {item.get('Bank Name', 'Unknown')}")
                                        print(f"Added fixed deposit from list: {item.get('Bank Name', 'Unknown')}")
                        elif isinstance(fixed_deposit_obj, dict):
                            # If it's a single object, check if it's empty
                            if len(fixed_deposit_obj) > 0:
                                if fixed_deposit_obj.get("Bank Name") or fixed_deposit_obj.get("Amount Invested"):
                                    all_fixed_deposits.append(fixed_deposit_obj)
                                    logger.info(f"Added fixed deposit: {fixed_deposit_obj.get('Bank Name', 'Unknown')}")
                                    print(f"Added fixed deposit: {fixed_deposit_obj.get('Bank Name', 'Unknown')}")
                        
                        logger.info(f"Total fixed deposits collected: {len(all_fixed_deposits)}")
                        print(f"Total fixed deposits collected: {len(all_fixed_deposits)}")
                        
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON response from LLM: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"JSON decode error: {error_msg}")
                        logger.error(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
                        logger.error(f"Raw response (first 500 chars): {text_response[:500]}")
                        print(f"ERROR: JSON decode failed. Error: {str(e)}")
                        print(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
                        # Try to extract JSON from the response if it's partially valid
                        try:
                            # First, try to find the first complete JSON array
                            # Look for the first '[' that starts a valid JSON array
                            json_start = cleaned_response.find('[')
                            if json_start != -1:
                                # Extract from first '[' onwards
                                json_substring = cleaned_response[json_start:]
                                
                                # Find the matching closing bracket for the first array
                                bracket_count = 0
                                in_string = False
                                escape_next = False
                                array_end = -1
                                
                                for i, char in enumerate(json_substring):
                                    if escape_next:
                                        escape_next = False
                                        continue
                                    if char == '\\':
                                        escape_next = True
                                        continue
                                    if char == '"' and not escape_next:
                                        in_string = not in_string
                                        continue
                                    if not in_string:
                                        if char == '[':
                                            bracket_count += 1
                                        elif char == ']':
                                            bracket_count -= 1
                                            if bracket_count == 0:
                                                # Found complete array
                                                array_end = i + 1
                                                break
                                
                                if array_end > 0:
                                    # Extract just the first complete array
                                    first_array = json_substring[:array_end]
                                    logger.info(f"Extracted first JSON array (length: {len(first_array)} chars)")
                                    print(f"Extracted first JSON array (length: {len(first_array)} chars)")
                                    
                                    # Clean any control characters that might cause issues
                                    first_array = first_array.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                                    
                                    # Try parsing the first array
                                    fixed_obj = json.loads(first_array)
                                    logger.info(f"Successfully parsed first JSON array")
                                    print(f"Successfully parsed first JSON array")
                                    
                                    # Process the fixed object
                                    if isinstance(fixed_obj, list):
                                        logger.info(f"Found {len(fixed_obj)} items in extracted array")
                                        print(f"Found {len(fixed_obj)} items in extracted array")
                                        all_fixed_deposits.extend([item for item in fixed_obj if item and isinstance(item, dict)])
                                    elif isinstance(fixed_obj, dict):
                                        all_fixed_deposits.append(fixed_obj)
                                else:
                                    # Array is incomplete - try to extract individual objects
                                    logger.warning("Could not find complete JSON array, trying to extract individual objects")
                                    print("WARNING: Could not find complete JSON array, trying to extract individual objects")
                                    
                                    # Find where duplicate starts (look for second '[' or markdown markers)
                                    duplicate_marker = json_substring.find('```', 1)  # Find second occurrence
                                    if duplicate_marker == -1:
                                        duplicate_marker = json_substring.find('[', 1)  # Find second '['
                                    if duplicate_marker > 0:
                                        # Only process up to the duplicate marker
                                        json_substring = json_substring[:duplicate_marker]
                                        logger.info(f"Truncated response at duplicate marker (position {duplicate_marker})")
                                        print(f"Truncated response at duplicate marker (position {duplicate_marker})")
                                    
                                    # Try to find and extract individual JSON objects using bracket matching
                                    extracted_objects = []
                                    seen_objects = set()  # Track seen objects to avoid duplicates
                                    
                                    i = 0
                                    while i < len(json_substring):
                                        # Find the start of an object
                                        obj_start = json_substring.find('{', i)
                                        if obj_start == -1:
                                            break
                                        
                                        # Find the matching closing brace
                                        brace_count = 0
                                        in_string = False
                                        escape_next = False
                                        obj_end = -1
                                        
                                        for j in range(obj_start, len(json_substring)):
                                            char = json_substring[j]
                                            if escape_next:
                                                escape_next = False
                                                continue
                                            if char == '\\':
                                                escape_next = True
                                                continue
                                            if char == '"' and not escape_next:
                                                in_string = not in_string
                                                continue
                                            if not in_string:
                                                if char == '{':
                                                    brace_count += 1
                                                elif char == '}':
                                                    brace_count -= 1
                                                    if brace_count == 0:
                                                        obj_end = j + 1
                                                        break
                                        
                                        if obj_end > obj_start:
                                            # Extract the object
                                            obj_str = json_substring[obj_start:obj_end]
                                            # Clean control characters
                                            obj_str = obj_str.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                                            try:
                                                obj = json.loads(obj_str)
                                                if isinstance(obj, dict):
                                                    # Check if it has at least Bank Name or Amount Invested
                                                    bank_name = obj.get("Bank Name") or ""
                                                    amount = obj.get("Amount Invested") or ""
                                                    if bank_name or amount:
                                                        # Create a unique key to avoid duplicates
                                                        obj_key = f"{bank_name.lower().strip()}_{str(amount).strip().lower()}"
                                                        if obj_key not in seen_objects:
                                                            seen_objects.add(obj_key)
                                                            extracted_objects.append(obj)
                                                            logger.info(f"Extracted object: {bank_name}, Amount: {amount}")
                                                            print(f"Extracted object: {bank_name}, Amount: {amount}")
                                                        else:
                                                            logger.info(f"Skipping duplicate object: {bank_name}, Amount: {amount}")
                                                            print(f"Skipping duplicate object: {bank_name}, Amount: {amount}")
                                            except json.JSONDecodeError as e:
                                                logger.warning(f"Failed to parse object at position {obj_start}: {str(e)}")
                                                print(f"WARNING: Failed to parse object: {str(e)}")
                                            
                                            # Move to after this object
                                            i = obj_end
                                        else:
                                            # No complete object found, move forward
                                            i = obj_start + 1
                                    
                                    if extracted_objects:
                                        logger.info(f"Successfully extracted {len(extracted_objects)} unique objects from incomplete response")
                                        print(f"Successfully extracted {len(extracted_objects)} unique objects from incomplete response")
                                        all_fixed_deposits.extend(extracted_objects)
                                    else:
                                        logger.warning("Could not extract any valid objects from incomplete response")
                                        print("WARNING: Could not extract any valid objects from incomplete response")
                            else:
                                # Try to find a JSON object instead
                                json_start = cleaned_response.find('{')
                                if json_start != -1:
                                    # Similar logic for objects
                                    json_substring = cleaned_response[json_start:]
                                    brace_count = 0
                                    in_string = False
                                    escape_next = False
                                    object_end = -1
                                    
                                    for i, char in enumerate(json_substring):
                                        if escape_next:
                                            escape_next = False
                                            continue
                                        if char == '\\':
                                            escape_next = True
                                            continue
                                        if char == '"' and not escape_next:
                                            in_string = not in_string
                                            continue
                                        if not in_string:
                                            if char == '{':
                                                brace_count += 1
                                            elif char == '}':
                                                brace_count -= 1
                                                if brace_count == 0:
                                                    object_end = i + 1
                                                    break
                                    
                                    if object_end > 0:
                                        first_object = json_substring[:object_end]
                                        fixed_obj = json.loads(first_object)
                                        if isinstance(fixed_obj, dict):
                                            all_fixed_deposits.append(fixed_obj)
                        except Exception as fix_error:
                            logger.error(f"Failed to extract valid JSON from partial response: {str(fix_error)}")
                            print(f"Failed to extract valid JSON: {str(fix_error)}")
                    except Exception as e:
                        errors.append(f"Error parsing response: {str(e)}")
                        logger.error(f"Parse error: {str(e)}")
            
            except Exception as e:
                errors.append(f"Error processing PDF: {str(e)}")
                logger.error(f"Error processing PDF: {str(e)}")
                print(f"ERROR processing PDF: {str(e)}")
                import traceback
                error_trace = traceback.format_exc()
                logger.error(error_trace)
                print(f"Traceback: {error_trace}")
            
            # Remove duplicates based on bank name and principal amount (keep first occurrence)
            logger.info(f"Before deduplication: {len(all_fixed_deposits)} fixed deposits")
            print(f"Before deduplication: {len(all_fixed_deposits)} fixed deposits")
            seen_fds = set()
            unique_fixed_deposits = []
            for fd in all_fixed_deposits:
                bank_name = fd.get("Bank Name") or fd.get("bank_name") or ""
                amount_invested = fd.get("Amount Invested") or fd.get("amount_invested") or ""
                # Create a unique key from bank name and amount
                if bank_name and amount_invested:
                    fd_key = f"{bank_name.lower().strip()}_{str(amount_invested).strip().lower()}"
                    if fd_key not in seen_fds:
                        seen_fds.add(fd_key)
                        unique_fixed_deposits.append(fd)
                    else:
                        logger.info(f"Skipping duplicate fixed deposit: {bank_name}, Amount: {amount_invested}")
                        print(f"Skipping duplicate fixed deposit: {bank_name}, Amount: {amount_invested}")
                else:
                    # If no bank name or amount, keep it (shouldn't happen based on validation)
                    unique_fixed_deposits.append(fd)
            
            all_fixed_deposits = unique_fixed_deposits
            logger.info(f"After deduplication: {len(all_fixed_deposits)} unique fixed deposits")
            print(f"After deduplication: {len(all_fixed_deposits)} unique fixed deposits")
            
            # Fetch existing fixed deposits from database to check for duplicates
            existing_fixed_deposits = []
            existing_fd_keys = set()
            try:
                logger.info("Fetching existing fixed deposits from database...")
                print("Fetching existing fixed deposits from database...")
                existing_assets_response = supabase_service.table("assets").select("name, principal_amount").eq("user_id", user_id).eq("type", "fixed_deposit").execute()
                all_existing_fds = existing_assets_response.data if existing_assets_response.data else []
                # Filter to only active fixed deposits (is_active = True or NULL)
                existing_fixed_deposits = [fd for fd in all_existing_fds if fd.get("is_active") is True or fd.get("is_active") is None]
                
                # Create set of existing FD keys (bank_name + principal_amount)
                for existing_fd in existing_fixed_deposits:
                    existing_bank_name = existing_fd.get("name", "")
                    existing_amount = existing_fd.get("principal_amount", "")
                    if existing_bank_name and existing_amount:
                        existing_key = f"{existing_bank_name.lower().strip()}_{str(existing_amount).strip().lower()}"
                        existing_fd_keys.add(existing_key)
                
                logger.info(f"Found {len(existing_fixed_deposits)} existing fixed deposits in database")
                print(f"Found {len(existing_fixed_deposits)} existing fixed deposits in database")
            except Exception as e:
                logger.warning(f"Error fetching existing fixed deposits: {str(e)}")
                print(f"Warning: Error fetching existing fixed deposits: {str(e)}")
            
            # Process all collected fixed deposits
            logger.info(f"Starting to process {len(all_fixed_deposits)} fixed deposits for database insertion")
            print(f"Starting to process {len(all_fixed_deposits)} fixed deposits for database insertion")
            # Reset skipped_fd_keys for this processing (already initialized at function level)
            skipped_fd_keys = []
            for fd_idx, fd_data in enumerate(all_fixed_deposits):
                try:
                    logger.info(f"Processing fixed deposit {fd_idx + 1}/{len(all_fixed_deposits)}: {fd_data}")
                    print(f"Processing fixed deposit {fd_idx + 1}/{len(all_fixed_deposits)}")
                    
                    # Get currency from market
                    asset_market = market or "india"
                    currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                    
                    # Extract and validate fields (handle multiple possible key names)
                    bank_name = fd_data.get("Bank Name") or fd_data.get("bank_name") or "Unknown Bank"
                    amount_invested = fd_data.get("Amount Invested") or fd_data.get("amount_invested") or fd_data.get("Principal Amount") or fd_data.get("principal_amount")
                    rate_of_interest = fd_data.get("Rate of Interest") or fd_data.get("rate_of_interest") or fd_data.get("Interest Rate") or fd_data.get("fd_interest_rate")
                    duration = fd_data.get("Duration") or fd_data.get("duration") or fd_data.get("duration_months")
                    start_date_str = fd_data.get("Start Date") or fd_data.get("start_date")
                    owner_name = fd_data.get("Owner Name") or fd_data.get("owner_name") or "self"
                    
                    # Handle empty string duration (convert to None)
                    if duration == "" or duration is None:
                        duration = None
                    
                    logger.info(f"Extracted: bank_name={bank_name}, amount={amount_invested}, rate={rate_of_interest}, duration={duration}, start_date={start_date_str}, owner={owner_name}")
                    print(f"Extracted: bank_name={bank_name}, amount={amount_invested}, rate={rate_of_interest}, duration={duration}")
                    
                    # Validate required fields
                    if not bank_name or not amount_invested or not rate_of_interest or not start_date_str or not duration:
                        error_msg = f"FD {fd_idx + 1}: Missing required fields (bank_name, amount_invested, rate_of_interest, start_date, or duration). Duration: {duration}"
                        logger.warning(error_msg)
                        print(f"WARNING: {error_msg}")
                        errors.append(error_msg)
                        continue
                                
                    # Helper function to clean numeric strings
                    def clean_numeric_string(value):
                        if isinstance(value, str):
                            cleaned = value.replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '').replace('%', '')
                            return cleaned
                        return str(value)
                    
                    # Convert amount invested to float
                    try:
                        amount_cleaned = clean_numeric_string(amount_invested)
                        principal_amount_float = float(amount_cleaned)
                    except (ValueError, TypeError) as e:
                        error_msg = f"FD {fd_idx + 1}: Invalid amount invested value: {amount_invested}"
                        errors.append(error_msg)
                        continue
                    
                    # Convert rate of interest to float
                    try:
                        rate_cleaned = clean_numeric_string(rate_of_interest)
                        fd_interest_rate_float = float(rate_cleaned)
                    except (ValueError, TypeError) as e:
                        error_msg = f"FD {fd_idx + 1}: Invalid interest rate value: {rate_of_interest}"
                        errors.append(error_msg)
                        continue
                    
                    # Convert duration to integer (months)
                    try:
                        duration_cleaned = clean_numeric_string(duration)
                        duration_months_int = int(float(duration_cleaned))
                    except (ValueError, TypeError) as e:
                        error_msg = f"FD {fd_idx + 1}: Invalid duration value: {duration}"
                        errors.append(error_msg)
                        continue
                                
                    # Parse start date
                    start_date = None
                    try:
                        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    except:
                        try:
                            start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                        except:
                            try:
                                start_date = datetime.strptime(start_date_str, "%d/%m/%Y").date()
                            except:
                                error_msg = f"FD {fd_idx + 1}: Invalid start date format: {start_date_str}"
                                errors.append(error_msg)
                                continue
                    
                    # Calculate maturity date from start date and duration (in months)
                    maturity_date = start_date + relativedelta(months=duration_months_int)
                    
                    # Map owner name to family member ID
                    family_member_id = None
                    owner_name_lower = owner_name.lower().strip()
                    if owner_name_lower in ["self", "me", "myself", ""]:
                        family_member_id = None
                    elif owner_name_lower in family_members_map:
                        family_member_id = family_members_map[owner_name_lower]
                    else:
                        # Try partial match
                        for fm_name, fm_id in family_members_map.items():
                            if owner_name_lower in fm_name or fm_name in owner_name_lower:
                                family_member_id = fm_id
                                break
                    
                    # Build asset data
                    asset_data = {
                        "name": bank_name,
                        "type": "fixed_deposit",
                        "currency": currency,
                        "principal_amount": principal_amount_float,
                        "fd_interest_rate": fd_interest_rate_float,
                        "start_date": start_date.isoformat(),
                        "maturity_date": maturity_date.isoformat(),
                        "current_value": principal_amount_float,  # Use principal amount as current value
                        "is_active": True,
                        "family_member_id": family_member_id
                    }
                    
                    # Create AssetCreate object
                    asset_create = AssetCreate(**{k: v for k, v in asset_data.items() if v is not None})
                    asset_create.model_validate_asset_fields()
                    
                    # Convert to dict
                    try:
                        asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
                    except AttributeError:
                        asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
                    
                    asset_dict["user_id"] = user_id
                    
                    # Convert decimals to strings
                    decimal_fields = ['principal_amount', 'fd_interest_rate', 'current_value']
                    for field in decimal_fields:
                        if field in asset_dict and asset_dict[field] is not None:
                            asset_dict[field] = str(asset_dict[field])
                                
                    # Check for duplicates before inserting
                    # Create FD key from bank name and principal amount
                    fd_key = f"{bank_name.lower().strip()}_{str(principal_amount_float).strip().lower()}"
                    is_duplicate = False
                    
                    # Check against existing FDs in database
                    if fd_key in existing_fd_keys:
                        logger.info(f"Skipping fixed deposit - already exists in database: {bank_name}, Amount: {principal_amount_float}")
                        print(f"Skipping fixed deposit - already exists in database: {bank_name}, Amount: {principal_amount_float}")
                        skipped_fd_keys.append(f"{bank_name} (Amount: {principal_amount_float})")
                        is_duplicate = True
                    
                    # Also check against newly created assets in this session
                    if not is_duplicate:
                        for created_asset in created_assets:
                            if created_asset.get("type") == "fixed_deposit":
                                created_bank_name = created_asset.get("name", "")
                                created_amount = created_asset.get("principal_amount", "")
                                if created_bank_name and created_amount:
                                    created_key = f"{created_bank_name.lower().strip()}_{str(created_amount).strip().lower()}"
                                    if fd_key == created_key:
                                        logger.info(f"Skipping fixed deposit - duplicate in current session: {bank_name}")
                                        print(f"Skipping fixed deposit - duplicate in current session: {bank_name}")
                                        if f"{bank_name} (Amount: {principal_amount_float})" not in skipped_fd_keys:
                                            skipped_fd_keys.append(f"{bank_name} (Amount: {principal_amount_float})")
                                        is_duplicate = True
                                        break
                    
                    if is_duplicate:
                        continue
                    
                    # Insert into database
                    logger.info(f"Inserting fixed deposit into database: {bank_name}, Amount: {principal_amount_float}")
                    print(f"Inserting fixed deposit into database: {bank_name}")
                    response = supabase_service.table("assets").insert(asset_dict).execute()
                    if response.data and len(response.data) > 0:
                        created_assets.append(response.data[0])
                        logger.info(f"Successfully created fixed deposit: {bank_name} (ID: {response.data[0].get('id')})")
                        print(f"Successfully created fixed deposit: {bank_name}")
                    else:
                        error_msg = f"Failed to create fixed deposit: {bank_name}"
                        logger.error(error_msg)
                        print(f"ERROR: {error_msg}")
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"FD {fd_idx + 1}: Error processing fixed deposit: {str(e)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)
        
        elif asset_type == "stock":
            logger = logging.getLogger(__name__)
            logger.info("=== STOCK PROCESSING STARTED ===")
            print("=== STOCK PROCESSING STARTED ===")
            
            if not _stock_llm_service.api_key:
                logger.error("GEMINI_API_KEY not found")
                print("ERROR: GEMINI_API_KEY not found")
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            logger.info("API key found, proceeding with stock extraction")
            print("API key found, proceeding with stock extraction")
            
            # Fetch family members for the user
            logger.info("Fetching family members...")
            print("Fetching family members...")
            family_members_list = []
            try:
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members_list = family_members_response.data if family_members_response.data else []
                logger.info(f"Found {len(family_members_list)} family members")
                print(f"Found {len(family_members_list)} family members")
            except Exception as e:
                logger.warning(f"Failed to fetch family members: {str(e)}")
                print(f"Warning: Failed to fetch family members: {str(e)}")
            
            # Format family members for the prompt and create mapping
            family_members_text = ""
            family_members_map = {}
            if family_members_list:
                family_members_lines = []
                for fm in family_members_list:
                    name = fm.get("name", "")
                    relationship = fm.get("relationship", "")
                    notes = fm.get("notes", "")
                    fm_id = fm.get("id", "")
                    if name:
                        line = f"- Name: {name}, Relationship: {relationship}"
                        if notes:
                            line += f", Notes: {notes}"
                        family_members_lines.append(line)
                        # Create mapping for owner name matching
                        if fm_id:
                            family_members_map[name.lower()] = str(fm_id)
                if family_members_lines:
                    family_members_text = "\n".join(family_members_lines)
            
            logger.info(f"Family members formatted. Text length: {len(family_members_text)}")
            print(f"Family members formatted. Text length: {len(family_members_text)}")
            
            # Combine all PDF pages into a single document
            complete_pdf_content = "\n\n--- Page Separator ---\n\n".join(pdf_pages)
            logger.info(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            print(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            logger.info(f"Starting stock extraction. PDF has {len(pdf_pages)} pages")
            print(f"Starting stock extraction. PDF has {len(pdf_pages)} pages")
            
            # Process the complete PDF document
            all_stocks = []
            
            try:
                # Load prompt from file and replace placeholders with actual content
                logger.info("Loading prompt from file...")
                print("Loading prompt from file...")
                prompt_template = load_prompt("stocks_prompt.txt")
                logger.info("Prompt loaded successfully")
                print("Prompt loaded successfully")
                
                logger.info("Formatting prompt with PDF content and family members...")
                print("Formatting prompt...")
                instruction_prompt = prompt_template.format(
                    page=complete_pdf_content,
                    family_members=family_members_text if family_members_text else "No family members have been added yet."
                )
                logger.info(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                print(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                
                # Use chat function from LLMService - LLM will return a JSON object/array
                logger.info("Calling LLM for stock extraction...")
                print("Calling LLM for stock extraction...")
                logger.info("WAITING for LLM response - blocking until complete...")
                print("WAITING for LLM response - blocking until complete...")
                logger.info("NOTE: Other requests may be processed concurrently while waiting for LLM (this is normal async behavior)")
                
                # Track timing for LLM call
                import time
                llm_start_time = time.time()
                logger.info(f"LLM call started at {llm_start_time}")
                print(f"LLM call started - this may take 30-120 seconds for large PDFs...")
                
                # Explicitly await the LLM response - this will block THIS request until the response is received
                # Note: FastAPI can still process other requests concurrently because run_in_executor yields to event loop
                # Increased max_tokens to 30000 to handle large PDFs (prompt is ~22k tokens, need room for response)
                # The prompt itself is large, so we need sufficient tokens for the response
                text_response = await _stock_llm_service.chat(
                    system_prompt="<Role>You are a helpful financial assistant that extracts stock/equity information from a document.</Role>",
                    message=instruction_prompt,
                    max_tokens=60000,  # Increased to handle large responses without truncation
                    temperature=0.7
                )
                
                llm_end_time = time.time()
                llm_duration = llm_end_time - llm_start_time
                logger.info(f"LLM call completed in {llm_duration:.2f} seconds ({llm_duration/60:.2f} minutes)")
                print(f"LLM call completed in {llm_duration:.2f} seconds")
                
                # Ensure we have a response before proceeding
                logger.info("LLM response received - proceeding with processing...")
                print("LLM response received - proceeding with processing...")
                print(f"Text response: {text_response}")
                logger.info(f"LLM response type: {type(text_response)}, length: {len(text_response) if text_response else 0}")
                
                if not text_response:
                    errors.append("No response from LLM")
                    logger.error("LLM returned empty response")
                elif text_response.startswith("Error:"):
                    errors.append(f"LLM returned error: {text_response}")
                    logger.error(f"LLM error: {text_response}")
                    # Check for specific LLM service errors
                    error_lower = text_response.lower()
                    if ("503" in text_response or "unavailable" in error_lower or 
                        "overloaded" in error_lower or "service unavailable" in error_lower):
                        message = f"Failed to extract assets from PDF: The AI service is temporarily unavailable. Please try again in a few moments. Details: {text_response}"
                    else:
                        message = f"Failed to extract assets from PDF due to an AI processing error. Details: {text_response}"
                    return {
                        "success": False,
                        "created_count": 0,
                        "created_assets": [],
                        "errors": errors,
                        "message": message,
                        "skipped_account_numbers": [],
                        "skipped_fixed_deposits": [],
                        "skipped_stocks": []
                    }
                else:
                    # Parse JSON response - LLM returns a JSON object or array
                    try:
                        # Clean the response - remove markdown code blocks if present
                        cleaned_response = clean_json_response(text_response)
                        
                        print(f"Cleaned response: {cleaned_response}")
                        
                        # Check if response looks complete (should end with ] or })
                        if not (cleaned_response.rstrip().endswith(']') or cleaned_response.rstrip().endswith('}')):
                            logger.warning("Response may be incomplete - doesn't end with ] or }")
                            print("WARNING: Response may be incomplete")
                        
                        # Parse the JSON response
                        logger.info("Parsing JSON...")
                        print("Parsing JSON...")
                        stock_obj = json.loads(cleaned_response)
                        logger.info(f"JSON parsed successfully. Type: {type(stock_obj).__name__}")
                        print(f"JSON parsed successfully. Type: {type(stock_obj).__name__}")
                        
                        # Handle different response formats
                        if isinstance(stock_obj, list):
                            logger.info(f"Processing list with {len(stock_obj)} items")
                            print(f"Processing list with {len(stock_obj)} items")
                            for idx, item in enumerate(stock_obj):
                                logger.info(f"Processing item {idx + 1}: {item}")
                                print(f"Processing item {idx + 1}: {item}")
                                if item and isinstance(item, dict) and len(item) > 0:
                                    # Check if it has required fields
                                    if item.get("Stock/Equity Name") or item.get("Stock Symbol"):
                                        all_stocks.append(item)
                                        logger.info(f"Added stock from list: {item.get('Stock/Equity Name', 'Unknown')}")
                                        print(f"Added stock from list: {item.get('Stock/Equity Name', 'Unknown')}")
                        elif isinstance(stock_obj, dict):
                            # If it's a single object, check if it's empty
                            if len(stock_obj) > 0:
                                if stock_obj.get("Stock/Equity Name") or stock_obj.get("Stock Symbol"):
                                    all_stocks.append(stock_obj)
                                    logger.info(f"Added stock: {stock_obj.get('Stock/Equity Name', 'Unknown')}")
                                    print(f"Added stock: {stock_obj.get('Stock/Equity Name', 'Unknown')}")
                        
                        logger.info(f"Total stocks collected: {len(all_stocks)}")
                        print(f"Total stocks collected: {len(all_stocks)}")
                        
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON response from LLM: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"JSON decode error: {error_msg}")
                        logger.error(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
                        logger.error(f"Raw response (first 500 chars): {text_response[:500]}")
                        print(f"ERROR: JSON decode failed. Error: {str(e)}")
                        print(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
                        
                        # Try to extract JSON from the response if it's partially valid
                        try:
                            # First, try to find the first complete JSON array
                            json_start = cleaned_response.find('[')
                            if json_start != -1:
                                json_substring = cleaned_response[json_start:]
                                bracket_count = 0
                                in_string = False
                                escape_next = False
                                array_end = -1
                                
                                for i, char in enumerate(json_substring):
                                    if escape_next: escape_next = False; continue
                                    if char == '\\': escape_next = True; continue
                                    if char == '"' and not escape_next: in_string = not in_string; continue
                                    if not in_string:
                                        if char == '[': bracket_count += 1
                                        elif char == ']':
                                            bracket_count -= 1
                                            if bracket_count == 0: array_end = i + 1; break
                                
                                if array_end > 0:
                                    first_array = json_substring[:array_end]
                                    stock_obj = json.loads(first_array)
                                    if isinstance(stock_obj, list):
                                        all_stocks.extend([item for item in stock_obj if item and isinstance(item, dict)])
                                    elif isinstance(stock_obj, dict):
                                        all_stocks.append(stock_obj)
                            else:
                                logger.warning("Could not find any JSON array or object start in response")
                                print("WARNING: Could not find any JSON array or object start in response")
                        except Exception as fix_error:
                            logger.error(f"Failed to extract valid JSON from partial response: {str(fix_error)}")
                            print(f"Failed to extract valid JSON: {str(fix_error)}")
                    except Exception as e:
                        errors.append(f"Error parsing response: {str(e)}")
                        logger.error(f"Parse error: {str(e)}")
            
            except Exception as e:
                error_msg = f"Error during stock extraction: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                import traceback
                error_trace = traceback.format_exc()
                logger.error(error_trace)
                print(f"Traceback: {error_trace}")
            
            # Ensure LLM processing is complete before proceeding with deduplication
            logger.info("LLM processing complete. Proceeding with stock deduplication and database insertion...")
            print("LLM processing complete. Proceeding with stock deduplication and database insertion...")
            
            # Remove duplicates based on stock symbol/name (keep first occurrence)
            logger.info(f"Before deduplication: {len(all_stocks)} stocks")
            print(f"Before deduplication: {len(all_stocks)} stocks")
            seen_stock_symbols = set()  # Track by symbol/name
            seen_stock_keys = set()  # Also track by symbol + purchase date for backward compatibility
            unique_stocks = []
            for stock in all_stocks:
                stock_symbol = stock.get("Stock Symbol") or stock.get("stock_symbol") or stock.get("Symbol") or ""
                stock_name = stock.get("Stock/Equity Name") or stock.get("Stock Name") or stock.get("Equity Name") or stock.get("stock_name") or stock.get("name") or ""
                purchase_date = stock.get("Purchase Date") or stock.get("purchase_date") or "1900-01-01"
                
                # Create a unique key from symbol/name (primary check)
                check_symbol = stock_symbol.lower().strip() if stock_symbol else (stock_name.lower().strip() if stock_name else "")
                
                # Also create key from symbol + purchase date for backward compatibility
                stock_key = f"{stock_symbol.lower().strip()}_{purchase_date.strip().lower()}" if stock_symbol and purchase_date else ""
                
                is_duplicate = False
                
                # Check by symbol/name first (regardless of purchase date)
                if check_symbol:
                    if check_symbol in seen_stock_symbols:
                        logger.info(f"Skipping duplicate stock: {stock_symbol or stock_name}")
                        print(f"Skipping duplicate stock: {stock_symbol or stock_name}")
                        is_duplicate = True
                    else:
                        seen_stock_symbols.add(check_symbol)
                
                # Also check by symbol + purchase date for backward compatibility
                if not is_duplicate and stock_key:
                    if stock_key in seen_stock_keys:
                        logger.info(f"Skipping duplicate stock: {stock_symbol}, Purchase Date: {purchase_date}")
                        print(f"Skipping duplicate stock: {stock_symbol}, Purchase Date: {purchase_date}")
                        is_duplicate = True
                    else:
                        seen_stock_keys.add(stock_key)
                
                if not is_duplicate:
                    unique_stocks.append(stock)
                # If no symbol or name, keep it (shouldn't happen based on validation)
                elif not check_symbol:
                    unique_stocks.append(stock)
            
            all_stocks = unique_stocks
            logger.info(f"After deduplication: {len(all_stocks)} unique stocks")
            print(f"After deduplication: {len(all_stocks)} unique stocks")
            
            # Fetch existing stocks from database to check for duplicates
            existing_stocks = []
            existing_stock_symbols = set()  # Track existing stock symbols (or names if symbol not available)
            existing_stock_keys = set()  # Track existing stock keys (symbol + purchase_date) for backward compatibility
            try:
                logger.info("Fetching existing stocks from database...")
                print("Fetching existing stocks from database...")
                existing_assets_response = supabase_service.table("assets").select("stock_symbol, name, purchase_date").eq("user_id", user_id).eq("type", "stock").execute()
                all_existing_stocks = existing_assets_response.data if existing_assets_response.data else []
                # Filter to only active stocks (is_active = True or NULL)
                existing_stocks = [s for s in all_existing_stocks if s.get("is_active") is True or s.get("is_active") is None]
                
                # Create set of existing stock symbols/names and keys
                for existing_stock in existing_stocks:
                    existing_symbol = existing_stock.get("stock_symbol", "")
                    existing_name = existing_stock.get("name", "")
                    existing_date = existing_stock.get("purchase_date", "")
                    
                    # Add to symbol/name set (use symbol if available, otherwise use name)
                    if existing_symbol:
                        existing_stock_symbols.add(existing_symbol.lower().strip())
                    elif existing_name:
                        existing_stock_symbols.add(existing_name.lower().strip())
                    
                    # Also track symbol + purchase_date for backward compatibility
                    if existing_symbol and existing_date:
                        existing_key = f"{existing_symbol.lower().strip()}_{existing_date.strip().lower()}"
                        existing_stock_keys.add(existing_key)
                
                logger.info(f"Found {len(existing_stocks)} existing active stocks in database")
                print(f"Found {len(existing_stocks)} existing active stocks in database")
            except Exception as e:
                logger.error(f"Error fetching existing stocks for duplicate check: {str(e)}")
                pass
            
            # Process all collected stocks for database insertion
            skipped_stocks = []
            logger.info(f"Starting to process {len(all_stocks)} stocks for database insertion")
            print(f"Starting to process {len(all_stocks)} stocks for database insertion")
            
            for stock_idx, stock_data in enumerate(all_stocks):
                try:
                    logger.info(f"Processing stock {stock_idx + 1}/{len(all_stocks)}")
                    print(f"Processing stock {stock_idx + 1}/{len(all_stocks)}")
                    
                    # Get currency from market
                    asset_market = market or "india"
                    currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                    
                    # Extract and validate fields (handle multiple possible key names)
                    stock_name = stock_data.get("Stock/Equity Name") or stock_data.get("Stock Name") or stock_data.get("Equity Name") or stock_data.get("stock_name") or stock_data.get("name")
                    stock_symbol = stock_data.get("Stock Symbol") or stock_data.get("stock_symbol") or stock_data.get("Symbol") or stock_data.get("symbol")
                    # Average Price = purchase price (the price at which shares were bought)
                    average_price = stock_data.get("Average Price") or stock_data.get("Avg. Price") or stock_data.get("avg_price") or stock_data.get("Purchase Price") or stock_data.get("purchase_price")
                    # Current Price = current market price
                    current_price = stock_data.get("Current Price") or stock_data.get("Price") or stock_data.get("current_price") or stock_data.get("Market Price") or stock_data.get("market_price")
                    quantity = stock_data.get("Quantity") or stock_data.get("Shares") or stock_data.get("Number of Shares") or stock_data.get("quantity")
                    purchase_date_str = stock_data.get("Purchase Date") or stock_data.get("purchase_date")
                    # Value at Cost = total amount invested (Average Price * Quantity)
                    value_at_cost = stock_data.get("Value at Cost") or stock_data.get("value_at_cost") or stock_data.get("Amount Invested") or stock_data.get("Total Invested") or stock_data.get("Investment Amount") or stock_data.get("amount_invested")
                    current_value = stock_data.get("Current Value") or stock_data.get("Current Worth") or stock_data.get("Market Value") or stock_data.get("current_value")
                    owner_name = stock_data.get("Owner Name") or stock_data.get("owner_name") or "self"
                    
                    # Use stock name as symbol if symbol is not provided
                    if not stock_symbol and stock_name:
                        stock_symbol = stock_name
                    
                    # Skip if this looks like a mutual fund (has "Scheme" or "NAV" or "Units" but no stock-like fields)
                    if (stock_data.get("Scheme") or stock_data.get("NAV") or stock_data.get("nav")) and not stock_name:
                        continue
                    
                    # Validate required fields (name, symbol, average_price, current_price, quantity, value_at_cost are mandatory; purchase_date can be defaulted)
                    if not stock_name or not stock_symbol or not average_price or not current_price or not quantity or not value_at_cost:
                        error_msg = f"Stock {stock_idx + 1}: Missing required fields (name, symbol, average_price, current_price, quantity, or value_at_cost). Data: {stock_data}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    # Use default date if purchase_date is not provided
                    if not purchase_date_str or purchase_date_str == "1900-01-01":
                        purchase_date_str = "1900-01-01"  # Default placeholder date
                    
                    # Parse purchase date (handle default placeholder)
                    purchase_date = None
                    if purchase_date_str and purchase_date_str != "1900-01-01":
                        try:
                            purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
                        except:
                            try:
                                purchase_date = datetime.strptime(purchase_date_str, "%d-%m-%Y").date()
                            except:
                                try:
                                    purchase_date = datetime.strptime(purchase_date_str, "%d/%m/%Y").date()
                                except:
                                    purchase_date = datetime.strptime("1900-01-01", "%Y-%m-%d").date()
                    else:
                        # Use default placeholder date
                        purchase_date = datetime.strptime("1900-01-01", "%Y-%m-%d").date()
                    
                    # Helper function to clean numeric strings (remove commas, spaces)
                    def clean_numeric_string(value):
                        if isinstance(value, str):
                            # Remove commas, spaces, and other non-numeric characters except decimal point
                            cleaned = value.replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '')
                            return cleaned
                        return str(value)
                    
                    # Convert to float (clean numeric strings first to handle commas)
                    try:
                        average_price_cleaned = clean_numeric_string(average_price)
                        current_price_cleaned = clean_numeric_string(current_price)
                        quantity_cleaned = clean_numeric_string(quantity)
                        value_at_cost_cleaned = clean_numeric_string(value_at_cost)
                        
                        average_price_float = float(average_price_cleaned)
                        current_price_float = float(current_price_cleaned)
                        quantity_float = float(quantity_cleaned)
                        value_at_cost_float = float(value_at_cost_cleaned)
                    except (ValueError, TypeError) as e:
                        error_msg = f"Stock {stock_idx + 1}: Invalid numeric values - avg_price: {average_price}, current_price: {current_price}, quantity: {quantity}, value_at_cost: {value_at_cost}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    # Note: We use the extracted value_at_cost directly - no validation against calculation
                    # The LLM should extract this value directly from the document, not calculate it
                    
                    # Extract current_value directly from document (do not calculate)
                    if current_value:
                        try:
                            current_value_cleaned = clean_numeric_string(current_value)
                            current_value_float = float(current_value_cleaned)
                        except (ValueError, TypeError):
                            # If current_value cannot be parsed, log error but don't calculate
                            current_value_float = 0.0
                    else:
                        # If not provided in document, set to 0 (do not calculate)
                        current_value_float = 0.0
                    
                    # Map owner name to family member ID
                    family_member_id = None
                    owner_name_lower = owner_name.lower().strip()
                    if owner_name_lower in ["self", "me", "myself", ""]:
                        family_member_id = None
                    elif owner_name_lower in family_members_map:
                        family_member_id = family_members_map[owner_name_lower]
                    else:
                        # Try partial match
                        for fm_name, fm_id in family_members_map.items():
                            if owner_name_lower in fm_name or fm_name in owner_name_lower:
                                family_member_id = fm_id
                                break
                                
                    # Check for duplicates before inserting
                    # Check by stock symbol (or name if symbol not available) - prevent duplicate stocks regardless of purchase date
                    normalized_symbol = stock_symbol.lower().strip() if stock_symbol else ""
                    normalized_name = stock_name.lower().strip() if stock_name else ""
                    
                    # Also create stock key from symbol and purchase date for backward compatibility
                    normalized_date = purchase_date.isoformat().strip().lower()
                    current_stock_key = f"{normalized_symbol}_{normalized_date}" if normalized_symbol else ""
                    
                    is_duplicate = False
                    
                    # First check: If stock symbol/name already exists (regardless of purchase date)
                    check_symbol = normalized_symbol if normalized_symbol else normalized_name
                    if check_symbol and check_symbol in existing_stock_symbols:
                        logger.info(f"Skipping stock - already exists in database: {stock_symbol or stock_name}")
                        print(f"Skipping stock - already exists in database: {stock_symbol or stock_name}")
                        skipped_stocks.append(f"{stock_symbol or stock_name}")
                        is_duplicate = True
                    
                    # Also check by symbol + purchase date for backward compatibility
                    if not is_duplicate and current_stock_key and current_stock_key in existing_stock_keys:
                        logger.info(f"Skipping stock - already exists in database: {stock_symbol} (Purchase Date: {purchase_date.isoformat()})")
                        print(f"Skipping stock - already exists in database: {stock_symbol} (Purchase Date: {purchase_date.isoformat()})")
                        skipped_stocks.append(f"{stock_symbol} (Purchase Date: {purchase_date.isoformat()})")
                        is_duplicate = True
                    
                    # Check against newly created assets in this session
                    if not is_duplicate:
                        for created_asset in created_assets:
                            if created_asset.get("type") == "stock":
                                created_symbol = str(created_asset.get("stock_symbol", "")).strip().lower()
                                created_name = str(created_asset.get("name", "")).strip().lower()
                                
                                # Check by symbol/name
                                if check_symbol:
                                    if (created_symbol and check_symbol == created_symbol) or (created_name and check_symbol == created_name):
                                        logger.info(f"Skipping stock - already added in this session: {stock_symbol or stock_name}")
                                        if (stock_symbol or stock_name) not in skipped_stocks:
                                            skipped_stocks.append(f"{stock_symbol or stock_name}")
                                        is_duplicate = True
                                        break
                                
                                # Also check by symbol + purchase date
                                created_date = created_asset.get("purchase_date", "")
                                if created_symbol and created_date and current_stock_key:
                                    created_key = f"{created_symbol}_{str(created_date).strip().lower()}"
                                    if current_stock_key == created_key:
                                        logger.info(f"Skipping stock - already added in this session: {stock_symbol} (Purchase Date: {purchase_date.isoformat()})")
                                        if f"{stock_symbol} (Purchase Date: {purchase_date.isoformat()})" not in skipped_stocks:
                                            skipped_stocks.append(f"{stock_symbol} (Purchase Date: {purchase_date.isoformat()})")
                                        is_duplicate = True
                                        break
                    
                    if is_duplicate:
                        continue
                    
                    # Build asset data
                    asset_data = {
                                    "name": stock_name,
                                    "type": "stock",
                                    "currency": currency,
                                    "stock_symbol": stock_symbol,
                                    "quantity": quantity_float,
                                    "purchase_price": average_price_float,  # Use average purchase price
                                    "purchase_date": purchase_date.isoformat(),
                                    "current_price": current_price_float,  # Use current market price
                                    "current_value": current_value_float,  # Current market value
                                    "is_active": True,
                                    "family_member_id": family_member_id
                    }
                    
                    # Create AssetCreate object
                    asset_create = AssetCreate(**{k: v for k, v in asset_data.items() if v is not None})
                    asset_create.model_validate_asset_fields()
                    
                    # Convert to dict
                    try:
                        asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
                    except AttributeError:
                        asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
                    
                    asset_dict["user_id"] = user_id
                    
                    # Convert decimals to strings
                    decimal_fields = ['quantity', 'purchase_price', 'current_price', 'current_value']
                    for field in decimal_fields:
                        if field in asset_dict and asset_dict[field] is not None:
                            asset_dict[field] = str(asset_dict[field])
                    
                    # Insert into database
                    logger.info(f"Inserting stock into database: {stock_name} ({stock_symbol})")
                    print(f"Inserting stock into database: {stock_name} ({stock_symbol})")
                    response = supabase_service.table("assets").insert(asset_dict).execute()
                    if response.data and len(response.data) > 0:
                        created_assets.append(response.data[0])
                        logger.info(f"Successfully created stock: {stock_name} ({stock_symbol})")
                        print(f"Successfully created stock: {stock_name} ({stock_symbol})")
                    else:
                        error_msg = f"Failed to create stock: {stock_name}"
                        logger.error(error_msg)
                        print(f"ERROR: {error_msg}")
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Stock {stock_idx + 1}: Error processing stock: {str(e)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)
                    logger.error(traceback.format_exc())
                    print(f"ERROR: {error_msg}")
        
        elif asset_type == "bank_account":
            logger = logging.getLogger(__name__)
            logger.info("=== BANK ACCOUNT PROCESSING STARTED ===")
            print("=== BANK ACCOUNT PROCESSING STARTED ===")
            
            if not _bank_account_llm_service.api_key:
                logger.error("GEMINI_API_KEY not found")
                print("ERROR: GEMINI_API_KEY not found")
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            logger.info("API key found, proceeding with bank account extraction")
            print("API key found, proceeding with bank account extraction")
            
            # Fetch family members for the user
            logger.info("Fetching family members...")
            print("Fetching family members...")
            family_members_list = []
            try:
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members_list = family_members_response.data if family_members_response.data else []
                logger.info(f"Found {len(family_members_list)} family members")
                print(f"Found {len(family_members_list)} family members")
            except Exception as e:
                logger.warning(f"Failed to fetch family members: {str(e)}")
                print(f"Warning: Failed to fetch family members: {str(e)}")
            
            # Format family members for the prompt and create mapping
            family_members_text = ""
            family_members_map = {}
            if family_members_list:
                family_members_lines = []
                for fm in family_members_list:
                    name = fm.get("name", "")
                    relationship = fm.get("relationship", "")
                    notes = fm.get("notes", "")
                    fm_id = fm.get("id", "")
                    if name:
                        line = f"- Name: {name}, Relationship: {relationship}"
                        if notes:
                            line += f", Notes: {notes}"
                        family_members_lines.append(line)
                        # Create mapping for owner name matching
                        if fm_id:
                            family_members_map[name.lower()] = str(fm_id)
                if family_members_lines:
                    family_members_text = "\n".join(family_members_lines)
            
            logger.info(f"Family members formatted. Text length: {len(family_members_text)}")
            print(f"Family members formatted. Text length: {len(family_members_text)}")
            
            # Combine all PDF pages into a single document
            complete_pdf_content = "\n\n--- Page Separator ---\n\n".join(pdf_pages)
            logger.info(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            print(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            
            # Process the complete PDF document
            all_bank_accounts = []
            
            logger = logging.getLogger(__name__)
            logger.info(f"Starting bank account extraction. PDF has {len(pdf_pages)} pages. Total content length: {len(complete_pdf_content)} chars")
            
            try:
                # Load prompt from file and replace placeholders with actual content
                logger.info("Loading prompt from file...")
                print("Loading prompt from file...")
                prompt_template = load_prompt("bank_accounts_prompt.txt")
                logger.info("Prompt loaded successfully")
                print("Prompt loaded successfully")
                
                logger.info("Formatting prompt with PDF content and family members...")
                print("Formatting prompt...")
                instruction_prompt = prompt_template.format(
                    page=complete_pdf_content,
                    family_members=family_members_text if family_members_text else "No family members have been added yet."
                )
                logger.info(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                print(f"Prompt formatted. Length: {len(instruction_prompt)} chars")

                with open("bank_account_instruction_prompt_debug.txt", "a", encoding="utf-8") as f:
                    f.write(instruction_prompt)
                    f.write("\n\n")
                
                # Use chat function from LLMService - LLM will return a JSON object/array
                logger.info("Calling LLM for bank account extraction...")
                print("Calling LLM for bank account extraction...")
                
                text_response = await _bank_account_llm_service.chat(
                    system_prompt="<Role>You are an helpful financial assistant that extracts bank account information from a document.</Role>",
                    message=instruction_prompt
                )
                
                logger.info(f"LLM response received. Length: {len(text_response) if text_response else 0}, First 100 chars: {text_response[:100] if text_response else 'None'}")
                print(f"LLM response received. Length: {len(text_response) if text_response else 0}")
                print(f"LLM response (first 200 chars): {text_response[:200] if text_response else 'None'}")
                
                if not text_response:
                    logger.error("No response from LLM")
                    print("ERROR: No response from LLM")
                    errors.append("No response from LLM")
                elif text_response.startswith("Error:"):
                    logger.error(f"LLM returned error: {text_response}")
                    print(f"ERROR: LLM returned error: {text_response}")
                    errors.append(f"LLM returned error: {text_response}")
                else:
                    logger.info("Processing LLM response...")
                    print("Processing LLM response...")
                    # Parse JSON response - LLM returns a JSON object or array
                    try:
                        # Clean the response - remove markdown code blocks if present
                        # Even though prompt says "only JSON", LLM sometimes wraps it in markdown
                        logger.info("Cleaning JSON response...")
                        print("Cleaning JSON response...")
                        cleaned_response = clean_json_response(text_response)
                        
                        # Debug: Log cleaned response
                        logger.info(f"Cleaned response (first 200 chars): {cleaned_response[:200]}")
                        print(f"Cleaned response (first 200 chars): {cleaned_response[:200]}")
                        
                        # Parse the JSON response
                        logger.info("Parsing JSON...")
                        print("Parsing JSON...")
                        bank_account_obj = json.loads(cleaned_response)
                        logger.info(f"JSON parsed successfully. Type: {type(bank_account_obj).__name__}")
                        print(f"JSON parsed successfully. Type: {type(bank_account_obj).__name__}")
                        
                        # Debug: Log what we received after parsing
                        logger = logging.getLogger(__name__)
                        if isinstance(bank_account_obj, dict):
                            logger.info(f"Parsed JSON object with keys: {list(bank_account_obj.keys())}, has Bank Name: {bool(bank_account_obj.get('Bank Name'))}, has Account Number: {bool(bank_account_obj.get('Account Number'))}")
                        elif isinstance(bank_account_obj, list):
                            logger.info(f"Parsed JSON array with {len(bank_account_obj)} items")
                        else:
                            logger.info(f"Parsed JSON - type: {type(bank_account_obj).__name__}, value: {bank_account_obj}")
                        
                        # Handle different response formats
                        if isinstance(bank_account_obj, list):
                            logger.info(f"Processing list with {len(bank_account_obj)} items")
                            print(f"Processing list with {len(bank_account_obj)} items")
                            # If it's a list, extend with all items (filter out empty objects)
                            for idx, item in enumerate(bank_account_obj):
                                logger.info(f"Processing item {idx + 1}: {item}")
                                print(f"Processing item {idx + 1}: {item}")
                                if item and isinstance(item, dict) and len(item) > 0:
                                    # Check if it has required fields
                                    if item.get("Bank Name") or item.get("Account Number"):
                                        all_bank_accounts.append(item)
                                        logger.info(f"Added bank account from list: {item.get('Bank Name', 'Unknown')}")
                                        print(f"Added bank account from list: {item.get('Bank Name', 'Unknown')}")
                                    else:
                                        logger.warning(f"Item {idx + 1} missing required fields: {item}")
                                        print(f"Item {idx + 1} missing required fields: {item}")
                                else:
                                    logger.warning(f"Item {idx + 1} is not a valid dict: {item}")
                                    print(f"Item {idx + 1} is not a valid dict: {item}")
                            logger.info(f"Total bank accounts collected: {len(all_bank_accounts)}")
                            print(f"Total bank accounts collected: {len(all_bank_accounts)}")
                        elif isinstance(bank_account_obj, dict):
                            # If it's a single object, check if it's empty (prompt says return empty array if no accounts)
                            if len(bank_account_obj) > 0:
                                # Check if it has required fields (not just an empty object)
                                if bank_account_obj.get("Bank Name") or bank_account_obj.get("Account Number"):
                                    all_bank_accounts.append(bank_account_obj)
                                    logger.info(f"Added bank account: {bank_account_obj.get('Bank Name', 'Unknown')}")
                                else:
                                    logger.info(f"Received object without required fields, skipping: {bank_account_obj}")
                            else:
                                logger.info(f"Received empty JSON object (no bank accounts in document), skipping")
                        else:
                            logger.warning(f"Unexpected JSON response type: {type(bank_account_obj)}, value: {bank_account_obj}")
                        
                    except json.JSONDecodeError as e:
                        errors.append(f"Invalid JSON response from LLM: {str(e)}")
                        logger = logging.getLogger(__name__)
                        logger.error(f"JSON decode error. Raw response: {text_response[:500]}")
                    except Exception as e:
                        errors.append(f"Error parsing response: {str(e)}")
                        logger = logging.getLogger(__name__)
                        logger.error(f"Parse error: {str(e)}")
            
            except Exception as e:
                error_msg = f"Error processing PDF: {str(e)}"
                errors.append(error_msg)
                logger = logging.getLogger(__name__)
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                # Also print to console for immediate visibility
                print(f"ERROR in bank account processing: {error_msg}")
                print(traceback.format_exc())
            
            # Remove duplicates based on account number (keep first occurrence)
            logger.info(f"Before deduplication: {len(all_bank_accounts)} bank accounts")
            print(f"Before deduplication: {len(all_bank_accounts)} bank accounts")
            seen_account_numbers = set()
            unique_bank_accounts = []
            for bank_account in all_bank_accounts:
                account_number = bank_account.get("Account Number") or bank_account.get("account_number") or bank_account.get("Account No") or bank_account.get("Account #")
                if account_number:
                    # Normalize account number for comparison (case-insensitive, strip whitespace)
                    normalized_account_number = str(account_number).strip().lower()
                    if normalized_account_number not in seen_account_numbers:
                        seen_account_numbers.add(normalized_account_number)
                        unique_bank_accounts.append(bank_account)
                    else:
                        logger.info(f"Skipping duplicate account number: {account_number}")
                        print(f"Skipping duplicate account number: {account_number}")
                else:
                    # If no account number, keep it (shouldn't happen based on validation, but safe to include)
                    unique_bank_accounts.append(bank_account)
            
            all_bank_accounts = unique_bank_accounts
            logger.info(f"After deduplication: {len(all_bank_accounts)} unique bank accounts")
            print(f"After deduplication: {len(all_bank_accounts)} unique bank accounts")
            
            # Fetch existing bank accounts from database to check for duplicates
            existing_bank_accounts = []
            existing_account_numbers = set()
            try:
                logger.info("Fetching existing bank accounts from database...")
                print("Fetching existing bank accounts from database...")
                existing_assets_response = supabase_service.table("assets").select("account_number, bank_name").eq("user_id", user_id).eq("type", "bank_account").eq("is_active", True).execute()
                existing_bank_accounts = existing_assets_response.data if existing_assets_response.data else []
                
                # Normalize existing account numbers for comparison
                for existing_account in existing_bank_accounts:
                    existing_account_num = existing_account.get("account_number")
                    if existing_account_num:
                        normalized = str(existing_account_num).strip().lower()
                        existing_account_numbers.add(normalized)
                
                logger.info(f"Found {len(existing_bank_accounts)} existing bank accounts in database")
                print(f"Found {len(existing_bank_accounts)} existing bank accounts in database")
            except Exception as e:
                logger.warning(f"Error fetching existing bank accounts: {str(e)}")
                print(f"Warning: Error fetching existing bank accounts: {str(e)}")
                # Continue processing even if fetch fails
            
            # Process all collected bank accounts
            logger.info(f"Starting to process {len(all_bank_accounts)} bank accounts for database insertion")
            print(f"Starting to process {len(all_bank_accounts)} bank accounts for database insertion")
            created_assets = []
            skipped_account_numbers = []  # Track account numbers that were skipped due to duplicates
            for ba_idx, ba_data in enumerate(all_bank_accounts):
                try:
                    # Get currency from market
                    asset_market = market or "india"
                    currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                    
                    # Extract and validate fields (handle multiple possible key names)
                    bank_name = ba_data.get("Bank Name") or ba_data.get("bank_name") or ba_data.get("Bank") or "Unknown Bank"
                    current_balance = ba_data.get("Current Balance") or ba_data.get("current_balance") or ba_data.get("Balance") or ba_data.get("balance") or ba_data.get("Available Balance") or ba_data.get("Account Balance")
                    account_number = ba_data.get("Account Number") or ba_data.get("account_number") or ba_data.get("Account No") or ba_data.get("Account #")
                    owner_name = ba_data.get("Owner Name") or ba_data.get("owner_name") or "self"
                    
                    # Validate required fields
                    if not bank_name or current_balance is None or not account_number:
                        error_msg = f"BA {ba_idx + 1}: Missing required fields (bank_name, current_balance, or account_number)"
                        errors.append(error_msg)
                        continue
                                
                    # Helper function to clean numeric strings (remove commas, spaces, currency symbols)
                    def clean_numeric_string(value):
                        if isinstance(value, str):
                            # Remove commas, spaces, and other non-numeric characters except decimal point
                            cleaned = value.replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '')
                            return cleaned
                        return str(value)
                    
                    # Convert balance to float (clean numeric strings first)
                    try:
                        balance_cleaned = clean_numeric_string(current_balance)
                        balance_float = float(balance_cleaned)
                    except (ValueError, TypeError) as e:
                        error_msg = f"BA {ba_idx + 1}: Invalid balance value: {current_balance}"
                        errors.append(error_msg)
                        continue
                    
                    # Map owner name to family member ID
                    family_member_id = None
                    owner_name_lower = owner_name.lower().strip()
                    if owner_name_lower in ["self", "me", "myself", ""]:
                        family_member_id = None
                    elif owner_name_lower in family_members_map:
                        family_member_id = family_members_map[owner_name_lower]
                    else:
                        # Try partial match
                        for fm_name, fm_id in family_members_map.items():
                            if owner_name_lower in fm_name or fm_name in owner_name_lower:
                                family_member_id = fm_id
                                break
                    
                    # Build asset data
                    asset_data = {
                        "name": bank_name,
                        "type": "bank_account",
                        "currency": currency,
                        "bank_name": bank_name,
                        "current_value": balance_float,  # Current balance
                        "is_active": True,
                        "family_member_id": family_member_id
                    }
                    
                    # Add account number
                    if account_number:
                        asset_data["account_number"] = account_number
                    
                    # Create AssetCreate object
                    asset_create = AssetCreate(**{k: v for k, v in asset_data.items() if v is not None})
                    asset_create.model_validate_asset_fields()
                    
                    # Convert to dict
                    try:
                        asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
                    except AttributeError:
                        asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
                    
                    asset_dict["user_id"] = user_id
                    
                    # Convert decimals to strings
                    if 'current_value' in asset_dict and asset_dict['current_value'] is not None:
                        asset_dict['current_value'] = str(asset_dict['current_value'])
                    
                    # Check for duplicates before inserting
                    # First, check against existing accounts in database
                    normalized_account_number = str(account_number).strip().lower() if account_number else ""
                    is_duplicate = False
                    
                    if normalized_account_number and normalized_account_number in existing_account_numbers:
                        logger.info(f"Skipping bank account - account number already exists in database: {account_number}")
                        print(f"Skipping bank account - account number already exists in database: {account_number}")
                        skipped_account_numbers.append(account_number)
                        is_duplicate = True
                    
                    # Also check against newly created assets in this session
                    if not is_duplicate:
                        for created_asset in created_assets:
                            if created_asset.get("type") == "bank_account":
                                created_account_number = created_asset.get("account_number", "")
                                created_bank_name = created_asset.get("bank_name", "")
                                # Match by account number (normalized)
                                if account_number and created_account_number:
                                    created_normalized = str(created_account_number).strip().lower()
                                    if normalized_account_number == created_normalized:
                                        logger.info(f"Skipping bank account - duplicate in current session: {account_number}")
                                        print(f"Skipping bank account - duplicate in current session: {account_number}")
                                        if account_number not in skipped_account_numbers:
                                            skipped_account_numbers.append(account_number)
                                        is_duplicate = True
                                        break
                    
                    if is_duplicate:
                        continue
                    
                    # Insert into database
                    logger.info(f"Inserting bank account into database: {bank_name}, account_number={account_number}")
                    print(f"Inserting bank account into database: {bank_name}")
                    response = supabase_service.table("assets").insert(asset_dict).execute()
                    if response.data and len(response.data) > 0:
                        created_assets.append(response.data[0])
                        logger.info(f"Successfully created bank account: {bank_name} (ID: {response.data[0].get('id')})")
                        print(f"Successfully created bank account: {bank_name}")
                    else:
                        error_msg = f"Failed to create bank account: {bank_name}"
                        logger.error(error_msg)
                        print(f"ERROR: {error_msg}")
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"BA {ba_idx + 1}: Error processing bank account: {str(e)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)
                    errors.append(error_msg)
        
        elif asset_type == "mutual_fund":
            logger = logging.getLogger(__name__)
            logger.info("=== MUTUAL FUND PROCESSING STARTED ===")
            print("=== MUTUAL FUND PROCESSING STARTED ===")
            
            if not _mutual_fund_llm_service.api_key:
                logger.error("GEMINI_API_KEY not found")
                print("ERROR: GEMINI_API_KEY not found")
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            logger.info("API key found, proceeding with mutual fund extraction")
            print("API key found, proceeding with mutual fund extraction")
            
            # Fetch family members for the user
            logger.info("Fetching family members...")
            print("Fetching family members...")
            family_members_list = []
            try:
                family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
                family_members_list = family_members_response.data if family_members_response.data else []
                logger.info(f"Found {len(family_members_list)} family members")
                print(f"Found {len(family_members_list)} family members")
            except Exception as e:
                logger.warning(f"Failed to fetch family members: {str(e)}")
                print(f"Warning: Failed to fetch family members: {str(e)}")
            
            # Format family members for the prompt and create mapping
            family_members_text = ""
            family_members_map = {}
            if family_members_list:
                family_members_lines = []
                for fm in family_members_list:
                    name = fm.get("name", "")
                    relationship = fm.get("relationship", "")
                    notes = fm.get("notes", "")
                    fm_id = fm.get("id", "")
                    if name:
                        line = f"- Name: {name}, Relationship: {relationship}"
                        if notes:
                            line += f", Notes: {notes}"
                        family_members_lines.append(line)
                        # Create mapping for owner name matching
                        if fm_id:
                            family_members_map[name.lower()] = str(fm_id)
                if family_members_lines:
                    family_members_text = "\n".join(family_members_lines)
            
            logger.info(f"Family members formatted. Text length: {len(family_members_text)}")
            print(f"Family members formatted. Text length: {len(family_members_text)}")
            
            # Fetch existing mutual funds to prevent duplicates
            existing_mutual_funds = []
            existing_fund_codes = set()
            try:
                existing_assets_response = supabase_service.table("assets").select("mutual_fund_code, name, fund_house").eq("user_id", user_id).eq("type", "mutual_fund").eq("is_active", True).execute()
                existing_mutual_funds = existing_assets_response.data if existing_assets_response.data else []
                # Create a set of normalized fund codes for quick lookup
                for fund in existing_mutual_funds:
                    fund_code = fund.get("mutual_fund_code", "")
                    if fund_code:
                        existing_fund_codes.add(fund_code.lower().strip())
                logger.info(f"Found {len(existing_mutual_funds)} existing mutual funds in database")
                print(f"Found {len(existing_mutual_funds)} existing mutual funds in database")
            except Exception as e:
                logger.warning(f"Failed to fetch existing mutual funds: {str(e)}")
                print(f"Warning: Failed to fetch existing mutual funds: {str(e)}")
            
            # Combine all PDF pages into a single document
            complete_pdf_content = "\n\n--- Page Separator ---\n\n".join(pdf_pages)
            logger.info(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            print(f"Combined PDF content. Total length: {len(complete_pdf_content)} chars")
            
            # Process the complete PDF document
            all_mutual_funds = []
            
            logger.info(f"Starting mutual fund extraction. PDF has {len(pdf_pages)} pages. Total content length: {len(complete_pdf_content)} chars")
            
            try:
                # Load prompt from file and replace placeholders with actual content
                logger.info("Loading prompt from file...")
                print("Loading prompt from file...")
                prompt_template = load_prompt("mutual_funds_prompt.txt")
                logger.info("Prompt loaded successfully")
                print("Prompt loaded successfully")
                
                logger.info("Formatting prompt with PDF content and family members...")
                print("Formatting prompt...")
                instruction_prompt = prompt_template.format(
                    page=complete_pdf_content,
                    family_members=family_members_text if family_members_text else "No family members have been added yet."
                )
                logger.info(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                print(f"Prompt formatted. Length: {len(instruction_prompt)} chars")
                
                # Use chat function from LLMService - LLM will return a JSON object/array
                logger.info("Calling LLM for mutual fund extraction...")
                print("Calling LLM for mutual fund extraction...")
                logger.info("WAITING for LLM response - blocking until complete...")
                print("WAITING for LLM response - blocking until complete...")
                logger.info("NOTE: Other requests may be processed concurrently while waiting for LLM (this is normal async behavior)")
                
                # Track timing for LLM call
                import time
                start_time = time.time()
                print("LLM call started - this may take 30-120 seconds for large PDFs...")
                
                text_response = await _mutual_fund_llm_service.chat(
                    system_prompt="<Role>You are a helpful financial assistant that extracts mutual fund and ETF information from a document.</Role>",
                    message=instruction_prompt,
                    max_tokens=30000,
                    temperature=0.7
                )
                
                end_time = time.time()
                duration = end_time - start_time
                logger.info(f"LLM call completed in {duration:.2f} seconds.")
                print(f"LLM call completed in {duration:.2f} seconds.")
                
                logger.info("LLM response received - proceeding with processing...")
                print("LLM response received - proceeding with processing...")
                print(f"Text response: {text_response}")
                logger.info(f"LLM response type: {type(text_response)}, length: {len(text_response) if text_response else 0}")
                
                if not text_response:
                    errors.append("No response from LLM")
                    logger.error("LLM returned empty response")
                elif text_response.startswith("Error:"):
                    errors.append(f"LLM returned error: {text_response}")
                    logger.error(f"LLM error: {text_response}")
                    error_lower = text_response.lower()
                    if ("503" in text_response or "unavailable" in error_lower or 
                        "overloaded" in error_lower or "service unavailable" in error_lower):
                        message = f"Failed to extract assets from PDF: The AI service is temporarily unavailable. Please try again in a few moments. Details: {text_response}"
                    elif "Could not extract response" in text_response:
                        message = f"Failed to extract assets from PDF: The AI service returned an unexpected response format. This may be due to service overload. Details: {text_response}"
                    else:
                        message = f"Failed to extract assets from PDF due to an AI processing error. Details: {text_response}"
                    return {
                        "success": False,
                        "created_count": 0,
                        "created_assets": [],
                        "errors": errors,
                        "message": message,
                        "skipped_account_numbers": [],
                        "skipped_fixed_deposits": [],
                        "skipped_stocks": [],
                        "skipped_mutual_funds": []
                    }
                else:
                    logger.info("Processing LLM response...")
                    print("Processing LLM response...")
                    # Parse JSON response - LLM returns a JSON object or array
                    try:
                        # Clean the response - remove markdown code blocks if present
                        logger.info("Cleaning JSON response...")
                        print("Cleaning JSON response...")
                        cleaned_response = clean_json_response(text_response)
                        
                        # Debug: Log cleaned response
                        logger.info(f"Cleaned response (first 200 chars): {cleaned_response[:200]}")
                        print(f"Cleaned response (first 200 chars): {cleaned_response[:200]}")
                        
                        # Parse the JSON response
                        logger.info("Parsing JSON...")
                        print("Parsing JSON...")
                        try:
                            mutual_funds_list = json.loads(cleaned_response)
                            if not isinstance(mutual_funds_list, list):
                                # If it's a single object, wrap it in a list
                                if isinstance(mutual_funds_list, dict):
                                    mutual_funds_list = [mutual_funds_list]
                                else:
                                    mutual_funds_list = []
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {str(e)}")
                            logger.error(f"Cleaned response (first 500 chars): {cleaned_response[:500]}")
                            logger.error(f"Raw response (first 500 chars): {text_response[:500]}")
                            print(f"ERROR: JSON decode failed. Error: {str(e)}")
                            print(f"Cleaned response (first 500 chars): {cleaned_response[:500]}")
                            
                            # Try to extract JSON from the response if it's partially valid
                            try:
                                # First, try to find the first complete JSON array
                                json_start = cleaned_response.find('[')
                                if json_start != -1:
                                    json_substring = cleaned_response[json_start:]
                                    bracket_count = 0
                                    in_string = False
                                    escape_next = False
                                    array_end = -1
                                    
                                    for i, char in enumerate(json_substring):
                                        if escape_next: 
                                            escape_next = False
                                            continue
                                        if char == '\\': 
                                            escape_next = True
                                            continue
                                        if char == '"' and not escape_next: 
                                            in_string = not in_string
                                            continue
                                        if not in_string:
                                            if char == '[': 
                                                bracket_count += 1
                                            elif char == ']':
                                                bracket_count -= 1
                                                if bracket_count == 0: 
                                                    array_end = i + 1
                                                    break
                                    
                                    if array_end > 0:
                                        first_array = json_substring[:array_end]
                                        mutual_funds_list = json.loads(first_array)
                                        if not isinstance(mutual_funds_list, list):
                                            if isinstance(mutual_funds_list, dict):
                                                mutual_funds_list = [mutual_funds_list]
                                            else:
                                                mutual_funds_list = []
                                    else:
                                        # If no complete array found, try to extract individual objects
                                        mutual_funds_list = []
                                        i = 0
                                        while i < len(json_substring):
                                            # Find next '{'
                                            obj_start = json_substring.find('{', i)
                                            if obj_start == -1:
                                                break
                                            
                                            # Find matching '}'
                                            bracket_count = 0
                                            in_string = False
                                            escape_next = False
                                            obj_end = -1
                                            
                                            for j in range(obj_start, len(json_substring)):
                                                char = json_substring[j]
                                                if escape_next:
                                                    escape_next = False
                                                    continue
                                                if char == '\\':
                                                    escape_next = True
                                                    continue
                                                if char == '"' and not escape_next:
                                                    in_string = not in_string
                                                    continue
                                                if not in_string:
                                                    if char == '{':
                                                        bracket_count += 1
                                                    elif char == '}':
                                                        bracket_count -= 1
                                                        if bracket_count == 0:
                                                            obj_end = j + 1
                                                            break
                                            
                                            if obj_end > obj_start:
                                                try:
                                                    obj_str = json_substring[obj_start:obj_end]
                                                    obj = json.loads(obj_str)
                                                    # Validate that it has required fields
                                                    if isinstance(obj, dict) and (obj.get("Fund Name") or obj.get("Fund Code") or obj.get("fund_name") or obj.get("fund_code")):
                                                        mutual_funds_list.append(obj)
                                                except:
                                                    pass
                                                i = obj_end
                                            else:
                                                break
                                else:
                                    logger.warning("Could not find any JSON array or object start in response")
                                    print("WARNING: Could not find any JSON array or object start in response")
                                    mutual_funds_list = []
                            except Exception as fix_error:
                                logger.error(f"Failed to extract valid JSON from partial response: {str(fix_error)}")
                                print(f"Failed to extract valid JSON: {str(fix_error)}")
                                mutual_funds_list = []
                        
                        logger.info(f"Parsed {len(mutual_funds_list)} mutual funds from LLM response")
                        print(f"Parsed {len(mutual_funds_list)} mutual funds from LLM response")
                        
                        # Process each mutual fund from the parsed list
                        for mf_data in mutual_funds_list:
                            if not isinstance(mf_data, dict):
                                continue
                            all_mutual_funds.append(mf_data)
                            logger.info(f"Added mutual fund: {mf_data.get('Fund Name', 'Unknown')}")
                            print(f"Added mutual fund: {mf_data.get('Fund Name', 'Unknown')}")
                        
                        logger.info(f"Total mutual funds collected: {len(all_mutual_funds)}")
                        print(f"Total mutual funds collected: {len(all_mutual_funds)}")
                        
                        # Deduplicate based on fund code
                        seen_fund_codes = set()
                        unique_mutual_funds = []
                        for mf in all_mutual_funds:
                            fund_code = mf.get("Fund Code") or mf.get("fund_code") or mf.get("Scheme Code") or mf.get("ISIN") or mf.get("Code") or mf.get("code")
                            if fund_code:
                                fund_code_normalized = fund_code.lower().strip()
                                if fund_code_normalized not in seen_fund_codes:
                                    seen_fund_codes.add(fund_code_normalized)
                                    unique_mutual_funds.append(mf)
                            else:
                                # If no fund code, include it (but this shouldn't happen per prompt requirements)
                                unique_mutual_funds.append(mf)
                        
                        logger.info(f"After deduplication: {len(unique_mutual_funds)} unique mutual funds")
                        print(f"After deduplication: {len(unique_mutual_funds)} unique mutual funds")
                        all_mutual_funds = unique_mutual_funds
                        
                    except json.JSONDecodeError as e:
                        error_msg = f"Invalid JSON response from LLM: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"JSON decode error: {error_msg}")
                        logger.error(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
                        logger.error(f"Raw response (first 500 chars): {text_response[:500]}")
                        print(f"ERROR: JSON decode failed. Error: {str(e)}")
                        print(f"Cleaned response (first 500 chars): {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}")
            
            except Exception as e:
                error_msg = f"Error processing mutual funds: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                import traceback
                logger.error(traceback.format_exc())
                print(f"ERROR: {error_msg}")
            
            # Process all collected mutual funds for database insertion
            skipped_mutual_funds = []
            logger.info(f"Starting to process {len(all_mutual_funds)} mutual funds for database insertion")
            print(f"Starting to process {len(all_mutual_funds)} mutual funds for database insertion")
            
            for mf_idx, mf_data in enumerate(all_mutual_funds):
                try:
                    # Get currency from market
                    asset_market = market or "india"
                    currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                    
                    # Extract and validate fields (handle multiple possible key names)
                    fund_name = mf_data.get("Fund Name") or mf_data.get("fund_name") or mf_data.get("Name") or mf_data.get("Scheme Name") or "Unknown Fund"
                    fund_code = mf_data.get("Fund Code") or mf_data.get("fund_code") or mf_data.get("Scheme Code") or mf_data.get("ISIN") or mf_data.get("Code") or mf_data.get("code")
                    fund_house = mf_data.get("Fund House") or mf_data.get("fund_house") or mf_data.get("AMC") or mf_data.get("Asset Management Company")
                    units = mf_data.get("Units") or mf_data.get("units") or mf_data.get("No. of Units") or mf_data.get("Quantity") or mf_data.get("quantity")
                    nav = mf_data.get("NAV") or mf_data.get("nav") or mf_data.get("Net Asset Value") or mf_data.get("Current NAV")
                    purchase_date_str = mf_data.get("Purchase Date") or mf_data.get("purchase_date") or mf_data.get("Date of Investment") or mf_data.get("Investment Date")
                    value_at_cost = mf_data.get("Value at Cost") or mf_data.get("value_at_cost") or mf_data.get("Amount Invested") or mf_data.get("Total Invested") or mf_data.get("Investment Amount") or mf_data.get("Purchase Value")
                    current_value = mf_data.get("Current Value") or mf_data.get("Current Worth") or mf_data.get("Market Value") or mf_data.get("current_value")
                    owner_name = mf_data.get("Owner Name") or mf_data.get("owner_name") or "self"
                    
                    # Validate required fields (fund_code is required)
                    if not fund_name or not fund_code or units is None:
                        error_msg = f"MF {mf_idx + 1}: Missing required fields (fund_name, fund_code, or units)"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    # Helper function to clean numeric strings (remove commas, spaces, currency symbols)
                    def clean_numeric_string(value):
                        if isinstance(value, str):
                            # Remove commas, spaces, and other non-numeric characters except decimal point
                            cleaned = value.replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '')
                            return cleaned
                        return str(value)
                    
                    # Convert units to float (clean numeric strings first)
                    try:
                        units_cleaned = clean_numeric_string(units)
                        units_float = float(units_cleaned)
                    except (ValueError, TypeError) as e:
                        error_msg = f"MF {mf_idx + 1}: Invalid units value: {units}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    # Convert NAV to float if provided (clean numeric strings first)
                    nav_float = None
                    if nav:
                        try:
                            nav_cleaned = clean_numeric_string(nav)
                            nav_float = float(nav_cleaned)
                        except (ValueError, TypeError):
                            pass
                    
                    # Convert value_at_cost to float if provided (clean numeric strings first)
                    value_at_cost_float = None
                    if value_at_cost:
                        try:
                            value_at_cost_cleaned = clean_numeric_string(value_at_cost)
                            value_at_cost_float = float(value_at_cost_cleaned)
                        except (ValueError, TypeError):
                            pass
                    
                    # Convert current_value to float if provided (clean numeric strings first)
                    current_value_float = None
                    if current_value:
                        try:
                            current_value_cleaned = clean_numeric_string(current_value)
                            current_value_float = float(current_value_cleaned)
                        except (ValueError, TypeError):
                            current_value_float = 0.0
                    else:
                        # If not provided, set to 0 (do not calculate)
                        current_value_float = 0.0
                    
                    # Parse purchase date if provided
                    purchase_date = None
                    if purchase_date_str:
                        try:
                            purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d").date()
                        except:
                            try:
                                purchase_date = datetime.strptime(purchase_date_str, "%d-%m-%Y").date()
                            except:
                                try:
                                    purchase_date = datetime.strptime(purchase_date_str, "%d/%m/%Y").date()
                                except:
                                    pass
                    
                    # Map owner name to family member ID
                    family_member_id = None
                    owner_name_lower = owner_name.lower().strip()
                    if owner_name_lower in ["self", "me", "myself", ""]:
                        family_member_id = None
                    elif owner_name_lower in family_members_map:
                        family_member_id = family_members_map[owner_name_lower]
                    else:
                        # Try partial match
                        for fm_name, fm_id in family_members_map.items():
                            if owner_name_lower in fm_name or fm_name in owner_name_lower:
                                family_member_id = fm_id
                                break
                    
                    # Check for duplicates before processing
                    is_duplicate = False
                    fund_code_normalized = fund_code.lower().strip()
                    
                    # Check in existing mutual funds from database
                    if fund_code_normalized in existing_fund_codes:
                        logger.info(f"Skipping mutual fund - already exists in database: {fund_name} ({fund_code})")
                        print(f"Skipping mutual fund - already exists in database: {fund_name} ({fund_code})")
                        skipped_mutual_funds.append(f"{fund_name} ({fund_code})")
                        is_duplicate = True
                    
                    # Check in newly created assets in this session
                    if not is_duplicate:
                        for created_asset in created_assets:
                            if created_asset.get("type") == "mutual_fund":
                                created_code = created_asset.get("mutual_fund_code", "")
                                if created_code and fund_code_normalized == created_code.lower().strip():
                                    logger.info(f"Skipping mutual fund - duplicate in current session: {fund_name} ({fund_code})")
                                    print(f"Skipping mutual fund - duplicate in current session: {fund_name} ({fund_code})")
                                    if f"{fund_name} ({fund_code})" not in skipped_mutual_funds:
                                        skipped_mutual_funds.append(f"{fund_name} ({fund_code})")
                                    is_duplicate = True
                                    break
                    
                    if is_duplicate:
                        continue
                    
                    # Build asset data
                    asset_data = {
                        "name": fund_name,
                        "type": "mutual_fund",
                        "currency": currency,
                        "mutual_fund_code": fund_code,
                        "units": units_float,
                        "is_active": True,
                        "family_member_id": family_member_id
                    }
                    
                    # Add optional fields if provided
                    if fund_house:
                        asset_data["fund_house"] = fund_house
                    if nav_float is not None:
                        asset_data["nav"] = nav_float
                    if purchase_date:
                        asset_data["nav_purchase_date"] = purchase_date.isoformat()
                    if current_value_float is not None:
                        asset_data["current_value"] = current_value_float
                    
                    # Store value_at_cost in notes field as JSON (since database doesn't have a separate field)
                    # Format: {"value_at_cost": "1234.56"}
                    if value_at_cost_float is not None:
                        notes_data = {"value_at_cost": str(value_at_cost_float)}
                        asset_data["notes"] = json.dumps(notes_data)
                    
                    # Create AssetCreate object
                    asset_create = AssetCreate(**{k: v for k, v in asset_data.items() if v is not None})
                    asset_create.model_validate_asset_fields()
                    
                    # Convert to dict
                    try:
                        asset_dict = asset_create.model_dump(exclude_unset=True, exclude_none=True, mode='json')
                    except AttributeError:
                        asset_dict = asset_create.dict(exclude_unset=True, exclude_none=True)
                    
                    asset_dict["user_id"] = user_id
                    
                    # Convert decimals to strings
                    decimal_fields = ['units', 'nav', 'current_value']
                    for field in decimal_fields:
                        if field in asset_dict and asset_dict[field] is not None:
                            asset_dict[field] = str(asset_dict[field])
                    
                    # Insert into database
                    logger.info(f"Inserting mutual fund into database: {fund_name} ({fund_code})")
                    print(f"Inserting mutual fund into database: {fund_name} ({fund_code})")
                    response = supabase_service.table("assets").insert(asset_dict).execute()
                    if response.data and len(response.data) > 0:
                        created_assets.append(response.data[0])
                        # Add to existing_fund_codes to prevent duplicates in subsequent processing
                        existing_fund_codes.add(fund_code_normalized)
                        logger.info(f"Successfully created mutual fund: {fund_name} ({fund_code})")
                        print(f"Successfully created mutual fund: {fund_name} ({fund_code})")
                    else:
                        error_msg = f"Failed to create mutual fund: {fund_name}"
                        logger.error(error_msg)
                        print(f"ERROR: {error_msg}")
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Mutual fund {mf_idx + 1}: Error processing mutual fund: {str(e)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    print(f"ERROR: {error_msg}")
                    errors.append(error_msg)
        
        else:
            errors.append(f"Unsupported asset type: {asset_type}")
        
        if not created_assets and not errors:
            if asset_type == "fixed_deposit":
                errors.append("No fixed deposits found in the PDF")
            elif asset_type == "stock":
                errors.append("No stocks found in the PDF")
            elif asset_type == "bank_account":
                errors.append("No bank accounts found in the PDF")
            elif asset_type == "mutual_fund":
                errors.append("No mutual funds found in the PDF")
            else:
                errors.append(f"No {asset_type} found in the PDF")
        
        # Build response message
        message = ""
        if asset_type == "bank_account" and skipped_account_numbers:
            skipped_msg = f"Bank account(s) with the following account number(s) were not added because they already exist in your portfolio: {', '.join(skipped_account_numbers)}"
            if created_assets:
                message = f"Successfully added {len(created_assets)} bank account(s) from PDF. {skipped_msg}"
            else:
                message = f"No new bank accounts were added. {skipped_msg}"
        elif asset_type == "fixed_deposit" and skipped_fd_keys:
            skipped_msg = f"Fixed deposit(s) with the following details were not added because they already exist in your portfolio: {', '.join(skipped_fd_keys)}"
            if created_assets:
                message = f"Successfully added {len(created_assets)} fixed deposit(s) from PDF. {skipped_msg}"
            else:
                message = f"No new fixed deposits were added. {skipped_msg}"
        elif asset_type == "stock" and skipped_stocks:
            skipped_msg = f"Stock(s) with the following details were not added because they already exist in your portfolio: {', '.join(skipped_stocks)}"
            if created_assets:
                message = f"Successfully added {len(created_assets)} stock(s) from PDF. {skipped_msg}"
            else:
                message = f"No new stocks were added. {skipped_msg}"
        elif asset_type == "mutual_fund" and skipped_mutual_funds:
            skipped_msg = f"Mutual fund(s) with the following details were not added because they already exist in your portfolio: {', '.join(skipped_mutual_funds)}"
            if created_assets:
                message = f"Successfully added {len(created_assets)} mutual fund(s) from PDF. {skipped_msg}"
            else:
                message = f"No new mutual funds were added. {skipped_msg}"
        elif created_assets:
            message = f"Successfully added {len(created_assets)} {asset_type}(s) from PDF"
        else:
            # Check if there were errors (like LLM API errors)
            if errors:
                # Extract the main error message
                main_error = errors[0] if errors else "Unknown error"
                # Check if it's an LLM service error
                if "LLM returned error" in main_error or "503" in main_error or "UNAVAILABLE" in main_error:
                    message = f"Failed to extract assets from PDF: The AI service is temporarily unavailable. Please try again in a few moments. Error: {main_error}"
                else:
                    message = f"Failed to extract assets from PDF: {main_error}"
            else:
                message = "No assets could be extracted from the PDF"
        
        return {
            "success": len(created_assets) > 0,
            "created_count": len(created_assets),
            "created_assets": created_assets,
            "errors": errors,
            "message": message,
            "skipped_account_numbers": skipped_account_numbers if asset_type == "bank_account" else [],
            "skipped_fixed_deposits": skipped_fd_keys if asset_type == "fixed_deposit" else [],
            "skipped_stocks": skipped_stocks if asset_type == "stock" else [],
            "skipped_mutual_funds": skipped_mutual_funds if asset_type == "mutual_fund" else []
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

