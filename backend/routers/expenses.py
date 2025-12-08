"""
Expenses API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from typing import List, Optional
from datetime import date
from models import Expense, ExpenseCreate, ExpenseUpdate
from database.supabase_client import supabase, supabase_service, get_supabase_client_with_token
from auth import get_current_user, security

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("/", response_model=List[Expense])
async def get_expenses(
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, description="Filter by month (1-12)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    current_user=Depends(get_current_user)
):
    """Get all expenses for the current user with optional filters"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        query = supabase.table("expenses").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("expense_date", start_date.isoformat())
        if end_date:
            query = query.lte("expense_date", end_date.isoformat())
        if year:
            # Filter by year using date range
            start_year = date(year, 1, 1)
            end_year = date(year, 12, 31)
            query = query.gte("expense_date", start_year.isoformat())
            query = query.lte("expense_date", end_year.isoformat())
        if month and year:
            # Filter by specific month and year
            start_month = date(year, month, 1)
            # Get last day of month
            if month == 12:
                end_month = date(year + 1, 1, 1)
            else:
                end_month = date(year, month + 1, 1)
            query = query.gte("expense_date", start_month.isoformat())
            query = query.lt("expense_date", end_month.isoformat())
        if category:
            query = query.eq("category", category)
        
        query = query.order("expense_date", desc=True)
        response = query.execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expenses: {str(e)}")


@router.get("/summary", response_model=dict)
async def get_expense_summary(
    year: Optional[int] = Query(None, description="Filter by year"),
    current_user=Depends(get_current_user)
):
    """Get expense summary grouped by month for a year"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        
        # Default to current year if not specified
        if not year:
            from datetime import datetime
            year = datetime.now().year
        
        # Get all expenses for the year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        query = supabase.table("expenses").select("*").eq("user_id", user_id)
        query = query.gte("expense_date", start_date.isoformat())
        query = query.lte("expense_date", end_date.isoformat())
        query = query.order("expense_date", desc=False)
        
        response = query.execute()
        
        # Group by month
        monthly_summary = {}
        for month in range(1, 13):
            monthly_summary[month] = {
                "month": month,
                "month_name": date(year, month, 1).strftime("%B"),
                "total": 0.0,
                "count": 0,
                "expenses": []
            }
        
        if response.data:
            for expense in response.data:
                expense_date = date.fromisoformat(expense["expense_date"])
                month = expense_date.month
                amount = float(expense["amount"])
                
                monthly_summary[month]["total"] += amount
                monthly_summary[month]["count"] += 1
                monthly_summary[month]["expenses"].append(expense)
        
        return {
            "year": year,
            "total": sum(m["total"] for m in monthly_summary.values()),
            "monthly_summary": list(monthly_summary.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expense summary: {str(e)}")


@router.post("/", response_model=Expense)
async def create_expense(
    expense: ExpenseCreate, 
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new expense"""
    try:
        # Get user's access token for RLS
        access_token = credentials.credentials
        
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        expense_data = expense.model_dump() if hasattr(expense, 'model_dump') else expense.dict()
        expense_data["user_id"] = user_id
        expense_data["expense_date"] = expense_data["expense_date"].isoformat() if hasattr(expense_data["expense_date"], 'isoformat') else expense_data["expense_date"]
        
        # Convert amount to string for Supabase
        if "amount" in expense_data and expense_data["amount"] is not None:
            expense_data["amount"] = str(expense_data["amount"])
        
        # Try using service role client first (bypasses RLS)
        # If that fails due to RLS, fall back to user token-based client
        try:
            response = supabase_service.table("expenses").insert(expense_data).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                # RLS is blocking - fall back to using user's token
                print(f"Service role failed, falling back to user token for expense creation")
                try:
                    # Use client with user's access token so RLS can identify the user
                    user_client = get_supabase_client_with_token(access_token)
                    response = user_client.table("expenses").insert(expense_data).execute()
                except Exception as fallback_error:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create expense: {str(fallback_error)}"
                    )
            else:
                raise
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create expense")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create expense: {str(e)}")


@router.get("/{expense_id}", response_model=Expense)
async def get_expense(expense_id: str, current_user=Depends(get_current_user)):
    """Get a specific expense"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("expenses").select("*").eq("id", expense_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Expense not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch expense: {str(e)}")


@router.put("/{expense_id}", response_model=Expense)
async def update_expense(
    expense_id: str, 
    expense: ExpenseUpdate, 
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update an expense"""
    try:
        access_token = credentials.credentials
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        update_data = expense.model_dump(exclude_unset=True) if hasattr(expense, 'model_dump') else expense.dict(exclude_unset=True)
        
        if "expense_date" in update_data and update_data["expense_date"]:
            update_data["expense_date"] = update_data["expense_date"].isoformat() if hasattr(update_data["expense_date"], 'isoformat') else update_data["expense_date"]
        
        # Convert amount to string for Supabase if present
        if "amount" in update_data and update_data["amount"] is not None:
            update_data["amount"] = str(update_data["amount"])
        
        # Try service role first, fall back to user token if RLS blocks
        try:
            response = supabase_service.table("expenses").update(update_data).eq("id", expense_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                user_client = get_supabase_client_with_token(access_token)
                response = user_client.table("expenses").update(update_data).eq("id", expense_id).eq("user_id", user_id).execute()
            else:
                raise
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Expense not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update expense: {str(e)}")


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: str, 
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete an expense"""
    try:
        access_token = credentials.credentials
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        
        # Try service role first, fall back to user token if RLS blocks
        try:
            response = supabase_service.table("expenses").delete().eq("id", expense_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                user_client = get_supabase_client_with_token(access_token)
                response = user_client.table("expenses").delete().eq("id", expense_id).eq("user_id", user_id).execute()
            else:
                raise
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Expense not found")
        return {"message": "Expense deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete expense: {str(e)}")
