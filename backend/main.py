"""
FinanceApp Backend API
Python FastAPI backend for FinanceApp
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from database.supabase_client import supabase
from auth import get_current_user

load_dotenv()

app = FastAPI(title="FinanceApp API", version="1.0.0")

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with detailed logging"""
    import json
    errors = exc.errors()
    error_details = []
    for error in errors:
        error_details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    print(f"Validation error on {request.url.path}:")
    print(json.dumps(error_details, indent=2))
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": error_details,
            "message": "Validation error: Please check the request data"
        }
    )

# CORS middleware to allow frontend requests
# Get allowed origins from environment variable or use defaults
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
).split(",")

# Add Vercel preview URLs pattern (will be set via environment variable in production)
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    allowed_origins.append(f"https://{vercel_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginResponse(BaseModel):
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None


@app.get("/")
async def root():
    return {"message": "FinanceApp API", "status": "running"}


@app.post("/api/auth/signup", response_model=LoginResponse)
async def signup(user_data: SignupRequest):
    """
    Register a new user
    """
    try:
        # Create user in Supabase Auth
        # Note: If there's a database trigger (like creating user_profiles) that's failing,
        # you may need to check your Supabase database triggers and functions
        try:
            response = supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "data": {
                        "name": user_data.name
                    }
                }
            })
        except Exception as auth_error:
            error_str = str(auth_error)
            # Check for database-related errors from Supabase
            if "Database error" in error_str or "500" in error_str:
                print(f"ERROR: Supabase auth signup failed with database error: {error_str}")
                print("\n" + "="*70)
                print("DIAGNOSIS: This is a database-level error, not a code issue.")
                print("="*70)
                print("\nMost likely causes:")
                print("1. A database trigger on auth.users is failing")
                print("2. A database function called during signup has an error")
                print("3. A constraint violation in a related table")
                print("\nIMMEDIATE FIX:")
                print("Since user_profiles table was removed, you need to remove the trigger:")
                print("Run this SQL in your Supabase SQL Editor:")
                print("  DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
                print("  DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;")
                print("\nOr use the script: backend/database/remove_user_profiles_trigger.sql")
                print("\nDIAGNOSTIC:")
                print("Run this SQL to check what's causing the issue:")
                print("  backend/database/fix_signup_error.sql")
                print("="*70 + "\n")
                # Re-raise with a more user-friendly message
                raise HTTPException(
                    status_code=500,
                    detail="Database error during signup. This is usually caused by a database trigger or function. Please check the backend logs for detailed instructions, or run the diagnostic scripts in backend/database/ to identify and fix the issue."
                )
            raise
        
        if not response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        # Create default "Self" family member for the new user
        # This is wrapped in try-except so signup doesn't fail if family member creation fails
        try:
            from database.supabase_client import supabase_service
            user_id = str(response.user.id)
            user_name = user_data.name or user_data.email.split("@")[0].title()
            
            self_family_member = {
                "user_id": user_id,
                "name": user_name,
                "relationship": "Self"
            }
            
            # Use service role client to bypass RLS for initial setup
            try:
                family_member_response = supabase_service.table("family_members").insert(self_family_member).execute()
                if family_member_response.data:
                    print(f"Successfully created default 'Self' family member for user {user_id} with name '{user_name}'")
                else:
                    print(f"Warning: Failed to create default 'Self' family member for user {user_id}")
            except Exception as insert_error:
                error_str = str(insert_error)
                # Check if it's a constraint error
                if "check constraint" in error_str.lower() or "23514" in error_str:
                    print(f"ERROR: Database constraint violation when creating 'Self' family member.")
                    print(f"Error details: {error_str}")
                    print("The database constraint needs to be updated to allow 'Self' as a relationship value.")
                    print("Please run the migration script in Supabase SQL Editor:")
                    print("  backend/database/add_self_relationship.sql")
                    # Don't fail signup - the user can still use the app, and the 'Self' member will be created
                    # automatically when they first access the family members endpoint
                    print("User signup will continue, but 'Self' family member will be created on first access.")
                else:
                    # Other errors - log but don't fail signup
                    print(f"Warning: Could not create default 'Self' family member during signup: {error_str}")
                    import traceback
                    print(traceback.format_exc())
        except Exception as fm_error:
            # Outer catch - shouldn't happen, but just in case
            print(f"Warning: Unexpected error in family member creation: {str(fm_error)}")
            import traceback
            print(traceback.format_exc())
        
        # Check if email confirmation is required
        # If session is None, email confirmation is required
        if response.session is None:
            # User created but needs to confirm email
            return LoginResponse(
                message="User created successfully. Please check your email to confirm your account before signing in.",
                access_token=None,
                refresh_token=None,
                user={
                    "id": response.user.id,
                    "email": response.user.email,
                    "name": user_data.name
                }
            )
        
        # Email confirmation is disabled, user can sign in immediately
        return LoginResponse(
            message="User created successfully",
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "name": user_data.name
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
            error_message = str(e)
            # Check for various "user exists" error patterns from Supabase
            if any(keyword in error_message.lower() for keyword in [
                "already registered", 
                "already exists", 
                "user already registered",
                "email address is already registered"
            ]):
                raise HTTPException(
                    status_code=400, 
                    detail=f"User with email {user_data.email} already exists. Please use a different email or try logging in instead."
                )
            # Check for database constraint errors
            if "check constraint" in error_message.lower() or "23514" in error_message:
                print(f"Database constraint error during signup: {error_message}")
                print("NOTE: The database constraint needs to be updated to allow 'Self' as a relationship value.")
                print("Please run the migration script: backend/database/add_self_relationship.sql")
                raise HTTPException(
                    status_code=500,
                    detail="Database configuration error. Please contact support or run the database migration script."
                )
            # Log the full error for debugging
            print(f"Signup error: {error_message}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Failed to create user: {error_message}")


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """
    Authenticate user and return token
    """
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not response.session:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user_data = response.user
        return LoginResponse(
            message="Login successful",
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            user={
                "id": user_data.id,
                "email": user_data.email,
                "name": user_data.user_metadata.get("name") if user_data.user_metadata else None
            }
        )
    except Exception as e:
        error_message = str(e)
        if "invalid" in error_message.lower() or "wrong" in error_message.lower():
            raise HTTPException(status_code=401, detail="Invalid email or password")
        raise HTTPException(status_code=500, detail=f"Login failed: {error_message}")


@app.post("/api/auth/logout")
async def logout(current_user: Dict = Depends(get_current_user)):
    """
    Logout user
    """
    try:
        # Note: Supabase client-side logout is typically handled on the frontend
        # This endpoint can be used for server-side session cleanup if needed
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
    try:
        user = current_user.user if hasattr(current_user, 'user') else current_user
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.user_metadata.get("name") if user.user_metadata else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user info: {str(e)}")


# Include routers
from routers import assets, chat, expenses, family_members

app.include_router(assets.router)
app.include_router(chat.router)
app.include_router(expenses.router)
app.include_router(family_members.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

