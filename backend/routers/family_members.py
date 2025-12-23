"""
Family Members API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import FamilyMember, FamilyMemberCreate, FamilyMemberUpdate
from database.supabase_client import supabase, supabase_service
from auth import get_current_user

router = APIRouter(prefix="/api/family-members", tags=["family-members"])


@router.get("/", response_model=List[FamilyMember])
async def get_family_members(current_user=Depends(get_current_user)):
    """Get all family members for the current user"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        print(f"Fetching family members for user_id: {user_id}")
        
        # Use service role client to bypass RLS (user already validated via get_current_user)
        response = supabase_service.table("family_members").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        
        family_members = response.data if response.data else []
        print(f"Found {len(family_members)} family members for user {user_id}")
        if len(family_members) > 0:
            print(f"Sample family member: {family_members[0]}")
        
        return family_members
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching family members: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"ERROR fetching family members: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch family members: {str(e)}")


@router.post("/", response_model=FamilyMember)
async def create_family_member(family_member: FamilyMemberCreate, current_user=Depends(get_current_user)):
    """Create a new family member"""
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
            family_member_data = family_member.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        except AttributeError:
            # Fallback for older Pydantic versions
            family_member_data = family_member.dict(exclude_unset=True, exclude_none=True)
        
        family_member_data["user_id"] = user_id
        
        # Use service role client to bypass RLS (user already validated via get_current_user)
        try:
            response = supabase_service.table("family_members").insert(family_member_data).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file."
                )
            raise
        
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create family member")
        
        created_member = response.data[0]
        print(f"Successfully created family member: id={created_member.get('id')}, name={created_member.get('name')}, relationship={created_member.get('relationship')}")
        return created_member
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating family member: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to create family member: {str(e)}")


@router.get("/{family_member_id}", response_model=FamilyMember)
async def get_family_member(family_member_id: str, current_user=Depends(get_current_user)):
    """Get a specific family member"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Use service role client to bypass RLS (user already validated via get_current_user)
        response = supabase_service.table("family_members").select("*").eq("id", family_member_id).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Family member not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching family member {family_member_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch family member: {str(e)}")


@router.put("/{family_member_id}", response_model=FamilyMember)
async def update_family_member(family_member_id: str, family_member: FamilyMemberUpdate, current_user=Depends(get_current_user)):
    """Update a family member"""
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
            update_data = family_member.model_dump(exclude_unset=True, exclude_none=True, mode='json')
        except AttributeError:
            # Fallback for older Pydantic versions
            update_data = family_member.dict(exclude_unset=True, exclude_none=True)
        
        # Use service role client to bypass RLS (user already validated via get_current_user)
        try:
            response = supabase_service.table("family_members").update(update_data).eq("id", family_member_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file."
                )
            raise
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Family member not found")
        
        updated_member = response.data[0]
        print(f"Successfully updated family member: id={updated_member.get('id')}, name={updated_member.get('name')}")
        return updated_member
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error updating family member: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to update family member: {str(e)}")


@router.delete("/{family_member_id}")
async def delete_family_member(family_member_id: str, current_user=Depends(get_current_user)):
    """Delete a family member"""
    try:
        # Extract user_id safely
        if hasattr(current_user, 'user') and hasattr(current_user.user, 'id'):
            user_id = str(current_user.user.id)
        elif hasattr(current_user, 'id'):
            user_id = str(current_user.id)
        else:
            raise HTTPException(status_code=401, detail="Unable to extract user ID from token")
        
        # Use service role client to bypass RLS (user already validated via get_current_user)
        try:
            response = supabase_service.table("family_members").delete().eq("id", family_member_id).eq("user_id", user_id).execute()
        except Exception as rls_error:
            error_msg = str(rls_error)
            if "row-level security" in error_msg.lower() or "42501" in error_msg:
                raise HTTPException(
                    status_code=500,
                    detail="RLS policy violation. Please set SUPABASE_SERVICE_ROLE_KEY in your .env file."
                )
            raise
        
        # Also set family_member_id to NULL for all assets assigned to this family member
        # This is handled by the foreign key constraint ON DELETE SET NULL, but we can do it explicitly
        try:
            supabase_service.table("assets").update({"family_member_id": None}).eq("family_member_id", family_member_id).execute()
        except Exception as e:
            print(f"Warning: Could not unassign assets from deleted family member: {str(e)}")
        
        print(f"Successfully deleted family member: id={family_member_id}")
        return {"message": "Family member deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error deleting family member: {str(e)}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to delete family member: {str(e)}")

