"""
Assets API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from models import Asset, AssetCreate, AssetUpdate, AssetType
from database.supabase_client import supabase
from auth import get_current_user

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
        
        query = supabase.table("assets").select("*").eq("user_id", user_id)
        
        if asset_type:
            query = query.eq("type", asset_type.value)
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        query = query.order("created_at", desc=True)
        response = query.execute()
        return response.data
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching assets: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch assets: {str(e)}")


@router.post("/", response_model=Asset)
async def create_asset(asset: AssetCreate, current_user=Depends(get_current_user)):
    """Create a new asset"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        asset_data = asset.dict(exclude_unset=True, exclude_none=True)
        asset_data["user_id"] = user_id
        
        # Convert date objects to strings for Supabase
        date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date']
        for field in date_fields:
            if field in asset_data and asset_data[field]:
                asset_data[field] = asset_data[field].isoformat() if hasattr(asset_data[field], 'isoformat') else asset_data[field]
        
        # Convert Decimal to string for Supabase
        decimal_fields = [
            'current_value', 'quantity', 'purchase_price', 'current_price',
            'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate'
        ]
        for field in decimal_fields:
            if field in asset_data and asset_data[field] is not None:
                asset_data[field] = str(asset_data[field])
        
        response = supabase.table("assets").insert(asset_data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create asset")
        return response.data[0]
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
        date_fields = ['purchase_date', 'nav_purchase_date', 'maturity_date', 'start_date']
        for field in date_fields:
            if field in update_data and update_data[field]:
                update_data[field] = update_data[field].isoformat() if hasattr(update_data[field], 'isoformat') else update_data[field]
        
        # Convert Decimal to string
        decimal_fields = [
            'current_value', 'quantity', 'purchase_price', 'current_price',
            'nav', 'units', 'interest_rate', 'principal_amount', 'fd_interest_rate'
        ]
        for field in decimal_fields:
            if field in update_data and update_data[field] is not None:
                update_data[field] = str(update_data[field])
        
        response = supabase.table("assets").update(update_data).eq("id", asset_id).eq("user_id", user_id).execute()
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
        response = supabase.table("assets").delete().eq("id", asset_id).eq("user_id", user_id).execute()
        if not response.data:
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

