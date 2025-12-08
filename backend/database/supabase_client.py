"""
Supabase client initialization
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
# Service role key bypasses RLS - use for backend operations where we've already validated the user
# IMPORTANT: Get this from Supabase Dashboard -> Settings -> API -> service_role key (secret)
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

# Base Supabase client (used for auth operations)
supabase: Client = create_client(supabase_url, supabase_key)

# Service role client (bypasses RLS - use when we've already validated user and set user_id)
# If service role key is not set, use the regular key (but RLS will still apply)
if supabase_service_role_key:
    supabase_service: Client = create_client(supabase_url, supabase_service_role_key)
    print("Using service role key - RLS will be bypassed")
else:
    # Fallback to regular key if service role not set
    supabase_service: Client = supabase
    print("WARNING: SUPABASE_SERVICE_ROLE_KEY not set. RLS policies will still apply.")
    print("To fix: Add SUPABASE_SERVICE_ROLE_KEY to your .env file (get it from Supabase Dashboard -> Settings -> API)")


def get_supabase_client_with_token(access_token: str) -> Client:
    """
    Create a Supabase client with user's access token for RLS policies
    This ensures that Row Level Security policies can identify the user
    """
    # Create a new client instance
    client = create_client(supabase_url, supabase_key)
    # Set the access token in the postgrest client's auth header
    # This makes auth.uid() available in RLS policies
    client.postgrest.auth(access_token)
    return client

