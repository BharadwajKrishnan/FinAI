-- Script to check for and fix any issues with user creation triggers
-- Run this in your Supabase SQL Editor

-- Check if there's a trigger on auth.users
SELECT 
    trigger_name, 
    event_manipulation, 
    event_object_table, 
    action_statement
FROM information_schema.triggers 
WHERE event_object_table = 'users' 
  AND event_object_schema = 'auth';

-- Check if handle_new_user function exists
SELECT 
    routine_name, 
    routine_type
FROM information_schema.routines 
WHERE routine_schema = 'public' 
  AND routine_name = 'handle_new_user';

-- If the trigger exists and is causing issues, you can temporarily disable it:
-- DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Or if you want to create a safe version that doesn't fail:
-- First, check if user_profiles table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_profiles'
);

