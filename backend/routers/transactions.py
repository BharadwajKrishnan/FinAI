"""
Transactions API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import date
from models import Transaction, TransactionCreate, TransactionUpdate
from database.supabase_client import supabase
from auth import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/", response_model=List[Transaction])
async def get_transactions(
    account_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user=Depends(get_current_user)
):
    """Get all transactions for the current user with optional filters"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        query = supabase.table("transactions").select("*").eq("user_id", user_id)
        
        if account_id:
            query = query.eq("account_id", account_id)
        if category_id:
            query = query.eq("category_id", category_id)
        if start_date:
            query = query.gte("date", start_date.isoformat())
        if end_date:
            query = query.lte("date", end_date.isoformat())
        
        query = query.order("date", desc=True)
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")


@router.post("/", response_model=Transaction)
async def create_transaction(transaction: TransactionCreate, current_user=Depends(get_current_user)):
    """Create a new transaction"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        transaction_data = transaction.dict()
        transaction_data["user_id"] = user_id
        transaction_data["date"] = transaction_data["date"].isoformat()
        
        response = supabase.table("transactions").insert(transaction_data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create transaction")
        
        # Update account balance
        account_response = supabase.table("accounts").select("balance, type").eq("id", transaction.account_id).eq("user_id", user_id).execute()
        if account_response.data:
            current_balance = float(account_response.data[0]["balance"])
            amount = float(transaction.amount)
            
            if transaction.type == "income":
                new_balance = current_balance + amount
            elif transaction.type == "expense":
                new_balance = current_balance - amount
            else:  # transfer
                new_balance = current_balance - amount
            
            supabase.table("accounts").update({"balance": str(new_balance)}).eq("id", transaction.account_id).execute()
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(transaction_id: str, current_user=Depends(get_current_user)):
    """Get a specific transaction"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("transactions").select("*").eq("id", transaction_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch transaction: {str(e)}")


@router.put("/{transaction_id}", response_model=Transaction)
async def update_transaction(transaction_id: str, transaction: TransactionUpdate, current_user=Depends(get_current_user)):
    """Update a transaction"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        update_data = transaction.dict(exclude_unset=True)
        
        if "date" in update_data:
            update_data["date"] = update_data["date"].isoformat()
        
        response = supabase.table("transactions").update(update_data).eq("id", transaction_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update transaction: {str(e)}")


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: str, current_user=Depends(get_current_user)):
    """Delete a transaction"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("transactions").delete().eq("id", transaction_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"message": "Transaction deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")

