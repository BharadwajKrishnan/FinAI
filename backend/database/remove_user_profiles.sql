-- Script to safely remove user_profiles table
-- Run this in your Supabase SQL Editor

-- Step 1: Drop the trigger that creates profiles on signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Step 2: Drop the function that creates profiles (if not used elsewhere)
DROP FUNCTION IF EXISTS public.handle_new_user();

-- Step 3: Drop the trigger that updates updated_at for user_profiles
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;

-- Step 4: Drop RLS policies for user_profiles
DROP POLICY IF EXISTS "Users can view their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON user_profiles;

-- Step 5: Drop the table (this will cascade delete any data)
DROP TABLE IF EXISTS user_profiles;

-- Verification: Check if table still exists (should return 0 rows)
-- SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'user_profiles';
