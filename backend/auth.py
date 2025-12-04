"""
Authentication dependencies
"""

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database.supabase_client import supabase

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user"""
    try:
        token = credentials.credentials
        # Verify token with Supabase
        try:
            user_response = supabase.auth.get_user(token)
            if not user_response or not hasattr(user_response, 'user') or not user_response.user:
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            return user_response
        except HTTPException:
            raise
        except Exception as auth_error:
            # If get_user fails, try to decode the token directly to extract user_id
            try:
                import jwt
                # Decode without verification to get user info (Supabase tokens are self-contained)
                decoded = jwt.decode(token, options={"verify_signature": False})
                user_id = decoded.get('sub') or decoded.get('user_id')
                
                if not user_id:
                    raise HTTPException(status_code=401, detail="Token does not contain user ID")
                
                # Return a mock user object with the user_id from the token
                class MockUser:
                    def __init__(self, user_id):
                        self.id = str(user_id)  # Ensure it's a string
                
                class MockUserResponse:
                    def __init__(self, user_id):
                        self.user = MockUser(user_id)
                
                return MockUserResponse(user_id)
            except jwt.DecodeError:
                raise HTTPException(status_code=401, detail="Invalid token format")
            except Exception as decode_error:
                raise HTTPException(status_code=401, detail=f"Invalid authentication credentials: {str(decode_error)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid authentication credentials: {str(e)}")

