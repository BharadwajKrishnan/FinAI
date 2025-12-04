"""
Accounts API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Account, AccountCreate, AccountUpdate
from database.supabase_client import supabase
from auth import get_current_user

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/", response_model=List[Account])
async def get_accounts(current_user=Depends(get_current_user)):
    """Get all accounts for the current user"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("accounts").select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch accounts: {str(e)}")


@router.post("/", response_model=Account)
async def create_account(account: AccountCreate, current_user=Depends(get_current_user)):
    """Create a new account"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        account_data = account.dict()
        account_data["user_id"] = user_id
        
        response = supabase.table("accounts").insert(account_data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create account")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create account: {str(e)}")


@router.get("/{account_id}", response_model=Account)
async def get_account(account_id: str, current_user=Depends(get_current_user)):
    """Get a specific account"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("accounts").select("*").eq("id", account_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Account not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch account: {str(e)}")


@router.put("/{account_id}", response_model=Account)
async def update_account(account_id: str, account: AccountUpdate, current_user=Depends(get_current_user)):
    """Update an account"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        update_data = account.dict(exclude_unset=True)
        
        response = supabase.table("accounts").update(update_data).eq("id", account_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Account not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update account: {str(e)}")


@router.delete("/{account_id}")
async def delete_account(account_id: str, current_user=Depends(get_current_user)):
    """Delete an account"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("accounts").delete().eq("id", account_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"message": "Account deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

