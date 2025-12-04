"""
Categories API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Category, CategoryCreate, CategoryUpdate
from database.supabase_client import supabase
from auth import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/", response_model=List[Category])
async def get_categories(current_user=Depends(get_current_user)):
    """Get all categories for the current user"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("categories").select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch categories: {str(e)}")


@router.post("/", response_model=Category)
async def create_category(category: CategoryCreate, current_user=Depends(get_current_user)):
    """Create a new category"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        category_data = category.dict()
        category_data["user_id"] = user_id
        
        response = supabase.table("categories").insert(category_data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create category")
        return response.data[0]
    except Exception as e:
        error_msg = str(e)
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Category with this name and type already exists")
        raise HTTPException(status_code=500, detail=f"Failed to create category: {error_msg}")


@router.get("/{category_id}", response_model=Category)
async def get_category(category_id: str, current_user=Depends(get_current_user)):
    """Get a specific category"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("categories").select("*").eq("id", category_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Category not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch category: {str(e)}")


@router.put("/{category_id}", response_model=Category)
async def update_category(category_id: str, category: CategoryUpdate, current_user=Depends(get_current_user)):
    """Update a category"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        update_data = category.dict(exclude_unset=True)
        
        response = supabase.table("categories").update(update_data).eq("id", category_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Category not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")


@router.delete("/{category_id}")
async def delete_category(category_id: str, current_user=Depends(get_current_user)):
    """Delete a category"""
    try:
        user_id = current_user.user.id if hasattr(current_user, 'user') else current_user.id
        response = supabase.table("categories").delete().eq("id", category_id).eq("user_id", user_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Category not found")
        return {"message": "Category deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")

