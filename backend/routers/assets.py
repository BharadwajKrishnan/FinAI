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
    cleaned_response = text_response.strip()
    
    # Remove opening markdown code block (handle both ```json and ```)
    if cleaned_response.startswith("```json"):
        cleaned_response = cleaned_response[7:].lstrip()  # Remove ```json and any following whitespace/newlines
    elif cleaned_response.startswith("```"):
        cleaned_response = cleaned_response[3:].lstrip()  # Remove ``` and any following whitespace/newlines
    
    # Remove closing markdown code block
    if cleaned_response.endswith("```"):
        cleaned_response = cleaned_response[:-3].rstrip()  # Remove ``` and any preceding whitespace/newlines
    
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


@router.post("/", response_model=Asset)
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
        update_data = asset.dict(exclude_unset=True, exclude_none=True)
        
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
        
        # Process fixed deposits or stocks
        if asset_type == "fixed_deposit":
            if not _fixed_deposit_llm_service.api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            # Process each page
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                if not page_content or not page_content.strip():
                    continue
                
                try:
                    # Load prompt from file
                    instruction_prompt = load_prompt("fixed_deposit_prompt.txt")
                    
                    # Build contents list using helper function
                    contents = build_contents_list(instruction_prompt, previous_contexts, page_content, page_idx, "fixed_deposit")
                    
                    # Call Gemini with JSON mode using LLMService
                    text_response = await _fixed_deposit_llm_service.generate_json(contents)
                    
                    if not text_response:
                        errors.append(f"Page {page_idx + 1}: No response from LLM")
                        continue
                    
                    # Parse JSON response using helper function
                    try:
                        fixed_deposits, cleaned_response = clean_and_parse_json_response(text_response)
                        
                        # Store input and output for future context (for pages after the first)
                        # This helps the LLM understand the format and extract data consistently
                        previous_contexts.append((page_content, cleaned_response))
                        
                        # Skip if empty array (no fixed deposits on this page) - this is valid, just log and continue
                        if len(fixed_deposits) == 0:
                            continue  # This is fine - just means no FDs on this page
                        
                        # Process each fixed deposit
                        for fd_idx, fd_data in enumerate(fixed_deposits):
                            try:
                                # Get currency from market
                                asset_market = market or "india"
                                currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                                
                                # Extract and validate fields
                                bank_name = fd_data.get("bank_name") or fd_data.get("Bank Name") or "Unknown Bank"
                                principal_amount = fd_data.get("principal_amount") or fd_data.get("Amount Invested")
                                fd_interest_rate = fd_data.get("fd_interest_rate") or fd_data.get("Rate of Interest")
                                duration_months = fd_data.get("duration_months") or fd_data.get("Duration")
                                start_date_str = fd_data.get("start_date") or fd_data.get("Start Date")
                                maturity_date_str = fd_data.get("maturity_date") or fd_data.get("Maturity Date")
                                maturity_amount = fd_data.get("maturity_amount") or fd_data.get("Total Amount at Maturity") or fd_data.get("Maturity Amount") or fd_data.get("Amount at Maturity") or fd_data.get("Maturity Value") or fd_data.get("Final Amount")
                                owner_name = fd_data.get("owner_name") or fd_data.get("Owner Name") or "self"
                                
                                # Validate required fields
                                if not principal_amount or not fd_interest_rate or not start_date_str:
                                    error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Missing required fields (principal_amount, fd_interest_rate, or start_date)"
                                    errors.append(error_msg)
                                    continue
                                
                                # Parse start date
                                try:
                                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                                except:
                                    # Try other date formats
                                    try:
                                        start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                                    except:
                                        try:
                                            start_date = datetime.strptime(start_date_str, "%d/%m/%Y").date()
                                        except:
                                            error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Invalid start date format: {start_date_str}"
                                            errors.append(error_msg)
                                            continue
                                
                                # Get maturity date (must be provided by user/PDF, not calculated)
                                maturity_date = None
                                
                                # Validate that maturity_date is provided (required field)
                                if not maturity_date_str:
                                    error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Missing maturity_date. Maturity date must be provided in the document."
                                    errors.append(error_msg)
                                    continue
                                
                                # Parse maturity_date from LLM response (user-provided value)
                                try:
                                    maturity_date = datetime.strptime(maturity_date_str, "%Y-%m-%d").date()
                                except:
                                    try:
                                        maturity_date = datetime.strptime(maturity_date_str, "%d-%m-%Y").date()
                                    except:
                                        try:
                                            maturity_date = datetime.strptime(maturity_date_str, "%d/%m/%Y").date()
                                        except:
                                            error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Invalid maturity date format: {maturity_date_str}"
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
                                    "type": "fixed_deposit",
                                    "currency": currency,
                                    "principal_amount": float(principal_amount),
                                    "fd_interest_rate": float(fd_interest_rate),
                                    "start_date": start_date.isoformat(),
                                    "maturity_date": maturity_date.isoformat(),
                                    "is_active": True,
                                    "family_member_id": family_member_id
                                }
                                
                                # Set current_value from maturity_amount if provided in the document
                                if maturity_amount:
                                    try:
                                        asset_data["current_value"] = float(maturity_amount)
                                    except (ValueError, TypeError):
                                        asset_data["current_value"] = 0.0
                                else:
                                    asset_data["current_value"] = 0.0
                                
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
                                
                                # Insert into database
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    created_assets.append(response.data[0])
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create fixed deposit: {bank_name}"
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                errors.append(f"Page {page_idx + 1}: Error processing fixed deposit: {str(e)}")
                    
                    except json.JSONDecodeError as e:
                        errors.append(f"Page {page_idx + 1}: Invalid JSON response from LLM: {str(e)}")
                    except Exception as e:
                        errors.append(f"Page {page_idx + 1}: {str(e)}")
                
                except Exception as e:
                    errors.append(f"Page {page_idx + 1}: Error calling LLM: {str(e)}")
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    await asyncio.sleep(5)
        
        elif asset_type == "stock":
            if not _stock_llm_service.api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            # Process each page
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                if not page_content or not page_content.strip():
                    continue
                
                try:
                    # Load prompt from file
                    instruction_prompt = load_prompt("stocks_prompt.txt")
                    
                    # Build contents list using helper function
                    contents = build_contents_list(instruction_prompt, previous_contexts, page_content, page_idx, "stock")
                    
                    # Call Gemini with JSON mode using LLMService
                    text_response = await _stock_llm_service.generate_json(contents)
                    
                    if not text_response:
                        errors.append(f"Page {page_idx + 1}: No response from LLM")
                        continue
                    
                    # Parse JSON response using helper function
                    try:
                        stocks, cleaned_response = clean_and_parse_json_response(text_response)
                        
                        # Store input and output for future context (for pages after the first)
                        previous_contexts.append((page_content, cleaned_response))
                        
                        # Skip if empty array (no stocks on this page)
                        if len(stocks) == 0:
                            continue
                        
                        # Process each stock
                        for stock_idx, stock_data in enumerate(stocks):
                            try:
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
                                    error_msg = f"Page {page_idx + 1}, Stock {stock_idx + 1}: Missing required fields (name, symbol, average_price, current_price, quantity, or value_at_cost). Data: {stock_data}"
                                    errors.append(error_msg)
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
                                    error_msg = f"Page {page_idx + 1}, Stock {stock_idx + 1}: Invalid numeric values - avg_price: {average_price}, current_price: {current_price}, quantity: {quantity}, value_at_cost: {value_at_cost}"
                                    errors.append(error_msg)
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
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    created_assets.append(response.data[0])
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create stock: {stock_name}"
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                errors.append(f"Page {page_idx + 1}: Error processing stock: {str(e)}")
                    
                    except json.JSONDecodeError as e:
                        errors.append(f"Page {page_idx + 1}: Invalid JSON response from LLM: {str(e)}")
                    except Exception as e:
                        errors.append(f"Page {page_idx + 1}: {str(e)}")
                
                except Exception as e:
                    errors.append(f"Page {page_idx + 1}: Error calling LLM: {str(e)}")
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    await asyncio.sleep(5)
        
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
            
            # Process all collected bank accounts
            logger.info(f"Starting to process {len(all_bank_accounts)} bank accounts for database insertion")
            print(f"Starting to process {len(all_bank_accounts)} bank accounts for database insertion")
            created_assets = []
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
                    
                    # Check for duplicates before inserting (check against newly created assets in this session)
                    is_duplicate = False
                    for created_asset in created_assets:
                        if created_asset.get("type") == "bank_account":
                            created_account_number = created_asset.get("account_number", "")
                            created_bank_name = created_asset.get("bank_name", "")
                            # Match by account number and bank name
                            if account_number and created_account_number:
                                if account_number.lower() == created_account_number.lower() and bank_name.lower() == created_bank_name.lower():
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
                    print(f"ERROR: {error_msg}")
                    import traceback
                    logger.error(traceback.format_exc())
                    errors.append(error_msg)
        
        elif asset_type == "mutual_fund":
            if not _mutual_fund_llm_service.api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            # Fetch existing mutual funds to prevent duplicates
            existing_mutual_funds = []
            try:
                existing_assets_response = supabase_service.table("assets").select("mutual_fund_code, name, fund_house").eq("user_id", user_id).eq("type", "mutual_fund").eq("is_active", True).execute()
                existing_mutual_funds = existing_assets_response.data if existing_assets_response.data else []
            except Exception as e:
                pass
            
            # Format existing mutual funds for the prompt
            existing_funds_text = ""
            if existing_mutual_funds:
                existing_funds_list = []
                for fund in existing_mutual_funds:
                    fund_name = fund.get("name", "Unknown")
                    fund_code = fund.get("mutual_fund_code", "")
                    fund_house = fund.get("fund_house", "")
                    if fund_code:
                        if fund_house:
                            existing_funds_list.append(f"- Name: {fund_name}, Fund Code: {fund_code}, Fund House: {fund_house}")
                        else:
                            existing_funds_list.append(f"- Name: {fund_name}, Fund Code: {fund_code}")
                    else:
                        existing_funds_list.append(f"- Name: {fund_name}")
                existing_funds_text = "\n".join(existing_funds_list)
            
            # Process each page
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                if not page_content or not page_content.strip():
                    continue
                
                try:
                    # Load prompt from file and format with existing funds
                    prompt_template = load_prompt("mutual_funds_prompt.txt")
                    existing_funds_placeholder = existing_funds_text if existing_funds_text else "No mutual funds have been added yet."
                    instruction_prompt = prompt_template.format(existing_funds_text=existing_funds_placeholder)
                    
                    # Build contents list using helper function
                    contents = build_contents_list(instruction_prompt, previous_contexts, page_content, page_idx, "mutual_fund")
                    
                    # Call Gemini with JSON mode using LLMService
                    text_response = await _mutual_fund_llm_service.generate_json(contents)
                    
                    if not text_response:
                        errors.append(f"Page {page_idx + 1}: No response from LLM")
                        continue
                    
                    # Parse JSON response using helper function
                    try:
                        mutual_funds, cleaned_response = clean_and_parse_json_response(text_response)
                        
                        # Store input and output for future context (for pages after the first)
                        previous_contexts.append((page_content, cleaned_response))
                        
                        # Skip if empty array (no mutual funds on this page)
                        if len(mutual_funds) == 0:
                            continue
                        
                        # Process each mutual fund
                        for mf_idx, mf_data in enumerate(mutual_funds):
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
                                    error_msg = f"Page {page_idx + 1}, MF {mf_idx + 1}: Missing required fields (fund_name, fund_code, or units)"
                                    errors.append(error_msg)
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
                                    error_msg = f"Page {page_idx + 1}, MF {mf_idx + 1}: Invalid units value: {units}"
                                    errors.append(error_msg)
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
                                
                                # Check for duplicates before inserting (check both existing DB records and newly created ones)
                                is_duplicate = False
                                # Check in existing mutual funds list
                                for existing_fund in existing_mutual_funds:
                                    existing_code = existing_fund.get("mutual_fund_code", "")
                                    if existing_code and fund_code and existing_code.lower() == fund_code.lower():
                                        is_duplicate = True
                                        break
                                
                                # Check in newly created assets in this session
                                if not is_duplicate:
                                    for created_asset in created_assets:
                                        if created_asset.get("type") == "mutual_fund":
                                            created_code = created_asset.get("mutual_fund_code", "")
                                            if created_code and fund_code and created_code.lower() == fund_code.lower():
                                                is_duplicate = True
                                                break
                                
                                if is_duplicate:
                                    continue
                                
                                # Insert into database
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    created_assets.append(response.data[0])
                                    # Also add to existing_mutual_funds list to prevent duplicates in subsequent pages
                                    existing_mutual_funds.append({
                                        "mutual_fund_code": fund_code,
                                        "name": fund_name,
                                        "fund_house": fund_house
                                    })
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create mutual fund: {fund_name}"
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                errors.append(f"Page {page_idx + 1}: Error processing mutual fund: {str(e)}")
                    
                    except json.JSONDecodeError as e:
                        errors.append(f"Page {page_idx + 1}: Invalid JSON response from LLM: {str(e)}")
                    except Exception as e:
                        errors.append(f"Page {page_idx + 1}: {str(e)}")
                
                except Exception as e:
                    errors.append(f"Page {page_idx + 1}: Error calling LLM: {str(e)}")
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    await asyncio.sleep(5)
        
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
        
        return {
            "success": len(created_assets) > 0,
            "created_count": len(created_assets),
            "created_assets": created_assets,
            "errors": errors,
            "message": f"Successfully added {len(created_assets)} {asset_type}(s) from PDF" if created_assets else "No assets could be extracted from the PDF"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

