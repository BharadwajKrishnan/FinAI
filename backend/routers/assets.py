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
        
        # Process fixed deposits or stocks
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
                    
                    # Get model name from environment or use default (gemini-2.5-flash has higher quota limits)
                    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
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
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    print(f"DEBUG: Waiting 5 seconds before processing next page...")
                    await asyncio.sleep(5)
        
        elif asset_type == "stock":
            # Import LLM service for direct JSON calls
            from google import genai
            from google.genai import types
            import asyncio
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            client = genai.Client(api_key=api_key)
            
            # Process each page
            print(f"DEBUG: Starting to process {len(pdf_pages)} pages from PDF for stocks")
            
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                print(f"DEBUG: Processing page {page_idx + 1} of {len(pdf_pages)} for stocks")
                if not page_content or not page_content.strip():
                    print(f"DEBUG: Page {page_idx + 1} is empty, skipping")
                    continue
                
                print(f"DEBUG: Page {page_idx + 1} content length: {len(page_content)} characters")
                try:
                    # Build instruction prompt using user's format
                    instruction_prompt = f"""Your task is to extract ONLY stocks/equities (shares of companies) from the document. DO NOT include mutual funds, bonds, or any other investment types. Only extract individual company stocks/equities.

CRITICAL RULES - READ CAREFULLY

1. SECTION RESTRICTION: ONLY search for and extract stocks/equities from sections of the document that are specifically labeled as "Stocks", "Equities", "Stock Holdings", "Equity Portfolio", "Share Holdings", or similar stock/equity sections. DO NOT extract information from mutual fund sections, bank account sections, fixed deposit sections, or any other sections. If the page does not contain a stock/equity section, return an empty JSON array [].
2. DO NOT PERFORM ANY CALCULATIONS WHATSOEVER. ONLY EXTRACT VALUES EXACTLY AS THEY APPEAR IN THE DOCUMENT.
3. ALL VALUES MUST BE EXACTLY AS SHOWN IN THE PDF - NO ROUNDING, NO MODIFICATIONS, NO CALCULATIONS.
4. YOU MUST EXTRACT ALL STOCKS FROM THE PAGE - DO NOT SKIP ANY STOCK. EVERY SINGLE STOCK MUST BE INCLUDED.

Return the stocks/equities in a JSON format. Do not include any other text in your response. Only return the JSON.

Each JSON object MUST have the following keys with EXACT names:
1. "Stock/Equity Name" - REQUIRED - Extract the name EXACTLY as shown in the document
2. "Stock Symbol" - REQUIRED - Extract the ticker symbol EXACTLY as shown (e.g., "AAPL", "RELIANCE", "TCS"). If not available, use the stock name as symbol
3. "Average Price" - REQUIRED - Extract the average purchase price EXACTLY as shown in the document. Look for "Avg. Price", "Average Price", or "Purchase Price" labels. Extract the EXACT value - do not round, modify, or calculate.
4. "Current Price" - REQUIRED - Extract the current market price EXACTLY as shown in the document. Look for "Price", "Current Price", or "Market Price" labels. Extract the EXACT value - do not round, modify, or calculate.
5. "Quantity" - REQUIRED - Extract the quantity EXACTLY as shown in the document. Extract the EXACT value - do not round, modify, or calculate.
6. "Purchase Date" - REQUIRED - Extract purchase date in YYYY-MM-DD format. If not available in document, use "1900-01-01" as placeholder
7. "Value at Cost" - REQUIRED - Extract the total amount invested EXACTLY as shown in the document. Look for "Value at Cost", "Amount Invested", or "Total Invested" labels. Extract the EXACT value as it appears - DO NOT calculate it. DO NOT multiply Average Price * Quantity. The document already shows this value - copy it EXACTLY.
8. "Current Value" - Optional - Extract current market value EXACTLY as shown in the document. Look for "Current Value", "Current Worth", or "Market Value" labels. Extract the EXACT value - do not round, modify, or calculate.
9. "Owner Name" - Optional - Primary holder's name. If not provided, use "self"

MANDATORY REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:
1. ONLY extract stocks/equities from stock/equity sections. DO NOT extract from mutual fund sections, bank account sections, fixed deposit sections, or any other sections. If the page does not contain a stock/equity section, return an empty JSON array [].
2. ONLY extract stocks/equities (individual company shares). DO NOT extract mutual funds, bonds, ETFs, or other investment types.
3. You MUST provide "Stock/Equity Name", "Stock Symbol", "Average Price", "Current Price", "Quantity", and "Value at Cost" for EVERY stock. These are mandatory fields.
3. ABSOLUTELY NO CALCULATIONS ALLOWED - Extract all numeric values EXACTLY as they appear in the document. If the document shows "1,515.55", extract it as "1,515.55" (do not convert to 1515.55, keep commas if present). If the document shows "1515.55", extract it as "1515.55".
4. For "Average Price": Find the value next to "Avg. Price", "Average Price", or "Purchase Price" in the document and copy it EXACTLY as shown. DO NOT calculate, round, or modify it.
5. For "Current Price": Find the value next to "Price", "Current Price", or "Market Price" in the document and copy it EXACTLY as shown. DO NOT calculate, round, or modify it.
6. For "Value at Cost": Find the value next to "Value at Cost", "Amount Invested", or "Total Invested" in the document and copy it EXACTLY as shown. DO NOT calculate it as Average Price * Quantity. DO NOT perform any multiplication. The document already contains this value - extract it EXACTLY as it appears.
7. For "Quantity": Find the quantity in the document and copy it EXACTLY as shown. DO NOT calculate, round, or modify it.
8. For "Stock Symbol": Extract the ticker symbol EXACTLY as shown (e.g., "RELIANCE", "TCS", "INFY"). If NOT available, use the stock name as the symbol.
9. For "Purchase Date": If available in the document, extract it and convert to YYYY-MM-DD format. If NOT available, use "1900-01-01" as a placeholder.
10. Use the EXACT key names as specified above (e.g., "Stock/Equity Name", "Stock Symbol", "Average Price", "Current Price", "Quantity", "Value at Cost", "Purchase Date").
11. YOU MUST EXTRACT ALL STOCKS FROM THE PAGE - DO NOT SKIP ANY STOCK. Count all stocks carefully and ensure EVERY stock is included in your response. If there are 10 stocks on the page, your JSON array must contain exactly 10 objects.
12. Extract values EXACTLY as they appear in the document - preserve decimal places, commas, and formatting as shown in the PDF.

Return a JSON array of stock objects. If there are multiple stocks on this page, return ALL of them in the array. DO NOT skip any stock."""
                    
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
                                "parts": [{"text": f"Here is a summary of all the stock/equity from page {prev_idx + 1}:\n\n{prev_input}"}]
                            })
                            # Add previous assistant response (LLM output)
                            contents.append({
                                "role": "model",
                                "parts": [{"text": prev_output}]
                            })
                    
                    # Add current page as user message
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"Here is a summary of all the stock/equity from page {page_idx + 1}:\n\n{page_content}"}]
                    })
                    
                    # Call Gemini with JSON mode
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                    
                    # Get model name from environment or use default (gemini-2.5-flash has higher quota limits)
                    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
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
                        
                        stocks = json.loads(cleaned_response)
                        # Handle both single object and array
                        if not isinstance(stocks, list):
                            stocks = [stocks]
                        
                        print(f"DEBUG: Page {page_idx + 1}: LLM returned {len(stocks)} stock(s)")
                        
                        # Store input and output for future context (for pages after the first)
                        previous_contexts.append((page_content, cleaned_response))
                        print(f"DEBUG: Page {page_idx + 1}: Stored context for future pages (total contexts: {len(previous_contexts)})")
                        
                        # Skip if empty array (no stocks on this page)
                        if len(stocks) == 0:
                            print(f"DEBUG: Page {page_idx + 1}: Empty array returned (no stocks on this page), continuing to next page")
                            continue
                        
                        # Process each stock
                        for stock_idx, stock_data in enumerate(stocks):
                            print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Processing {stock_data}")
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
                                    print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Skipping mutual fund entry (has Scheme/NAV but no stock name)")
                                    continue
                                
                                print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Extracted fields - name={stock_name}, symbol={stock_symbol}, avg_price={average_price}, current_price={current_price}, quantity={quantity}, value_at_cost={value_at_cost}, purchase_date={purchase_date_str}")
                                
                                # Validate required fields (name, symbol, average_price, current_price, quantity, value_at_cost are mandatory; purchase_date can be defaulted)
                                if not stock_name or not stock_symbol or not average_price or not current_price or not quantity or not value_at_cost:
                                    error_msg = f"Page {page_idx + 1}, Stock {stock_idx + 1}: Missing required fields (name, symbol, average_price, current_price, quantity, or value_at_cost). Data: {stock_data}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Use default date if purchase_date is not provided
                                if not purchase_date_str or purchase_date_str == "1900-01-01":
                                    purchase_date_str = "1900-01-01"  # Default placeholder date
                                    print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Purchase date not provided, using default placeholder")
                                
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
                                                print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Invalid purchase date format: {purchase_date_str}, using default")
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
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Note: We use the extracted value_at_cost directly - no validation against calculation
                                # The LLM should extract this value directly from the document, not calculate it
                                print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Using extracted Value at Cost: {value_at_cost_float}")
                                
                                # Extract current_value directly from document (do not calculate)
                                if current_value:
                                    try:
                                        current_value_cleaned = clean_numeric_string(current_value)
                                        current_value_float = float(current_value_cleaned)
                                        print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Using extracted Current Value: {current_value_float}")
                                    except (ValueError, TypeError):
                                        # If current_value cannot be parsed, log error but don't calculate
                                        print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Could not parse Current Value: {current_value}, setting to 0")
                                        current_value_float = 0.0
                                else:
                                    # If not provided in document, set to 0 (do not calculate)
                                    print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Current Value not found in document, setting to 0")
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
                                print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Inserting into database - {stock_name}")
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    print(f"DEBUG: Page {page_idx + 1}, Stock {stock_idx + 1}: Successfully created - {stock_name}")
                                    created_assets.append(response.data[0])
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create stock: {stock_name}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                import traceback
                                print(f"Error processing stock from page {page_idx + 1}: {e}")
                                print(traceback.format_exc())
                                errors.append(f"Page {page_idx + 1}: Error processing stock: {str(e)}")
                    
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
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    print(f"DEBUG: Waiting 5 seconds before processing next page...")
                    await asyncio.sleep(5)
        
        elif asset_type == "bank_account":
            # Import LLM service for direct JSON calls
            from google import genai
            from google.genai import types
            import asyncio
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            client = genai.Client(api_key=api_key)
            
            # Fetch existing bank accounts to prevent duplicates
            existing_bank_accounts = []
            try:
                existing_assets_response = supabase_service.table("assets").select("bank_name, account_number, account_type").eq("user_id", user_id).eq("type", "bank_account").eq("is_active", True).execute()
                existing_bank_accounts = existing_assets_response.data if existing_assets_response.data else []
                print(f"DEBUG: Found {len(existing_bank_accounts)} existing bank accounts")
            except Exception as e:
                print(f"Error fetching existing bank accounts: {e}")
            
            # Format existing bank accounts for the prompt
            existing_accounts_text = ""
            if existing_bank_accounts:
                existing_accounts_list = []
                for acc in existing_bank_accounts:
                    bank_name = acc.get("bank_name", "Unknown")
                    account_number = acc.get("account_number", "")
                    account_type = acc.get("account_type", "")
                    if account_number:
                        existing_accounts_list.append(f"- Bank: {bank_name}, Account Number: {account_number}, Type: {account_type}")
                    else:
                        existing_accounts_list.append(f"- Bank: {bank_name}, Type: {account_type}")
                existing_accounts_text = "\n".join(existing_accounts_list)
            
            # Process each page
            print(f"DEBUG: Starting to process {len(pdf_pages)} pages from PDF for bank accounts")
            
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                print(f"DEBUG: Processing page {page_idx + 1} of {len(pdf_pages)} for bank accounts")
                if not page_content or not page_content.strip():
                    print(f"DEBUG: Page {page_idx + 1} is empty, skipping")
                    continue
                
                print(f"DEBUG: Page {page_idx + 1} content length: {len(page_content)} characters")
                try:
                    # Build instruction prompt
                    instruction_prompt = f"""Your task is to extract bank account information from the document. DO NOT include fixed deposits, mutual funds, stocks, or any other investment types. Only extract bank accounts (savings, checking, current accounts).

⚠️⚠️⚠️ CRITICAL RULES - READ CAREFULLY ⚠️⚠️⚠️

1. DO NOT PERFORM ANY CALCULATIONS WHATSOEVER. ONLY EXTRACT VALUES EXACTLY AS THEY APPEAR IN THE DOCUMENT.
2. ALL VALUES MUST BE EXACTLY AS SHOWN IN THE PDF - NO ROUNDING, NO MODIFICATIONS, NO CALCULATIONS.
3. ⚠️ DUPLICATE PREVENTION: Check the following list of ALREADY ADDED bank accounts. If a bank account from the document matches any of these (same bank name and account number, or same bank name if account number is not available), DO NOT include it in your response. Return an empty JSON array [] if all bank accounts on this page are already added.
4. YOU MUST EXTRACT ALL NEW BANK ACCOUNTS FROM THE PAGE - DO NOT SKIP ANY NEW BANK ACCOUNT. However, skip any bank accounts that are duplicates of already added accounts.

ALREADY ADDED BANK ACCOUNTS:
{existing_accounts_text if existing_accounts_text else "No bank accounts have been added yet."}

IMPORTANT: A bank account is considered a duplicate if:
- The bank name matches AND the account number matches (if account number is available in both)
- OR the bank name matches AND account type matches (if account number is not available in either)

If you find a duplicate, skip it and do not include it in your response. Only return NEW bank accounts that are not in the list above.

Return the bank accounts in a JSON format. Do not include any other text in your response. Only return the JSON.

Each JSON object MUST have the following keys with EXACT names:

REQUIRED FIELDS (must be present for every bank account):
1. "Bank Name" - REQUIRED - Extract the name of the bank EXACTLY as shown in the document
2. "Account Type" - REQUIRED - Extract the account type. Must be one of: "savings", "checking", or "current". Extract the value EXACTLY as shown or map to the closest match (e.g., "Savings Account" -> "savings", "Current Account" -> "current", "Checking Account" -> "checking")
3. "Current Balance" - REQUIRED - Extract the current account balance EXACTLY as shown in the document. Look for "Balance", "Current Balance", "Available Balance", or "Account Balance" labels. Extract the EXACT value - do not round, modify, or calculate.
4. "Account Number" - REQUIRED - Extract the account number EXACTLY as shown in the document. Can be masked or partial (e.g., "****1234" or "50100121888270"). ⚠️ CRITICAL: If you cannot find an account number in the document for a bank account, DO NOT include that bank account in your response. Only return bank accounts that have an account number clearly visible in the document.

OPTIONAL FIELDS (include if available in the document):
5. "Interest Rate" - Optional - Extract the annual interest rate percentage EXACTLY as shown in the document. Look for "Interest Rate", "Annual Interest Rate", or "Rate of Interest" labels. Extract the EXACT value - do not round, modify, or calculate.
6. "Owner Name" - Optional - Primary account holder's name. If not provided, use "self"

CRITICAL REQUIREMENTS:
1. ONLY extract bank accounts (savings, checking, current accounts). DO NOT extract fixed deposits, mutual funds, stocks, or other investment types.
2. You MUST provide "Bank Name", "Account Type", "Current Balance", and "Account Number" for EVERY bank account. These are mandatory fields. ⚠️ IF AN ACCOUNT NUMBER IS NOT AVAILABLE IN THE DOCUMENT, DO NOT INCLUDE THAT BANK ACCOUNT IN YOUR RESPONSE.
3. ⚠️ ABSOLUTELY NO CALCULATIONS ALLOWED - Extract all numeric values EXACTLY as they appear in the document. If the document shows "10,000.50", extract it as "10,000.50" (preserve formatting as shown).
4. For "Account Type": Extract or map to one of: "savings", "checking", or "current". Common mappings:
   - "Savings Account", "SA", "Saving Account" -> "savings"
   - "Current Account", "CA", "Current A/c" -> "current"
   - "Checking Account", "Checking", "CHK" -> "checking"
5. For "Current Balance": Find the value next to "Balance", "Current Balance", "Available Balance", or "Account Balance" in the document and copy it EXACTLY as shown. DO NOT calculate, round, or modify it.
6. For "Interest Rate": Extract the annual interest rate percentage EXACTLY as shown. DO NOT calculate or modify it.
7. For "Account Number": Extract the account number EXACTLY as shown (can be masked, e.g., "****1234" or full number like "50100121888270"). ⚠️ THIS FIELD IS REQUIRED - if you cannot find an account number in the document, DO NOT include that bank account in your response.
8. ⚠️ DUPLICATE CHECK: Before including any bank account in your response, check if it already exists in the "ALREADY ADDED BANK ACCOUNTS" list above. Compare by:
   - Bank name (case-insensitive matching)
   - Account number (if available in both the document and the existing list)
   - Account type (if account number is not available)
   - If a match is found, DO NOT include that bank account in your response.
9. ⚠️ YOU MUST EXTRACT ALL NEW BANK ACCOUNTS FROM THE PAGE - DO NOT SKIP ANY NEW BANK ACCOUNT. However, skip any bank accounts that are duplicates of already added accounts.
10. Extract values EXACTLY as they appear in the document - preserve decimal places, commas, and formatting as shown in the PDF.

Return a JSON array of bank account objects. If there are multiple NEW bank accounts on this page (not duplicates), return ALL of them in the array. If all bank accounts on this page are duplicates, return an empty array []. DO NOT skip any new bank account, but DO skip duplicates."""
                    
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
                                "parts": [{"text": f"Here is a summary of all the bank accounts from page {prev_idx + 1}:\n\n{prev_input}"}]
                            })
                            # Add previous assistant response (LLM output)
                            contents.append({
                                "role": "model",
                                "parts": [{"text": prev_output}]
                            })
                    
                    # Add current page as user message
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"Here is a summary of all the bank accounts from page {page_idx + 1}:\n\n{page_content}"}]
                    })
                    
                    # Call Gemini with JSON mode
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                    
                    # Get model name from environment or use default (gemini-2.5-flash has higher quota limits)
                    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
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
                        
                        bank_accounts = json.loads(cleaned_response)
                        # Handle both single object and array
                        if not isinstance(bank_accounts, list):
                            bank_accounts = [bank_accounts]
                        
                        print(f"DEBUG: Page {page_idx + 1}: LLM returned {len(bank_accounts)} bank account(s)")
                        
                        # Store input and output for future context (for pages after the first)
                        previous_contexts.append((page_content, cleaned_response))
                        print(f"DEBUG: Page {page_idx + 1}: Stored context for future pages (total contexts: {len(previous_contexts)})")
                        
                        # Skip if empty array (no bank accounts on this page)
                        if len(bank_accounts) == 0:
                            print(f"DEBUG: Page {page_idx + 1}: Empty array returned (no bank accounts on this page), continuing to next page")
                            continue
                        
                        # Process each bank account
                        for ba_idx, ba_data in enumerate(bank_accounts):
                            print(f"DEBUG: Page {page_idx + 1}, Bank Account {ba_idx + 1}: Processing {ba_data}")
                            try:
                                # Get currency from market
                                asset_market = market or "india"
                                currency = "INR" if asset_market.lower() == "india" else "EUR" if asset_market.lower() == "europe" else "INR"
                                
                                # Extract and validate fields (handle multiple possible key names)
                                bank_name = ba_data.get("Bank Name") or ba_data.get("bank_name") or ba_data.get("Bank") or "Unknown Bank"
                                account_type_str = ba_data.get("Account Type") or ba_data.get("account_type") or ba_data.get("Type") or ba_data.get("type")
                                current_balance = ba_data.get("Current Balance") or ba_data.get("current_balance") or ba_data.get("Balance") or ba_data.get("balance") or ba_data.get("Available Balance") or ba_data.get("Account Balance")
                                account_number = ba_data.get("Account Number") or ba_data.get("account_number") or ba_data.get("Account No") or ba_data.get("Account #")
                                interest_rate = ba_data.get("Interest Rate") or ba_data.get("interest_rate") or ba_data.get("Annual Interest Rate") or ba_data.get("Rate of Interest")
                                owner_name = ba_data.get("Owner Name") or ba_data.get("owner_name") or "self"
                                
                                print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Extracted fields - bank_name={bank_name}, account_type={account_type_str}, balance={current_balance}, account_number={account_number}, interest_rate={interest_rate}")
                                
                                # Validate required fields (account_number is now required)
                                if not bank_name or not account_type_str or current_balance is None or not account_number:
                                    error_msg = f"Page {page_idx + 1}, BA {ba_idx + 1}: Missing required fields (bank_name, account_type, current_balance, or account_number)"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Normalize account type (map to valid enum values)
                                account_type_lower = account_type_str.lower().strip()
                                if "savings" in account_type_lower or account_type_lower in ["sa", "sav"]:
                                    account_type = "savings"
                                elif "current" in account_type_lower or account_type_lower in ["ca", "cur"]:
                                    account_type = "current"
                                elif "checking" in account_type_lower or account_type_lower in ["chk", "check"]:
                                    account_type = "checking"
                                else:
                                    # Default to savings if can't determine
                                    account_type = "savings"
                                    print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Could not determine account type from '{account_type_str}', defaulting to 'savings'")
                                
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
                                    print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Using extracted Current Balance: {balance_float}")
                                except (ValueError, TypeError) as e:
                                    error_msg = f"Page {page_idx + 1}, BA {ba_idx + 1}: Invalid balance value: {current_balance}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Convert interest_rate to float if provided (clean numeric strings first)
                                interest_rate_float = None
                                if interest_rate:
                                    try:
                                        interest_rate_cleaned = clean_numeric_string(interest_rate)
                                        interest_rate_float = float(interest_rate_cleaned)
                                        print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Using extracted Interest Rate: {interest_rate_float}")
                                    except (ValueError, TypeError):
                                        print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Could not parse Interest Rate: {interest_rate}, leaving as None")
                                
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
                                    "account_type": account_type,
                                    "current_value": balance_float,  # Current balance
                                    "is_active": True,
                                    "family_member_id": family_member_id
                                }
                                
                                # Add optional fields if provided
                                if account_number:
                                    asset_data["account_number"] = account_number
                                if interest_rate_float is not None:
                                    asset_data["interest_rate"] = interest_rate_float
                                
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
                                decimal_fields = ['current_value', 'interest_rate']
                                for field in decimal_fields:
                                    if field in asset_dict and asset_dict[field] is not None:
                                        asset_dict[field] = str(asset_dict[field])
                                
                                # Check for duplicates before inserting (check both existing DB records and newly created ones)
                                is_duplicate = False
                                # Check in existing bank accounts list
                                for existing_account in existing_bank_accounts:
                                    existing_account_number = existing_account.get("account_number", "")
                                    existing_bank_name = existing_account.get("bank_name", "")
                                    existing_account_type = existing_account.get("account_type", "")
                                    # Match by account number if both have it, otherwise match by bank name + account type
                                    if account_number and existing_account_number:
                                        if account_number.lower() == existing_account_number.lower() and bank_name.lower() == existing_bank_name.lower():
                                            print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Duplicate found in existing accounts - {bank_name} (Account: {account_number})")
                                            is_duplicate = True
                                            break
                                    elif bank_name.lower() == existing_bank_name.lower() and account_type == existing_account_type:
                                        print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Duplicate found in existing accounts - {bank_name} (Type: {account_type})")
                                        is_duplicate = True
                                        break
                                
                                # Check in newly created assets in this session
                                if not is_duplicate:
                                    for created_asset in created_assets:
                                        if created_asset.get("type") == "bank_account":
                                            created_account_number = created_asset.get("account_number", "")
                                            created_bank_name = created_asset.get("bank_name", "")
                                            created_account_type = created_asset.get("account_type", "")
                                            # Match by account number if both have it, otherwise match by bank name + account type
                                            if account_number and created_account_number:
                                                if account_number.lower() == created_account_number.lower() and bank_name.lower() == created_bank_name.lower():
                                                    print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Duplicate found in newly created assets - {bank_name} (Account: {account_number})")
                                                    is_duplicate = True
                                                    break
                                            elif bank_name.lower() == created_bank_name.lower() and account_type == created_account_type:
                                                print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Duplicate found in newly created assets - {bank_name} (Type: {account_type})")
                                                is_duplicate = True
                                                break
                                
                                if is_duplicate:
                                    print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Skipping duplicate bank account - {bank_name}")
                                    continue
                                
                                # Insert into database
                                print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Inserting into database - {bank_name}")
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    print(f"DEBUG: Page {page_idx + 1}, BA {ba_idx + 1}: Successfully created - {bank_name}")
                                    created_assets.append(response.data[0])
                                    # Also add to existing_bank_accounts list to prevent duplicates in subsequent pages
                                    existing_bank_accounts.append({
                                        "bank_name": bank_name,
                                        "account_number": account_number,
                                        "account_type": account_type
                                    })
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create bank account: {bank_name}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                import traceback
                                print(f"Error processing bank account from page {page_idx + 1}: {e}")
                                print(traceback.format_exc())
                                errors.append(f"Page {page_idx + 1}: Error processing bank account: {str(e)}")
                    
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
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    print(f"DEBUG: Waiting 5 seconds before processing next page...")
                    await asyncio.sleep(5)
        
        elif asset_type == "mutual_fund":
            # Import LLM service for direct JSON calls
            from google import genai
            from google.genai import types
            import asyncio
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not found in environment variables")
            
            client = genai.Client(api_key=api_key)
            
            # Fetch existing mutual funds to prevent duplicates
            existing_mutual_funds = []
            try:
                existing_assets_response = supabase_service.table("assets").select("mutual_fund_code, name, fund_house").eq("user_id", user_id).eq("type", "mutual_fund").eq("is_active", True).execute()
                existing_mutual_funds = existing_assets_response.data if existing_assets_response.data else []
                print(f"DEBUG: Found {len(existing_mutual_funds)} existing mutual funds")
            except Exception as e:
                print(f"Error fetching existing mutual funds: {e}")
            
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
            print(f"DEBUG: Starting to process {len(pdf_pages)} pages from PDF for mutual funds")
            
            # Store context from previous pages (input and output pairs)
            previous_contexts = []
            
            for page_idx, page_content in enumerate(pdf_pages):
                print(f"DEBUG: Processing page {page_idx + 1} of {len(pdf_pages)} for mutual funds")
                if not page_content or not page_content.strip():
                    print(f"DEBUG: Page {page_idx + 1} is empty, skipping")
                    continue
                
                print(f"DEBUG: Page {page_idx + 1} content length: {len(page_content)} characters")
                try:
                    # Build instruction prompt
                    instruction_prompt = f"""Your task is to extract mutual fund information from the document. DO NOT include stocks, bank accounts, fixed deposits, or any other investment types. Only extract mutual funds.

CRITICAL RULES - READ CAREFULLY

1. HOW TO IDENTIFY A MUTUAL FUND: A mutual fund can be identified by the presence of a NAV (Net Asset Value) property or field. If an investment/asset has a NAV value, it is a mutual fund. Look for labels like "NAV", "Net Asset Value", "Current NAV", or "NAV per Unit" in the document. If you see NAV mentioned for an investment, treat it as a mutual fund and extract it.
2. SIP-BASED MUTUAL FUNDS: Note that mutual funds can be SIP-based (Systematic Investment Plan) or lump-sum investments. Both types should be extracted. SIP-based mutual funds are still mutual funds and should be included.
3. DO NOT PERFORM ANY CALCULATIONS WHATSOEVER. ONLY EXTRACT VALUES EXACTLY AS THEY APPEAR IN THE DOCUMENT.
4. ALL VALUES MUST BE EXACTLY AS SHOWN IN THE PDF - NO ROUNDING, NO MODIFICATIONS, NO CALCULATIONS.
5. DUPLICATE PREVENTION: Check the following list of ALREADY ADDED mutual funds. If a mutual fund from the document matches any of these (same fund code, or same fund name and fund house if code is not available), DO NOT include it in your response. Return an empty JSON array [] if all mutual funds on this page are already added.
6. YOU MUST EXTRACT ALL NEW MUTUAL FUNDS FROM THE PAGE - DO NOT SKIP ANY NEW MUTUAL FUND. However, skip any mutual funds that are duplicates of already added funds.

ALREADY ADDED MUTUAL FUNDS:
{existing_funds_text if existing_funds_text else "No mutual funds have been added yet."}

IMPORTANT: A mutual fund is considered a duplicate if:
- The fund code matches (if fund code is available in both)
- OR the fund name matches AND fund house matches (if fund code is not available in either)

If you find a duplicate, skip it and do not include it in your response. Only return NEW mutual funds that are not in the list above.

Return the mutual funds in a JSON format. Do not include any other text in your response. Only return the JSON.

Each JSON object MUST have the following keys with EXACT names:

REQUIRED FIELDS (must be present for every mutual fund):
1. "Fund Name" - REQUIRED - Extract the name of the mutual fund EXACTLY as shown in the document
2. "Fund Code" - REQUIRED - Extract the mutual fund code/identifier EXACTLY as shown in the document. Look for "Fund Code", "Scheme Code", "ISIN", or "Code" labels. CRITICAL: If you cannot find a fund code in the document for a mutual fund, DO NOT include that mutual fund in your response. Only return mutual funds that have a fund code clearly visible in the document.
3. "Units" - REQUIRED - Extract the number of units held EXACTLY as shown in the document. Look for "Units", "No. of Units", or "Quantity" labels. Extract the EXACT value - do not round, modify, or calculate.
4. "Fund House" - Optional - Extract the fund house/AMC (Asset Management Company) name EXACTLY as shown in the document. Look for "Fund House", "AMC", "Asset Management Company", or "Scheme Name" labels.
5. "NAV" - Optional - Extract the Net Asset Value per unit EXACTLY as shown in the document. Look for "NAV", "Net Asset Value", or "Current NAV" labels. Extract the EXACT value - do not round, modify, or calculate.
6. "Purchase Date" - Optional - Extract the purchase date in YYYY-MM-DD format. Look for "Purchase Date", "Date of Investment", or "Investment Date" labels. If not available, leave as null.
7. "Value at Cost" - Optional - Extract the total amount invested (value at cost) EXACTLY as shown in the document. Look for "Value at Cost", "Amount Invested", "Total Invested", "Investment Amount", or "Purchase Value" labels. Extract the EXACT value - do not round, modify, or calculate. DO NOT calculate this as Units * NAV. The document already contains this value - extract it EXACTLY as it appears.
8. "Current Value" - Optional - Extract the current market value EXACTLY as shown in the document. Look for "Current Value", "Current Worth", or "Market Value" labels. Extract the EXACT value - do not round, modify, or calculate.
9. "Owner Name" - Optional - Primary holder's name. If not provided, use "self"

CRITICAL REQUIREMENTS:
1. HOW TO IDENTIFY A MUTUAL FUND: A mutual fund can be identified by the presence of a NAV (Net Asset Value) property or field. If an investment/asset has a NAV value, it is a mutual fund. Look for labels like "NAV", "Net Asset Value", "Current NAV", or "NAV per Unit" in the document. If you see NAV mentioned for an investment, treat it as a mutual fund and extract it.
2. SIP-based mutual funds are still mutual funds and should be extracted. Look for mutual funds regardless of whether they are SIP-based or lump-sum investments.
3. You MUST provide "Fund Name", "Fund Code", and "Units" for EVERY mutual fund. These are mandatory fields. IF A FUND CODE IS NOT AVAILABLE IN THE DOCUMENT, DO NOT INCLUDE THAT MUTUAL FUND IN YOUR RESPONSE.
4. ABSOLUTELY NO CALCULATIONS ALLOWED - Extract all numeric values EXACTLY as they appear in the document. If the document shows "1,234.56", extract it as "1,234.56" (preserve formatting as shown).
5. For "Fund Code": Extract the fund code EXACTLY as shown. Look for labels like "Fund Code", "Scheme Code", "ISIN", or "Code". THIS FIELD IS REQUIRED - if you cannot find a fund code in the document, DO NOT include that mutual fund in your response.
6. For "Units": Find the number of units in the document and copy it EXACTLY as shown. DO NOT calculate, round, or modify it.
7. For "NAV": Extract the NAV per unit EXACTLY as shown. This is a key identifier for mutual funds - if NAV is present, the investment is a mutual fund. DO NOT calculate or modify it.
8. For "Value at Cost": Extract the total amount invested (value at cost) EXACTLY as shown. Look for "Value at Cost", "Amount Invested", "Total Invested", or "Investment Amount" labels. DO NOT calculate it as Units * NAV. DO NOT perform any multiplication. The document already contains this value - extract it EXACTLY as it appears.
9. For "Current Value": Extract the current market value EXACTLY as shown. DO NOT calculate it as Units * NAV. DO NOT perform any multiplication. The document already contains this value - extract it EXACTLY as it appears.
10. REMEMBER: If an investment has a NAV (Net Asset Value) property, it is a mutual fund. Use NAV as the key identifier to distinguish mutual funds from stocks, bank accounts, fixed deposits, or other investment types.
11. DUPLICATE CHECK: Before including any mutual fund in your response, check if it already exists in the "ALREADY ADDED MUTUAL FUNDS" list above. Compare by:
   - Fund code (if available in both)
   - OR fund name and fund house (if fund code is not available)
   - If a match is found, DO NOT include that mutual fund in your response.
12. YOU MUST EXTRACT ALL NEW MUTUAL FUNDS FROM THE PAGE - DO NOT SKIP ANY NEW MUTUAL FUND. However, skip any mutual funds that are duplicates of already added funds.
13. Extract values EXACTLY as they appear in the document - preserve decimal places, commas, and formatting as shown in the PDF.

Return a JSON array of mutual fund objects. If there are multiple NEW mutual funds on this page (not duplicates), return ALL of them in the array. If all mutual funds on this page are duplicates, return an empty array []. DO NOT skip any new mutual fund, but DO skip duplicates."""
                    
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
                                "parts": [{"text": f"Here is a summary of all the mutual funds from page {prev_idx + 1}:\n\n{prev_input}"}]
                            })
                            # Add previous assistant response (LLM output)
                            contents.append({
                                "role": "model",
                                "parts": [{"text": prev_output}]
                            })
                    
                    # Add current page as user message
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"Here is a summary of all the mutual funds from page {page_idx + 1}:\n\n{page_content}"}]
                    })
                    
                    # Call Gemini with JSON mode
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                    
                    # Get model name from environment or use default (gemini-2.5-flash has higher quota limits)
                    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=model_name,
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
                        
                        mutual_funds = json.loads(cleaned_response)
                        # Handle both single object and array
                        if not isinstance(mutual_funds, list):
                            mutual_funds = [mutual_funds]
                        
                        print(f"DEBUG: Page {page_idx + 1}: LLM returned {len(mutual_funds)} mutual fund(s)")
                        
                        # Store input and output for future context (for pages after the first)
                        previous_contexts.append((page_content, cleaned_response))
                        print(f"DEBUG: Page {page_idx + 1}: Stored context for future pages (total contexts: {len(previous_contexts)})")
                        
                        # Skip if empty array (no mutual funds on this page)
                        if len(mutual_funds) == 0:
                            print(f"DEBUG: Page {page_idx + 1}: Empty array returned (no mutual funds on this page), continuing to next page")
                            continue
                        
                        # Process each mutual fund
                        for mf_idx, mf_data in enumerate(mutual_funds):
                            print(f"DEBUG: Page {page_idx + 1}, Mutual Fund {mf_idx + 1}: Processing {mf_data}")
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
                                
                                print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Extracted fields - name={fund_name}, code={fund_code}, units={units}, nav={nav}, value_at_cost={value_at_cost}, current_value={current_value}")
                                
                                # Validate required fields (fund_code is required)
                                if not fund_name or not fund_code or units is None:
                                    error_msg = f"Page {page_idx + 1}, MF {mf_idx + 1}: Missing required fields (fund_name, fund_code, or units)"
                                    print(f"DEBUG: {error_msg}")
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
                                    print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Using extracted Units: {units_float}")
                                except (ValueError, TypeError) as e:
                                    error_msg = f"Page {page_idx + 1}, MF {mf_idx + 1}: Invalid units value: {units}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    continue
                                
                                # Convert NAV to float if provided (clean numeric strings first)
                                nav_float = None
                                if nav:
                                    try:
                                        nav_cleaned = clean_numeric_string(nav)
                                        nav_float = float(nav_cleaned)
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Using extracted NAV: {nav_float}")
                                    except (ValueError, TypeError):
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Could not parse NAV: {nav}, leaving as None")
                                
                                # Convert value_at_cost to float if provided (clean numeric strings first)
                                value_at_cost_float = None
                                if value_at_cost:
                                    try:
                                        value_at_cost_cleaned = clean_numeric_string(value_at_cost)
                                        value_at_cost_float = float(value_at_cost_cleaned)
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Using extracted Value at Cost: {value_at_cost_float}")
                                    except (ValueError, TypeError):
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Could not parse Value at Cost: {value_at_cost}, leaving as None")
                                
                                # Convert current_value to float if provided (clean numeric strings first)
                                current_value_float = None
                                if current_value:
                                    try:
                                        current_value_cleaned = clean_numeric_string(current_value)
                                        current_value_float = float(current_value_cleaned)
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Using extracted Current Value: {current_value_float}")
                                    except (ValueError, TypeError):
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Could not parse Current Value: {current_value}, setting to 0")
                                        current_value_float = 0.0
                                else:
                                    # If not provided, set to 0 (do not calculate)
                                    current_value_float = 0.0
                                    print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Current Value not found in document, setting to 0")
                                
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
                                                print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Could not parse purchase date: {purchase_date_str}, leaving as None")
                                
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
                                    print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Stored Value at Cost in notes: {value_at_cost_float}")
                                
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
                                        print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Duplicate found in existing funds - {fund_name} (Code: {fund_code})")
                                        is_duplicate = True
                                        break
                                
                                # Check in newly created assets in this session
                                if not is_duplicate:
                                    for created_asset in created_assets:
                                        if created_asset.get("type") == "mutual_fund":
                                            created_code = created_asset.get("mutual_fund_code", "")
                                            if created_code and fund_code and created_code.lower() == fund_code.lower():
                                                print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Duplicate found in newly created assets - {fund_name} (Code: {fund_code})")
                                                is_duplicate = True
                                                break
                                
                                if is_duplicate:
                                    print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Skipping duplicate mutual fund - {fund_name} (Code: {fund_code})")
                                    continue
                                
                                # Insert into database
                                print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Inserting into database - {fund_name}")
                                response = supabase_service.table("assets").insert(asset_dict).execute()
                                if response.data and len(response.data) > 0:
                                    print(f"DEBUG: Page {page_idx + 1}, MF {mf_idx + 1}: Successfully created - {fund_name}")
                                    created_assets.append(response.data[0])
                                    # Also add to existing_mutual_funds list to prevent duplicates in subsequent pages
                                    existing_mutual_funds.append({
                                        "mutual_fund_code": fund_code,
                                        "name": fund_name,
                                        "fund_house": fund_house
                                    })
                                else:
                                    error_msg = f"Page {page_idx + 1}: Failed to create mutual fund: {fund_name}"
                                    print(f"DEBUG: {error_msg}")
                                    errors.append(error_msg)
                                    
                            except Exception as e:
                                import traceback
                                print(f"Error processing mutual fund from page {page_idx + 1}: {e}")
                                print(traceback.format_exc())
                                errors.append(f"Page {page_idx + 1}: Error processing mutual fund: {str(e)}")
                    
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
                
                # Add 5-second delay after processing each page to prevent LLM overload
                if page_idx < len(pdf_pages) - 1:  # Don't delay after the last page
                    print(f"DEBUG: Waiting 5 seconds before processing next page...")
                    await asyncio.sleep(5)
        
        else:
            errors.append(f"Unsupported asset type: {asset_type}")
        
        print(f"DEBUG: Finished processing all pages. Created {len(created_assets)} assets, {len(errors)} errors")
        
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
        import traceback
        print(f"Error in upload_pdf_for_asset_type: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

