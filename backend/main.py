"""
FinanceApp Backend API
Python FastAPI backend for FinanceApp
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
from database.supabase_client import supabase
from auth import get_current_user

load_dotenv()

app = FastAPI(title="FinanceApp API", version="1.0.0")

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
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "name": user_data.name
                }
            }
        })
        
        if not response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
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
        # Log the full error for debugging
        print(f"Signup error: {error_message}")
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
from routers import assets, chat

app.include_router(assets.router)
app.include_router(chat.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

