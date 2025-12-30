"""
Assets API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from fastapi.security import HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from models import Asset, AssetCreate, AssetUpdate, AssetType
from database.supabase_client import supabase, supabase_service
from auth import get_current_user, security
import io
import os
import json
from datetime import datetime

router = APIRouter(prefix="/api/assets", tags=["assets"])


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
        
        # Debug: Log the query before execution
        print(f"Fetching assets for user_id={user_id}, asset_type={asset_type}, is_active={is_active}")
        
        response = query.execute()
        all_assets = response.data if response.data else []
        
        # Filter by is_active if not explicitly specified
        # Include assets where is_active is True or NULL (NULL treated as active for backward compatibility)
        if is_active is None:
            assets = [a for a in all_assets if a.get("is_active") is True or a.get("is_active") is None]
        else:
            assets = all_assets
        
        print(f"Fetched {len(assets)} assets for user {user_id} (out of {len(all_assets)} total)")
        if len(assets) > 0:
            print(f"Sample asset: {assets[0]}")
        elif len(all_assets) > 0:
            print(f"Warning: {len(all_assets)} assets found but filtered to {len(assets)} based on is_active filter")
            print(f"Sample asset (all): {all_assets[0]}")
        
        return assets
    except Exception as e:
        import traceback
        import logging
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
        
        print(f"Creating asset for user {user_id}: type={asset_data.get('type')}, name={asset_data.get('name')}, is_active={asset_data.get('is_active')}")
        
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
            print(f"Failed to create asset: No data returned from Supabase")
            raise HTTPException(status_code=400, detail="Failed to create asset")
        
        created_asset = response.data[0]
        print(f"Successfully created asset: id={created_asset.get('id')}, type={created_asset.get('type')}, name={created_asset.get('name')}")
        return created_asset
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating asset: {str(e)}")
        print(f"Traceback: {error_details}")
        try:
            print(f"Asset data received: {asset.model_dump() if hasattr(asset, 'model_dump') else asset.dict()}")
        except:
            print("Could not serialize asset data for logging")
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
        import traceback
        import logging
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
        
        print(f"Deleting asset {asset_id} for user {user_id}")
        
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
            print(f"Asset {asset_id} not found or already deleted")
            raise HTTPException(status_code=404, detail="Asset not found")
        
        print(f"Successfully deleted asset {asset_id}")
        return {"message": "Asset deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error deleting asset: {str(e)}")
        print(f"Traceback: {error_details}")
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
        from services.stock_price_service import stock_price_service
        
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
        from services.stock_price_service import stock_price_service
        
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
        import pdfplumber
        
        pdf_stream = io.BytesIO(file_content)
        
        # Handle password-protected PDFs by decrypting with PyPDF2 first if password is provided
        if password:
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(pdf_stream)
                if pdf_reader.is_encrypted:
                    if not pdf_reader.decrypt(password):
                        raise HTTPException(
                            status_code=400,
                            detail="Incorrect password for PDF file. Please check the password and try again."
                        )
                    # Create a new stream with decrypted content
                    from PyPDF2 import PdfWriter
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
                print(f"Error decrypting PDF with PyPDF2: {e}")
        
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
        print(f"Error parsing PDF: {e}")
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
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Validate file type
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        if file_extension != 'pdf':
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read file content
        file_content = await file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
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
        
        # Fetch family members for owner name mapping
        family_members_map = {}
        try:
            family_members_response = supabase_service.table("family_members").select("*").eq("user_id", user_id).execute()
            family_members_list = family_members_response.data if family_members_response.data else []
            for fm in family_members_list:
                family_members_map[fm.get("name", "").lower()] = str(fm.get("id"))
        except Exception as e:
            print(f"Error fetching family members: {e}")
        
        # Process each page separately
        created_assets = []
        errors = []
        
        # Only process fixed deposits for now
        if asset_type == "fixed_deposit":
            # Import LLM service for direct JSON calls
            from google import genai
            from google.genai import types
            import asyncio
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            client = genai.Client(api_key=api_key)
            
            # Process each page
            print(f"DEBUG: Starting to process {len(pdf_pages)} pages from PDF")
            
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                print(f"DEBUG: Processing page {page_idx + 1} of {len(pdf_pages)}")
                if not page_content or not page_content.strip():
                    print(f"DEBUG: Page {page_idx + 1} is empty, skipping")
                    continue
                
                print(f"DEBUG: Page {page_idx + 1} content length: {len(page_content)} characters")
                try:
                    # Build system/instruction prompt
                    instruction_prompt = """Your task is to return the fixed deposits in a JSON format.

Do not include any other text in your response. Only return the JSON.

Each JSON object should have the following keys:

REQUIRED FIELDS (must be present for every fixed deposit):
1. bank_name (Account Number / Bank Account Number) - REQUIRED - This will be used as the asset name
2. principal_amount (Amount Invested / Principal Amount) - REQUIRED
3. fd_interest_rate (Rate of Interest / Interest Rate) - REQUIRED
4. start_date (Start Date in YYYY-MM-DD format) - REQUIRED
5. maturity_date (Maturity Date in YYYY-MM-DD format) - REQUIRED - Must be extracted directly from the document, do not calculate it

OPTIONAL FIELDS (include if available in the document):
6. maturity_amount (Total Amount at Maturity / Amount at Maturity / Maturity Value / Final Amount) - Optional - Extract this value ONLY if it is explicitly shown in the document with labels like "Total Amount at Maturity", "Maturity Amount", "Amount at Maturity", "Maturity Value", or "Final Amount". DO NOT calculate it. If the document does not explicitly show this value, leave it as null.
7. duration_months (Duration in months) - Optional - Extract this from the document if available. Do not calculate it.
8. owner_name (Owner Name - only the primary holder's name) - Optional - If not provided, use "self"

CRITICAL REQUIREMENTS:
1. You MUST provide all 5 REQUIRED fields (bank_name, principal_amount, fd_interest_rate, start_date, maturity_date) for EVERY fixed deposit. Do not skip any fixed deposit if these fields are present.
2. If a required field is missing from the document, you can leave it as null, but try your best to extract all required fields.
3. Make sure that you have extracted ALL fixed deposits from the page. Do not skip any fixed deposit.
4. For maturity_amount: ONLY extract it if you see it explicitly written in the document with one of the labels mentioned above. DO NOT calculate it using principal_amount, interest rate, or duration. If it's not explicitly shown, set it to null.
5. For optional fields, only include them if they are clearly present in the document.

Return a JSON array of fixed deposit objects. If there are multiple fixed deposits on this page, return all of them in the array."""
                    
                    # Build conversation messages list as list of dictionaries (conversational format)
                    contents = []
                    
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
                                "parts": [{"text": f"Here is a summary of all the fixed deposits from page {prev_idx + 1}:\n\n{prev_input}"}]
                            })
                            # Add previous assistant response (LLM output)
                            contents.append({
                                "role": "model",
                                "parts": [{"text": prev_output}]
                            })
                    
                    # Add current page as user message
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"Here is a summary of all the fixed deposits from page {page_idx + 1}:\n\n{page_content}"}]
                    })
                    
                    # Call Gemini with JSON mode
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model="gemini-2.0-flash-exp",
                            contents=contents,
                            config=config,
                        )
                    )
                    
                    # Extract JSON response
                    text_response = ""
                    if hasattr(response, 'text') and response.text:
                        text_response = response.text
                    elif hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                            text_response = "".join(text_parts)
                    
                    if not text_response:
                        errors.append(f"Page {page_idx + 1}: No response from LLM")
                        continue
                    
                    # Parse JSON response
                    try:
                        # Clean the response - remove markdown code blocks if present
                        cleaned_response = text_response.strip()
                        if cleaned_response.startswith("```json"):
                            cleaned_response = cleaned_response[7:]
                        if cleaned_response.startswith("```"):
                            cleaned_response = cleaned_response[3:]
                        if cleaned_response.endswith("```"):
                            cleaned_response = cleaned_response[:-3]
                        cleaned_response = cleaned_response.strip()
                        
                        fixed_deposits = json.loads(cleaned_response)
                        # Handle both single object and array
                        if not isinstance(fixed_deposits, list):
                            fixed_deposits = [fixed_deposits]
                        
                        print(f"DEBUG: Page {page_idx + 1}: LLM returned {len(fixed_deposits)} fixed deposit(s)")
                        
                        # Store input and output for future context (for pages after the first)
                        # This helps the LLM understand the format and extract data consistently
                        previous_contexts.append((page_content, cleaned_response))
                        print(f"DEBUG: Page {page_idx + 1}: Stored context for future pages (total contexts: {len(previous_contexts)})")
                        
                        # Skip if empty array (no fixed deposits on this page) - this is valid, just log and continue
                        if len(fixed_deposits) == 0:
                            print(f"DEBUG: Page {page_idx + 1}: Empty array returned (no fixed deposits on this page), continuing to next page")
                            continue  # This is fine - just means no FDs on this page
                        
                        # Process each fixed deposit
                        for fd_idx, fd_data in enumerate(fixed_deposits):
                            print(f"DEBUG: Page {page_idx + 1}, Fixed Deposit {fd_idx + 1}: Processing {fd_data}")
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
                                
                                print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Extracted fields - duration_months={duration_months}, maturity_date_str={maturity_date_str}, maturity_amount={maturity_amount}")
                                
                                # Validate required fields
                                if not principal_amount or not fd_interest_rate or not start_date_str:
                                    error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Missing required fields (principal_amount, fd_interest_rate, or start_date)"
                                    print(f"DEBUG: {error_msg}")
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
                                            print(f"DEBUG: {error_msg}")
                                            errors.append(error_msg)
                                            continue
                                
                                # Get maturity date (must be provided by user/PDF, not calculated)
                                maturity_date = None
                                
                                # Validate that maturity_date is provided (required field)
                                if not maturity_date_str:
                                    error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Missing maturity_date. Maturity date must be provided in the document."
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Parse maturity_date from LLM response (user-provided value)
                                try:
                                    maturity_date = datetime.strptime(maturity_date_str, "%Y-%m-%d").date()
                                    print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Using maturity_date from document (YYYY-MM-DD): {maturity_date}")
                                except:
                                    try:
                                        maturity_date = datetime.strptime(maturity_date_str, "%d-%m-%Y").date()
                                        print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Using maturity_date from document (DD-MM-YYYY): {maturity_date}")
                                    except:
                                        try:
                                            maturity_date = datetime.strptime(maturity_date_str, "%d/%m/%Y").date()
                                            print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Using maturity_date from document (DD/MM/YYYY): {maturity_date}")
                                        except:
                                            error_msg = f"Page {page_idx + 1}, FD {fd_idx + 1}: Invalid maturity date format: {maturity_date_str}"
                                            print(f"DEBUG: {error_msg}")
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
                                        print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Using maturity_amount from document: {maturity_amount}")
                                    except (ValueError, TypeError):
                                        print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Invalid maturity_amount format: {maturity_amount}, setting current_value to 0")
                                        asset_data["current_value"] = 0.0
                                else:
                                    asset_data["current_value"] = 0.0
                                    print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: No maturity_amount in document, current_value set to 0")
                                
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
                                print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Inserting into database - {bank_name}")
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    print(f"DEBUG: Page {page_idx + 1}, FD {fd_idx + 1}: Successfully created - {bank_name}")
                                    created_assets.append(response.data[0])
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create fixed deposit: {bank_name}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                import traceback
                                print(f"Error processing fixed deposit from page {page_idx + 1}: {e}")
                                print(traceback.format_exc())
                                errors.append(f"Page {page_idx + 1}: Error processing fixed deposit: {str(e)}")
                    
                    except json.JSONDecodeError as e:
                        errors.append(f"Page {page_idx + 1}: Invalid JSON response from LLM: {str(e)}")
                        print(f"LLM response was: {text_response}")
                    except Exception as e:
                        import traceback
                        print(f"Error processing page {page_idx + 1}: {e}")
                        print(traceback.format_exc())
                        errors.append(f"Page {page_idx + 1}: {str(e)}")
                
                except Exception as e:
                    import traceback
                    print(f"Error calling LLM for page {page_idx + 1}: {e}")
                    print(traceback.format_exc())
                    errors.append(f"Page {page_idx + 1}: Error calling LLM: {str(e)}")
        
        else:
            errors.append(f"Unsupported asset type: {asset_type}")
        
        print(f"DEBUG: Finished processing all pages. Created {len(created_assets)} assets, {len(errors)} errors")
        
        if not created_assets and not errors:
            errors.append("No fixed deposits found in the PDF")
        
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
        import traceback
        print(f"Error in upload_pdf_for_asset_type: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

