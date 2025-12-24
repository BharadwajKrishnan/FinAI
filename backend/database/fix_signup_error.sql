-- Comprehensive script to diagnose and fix signup errors
-- Run this in your Supabase SQL Editor

-- Step 1: Check for triggers on auth.users
SELECT 
    trigger_name, 
    event_manipulation, 
    event_object_table, 
    action_statement,
    action_timing
FROM information_schema.triggers 
WHERE event_object_table = 'users' 
  AND event_object_schema = 'auth';

-- Step 2: Check for functions that might be called by triggers
SELECT 
    routine_name, 
    routine_type,
    routine_definition
FROM information_schema.routines 
WHERE routine_schema = 'public' 
  AND (routine_name LIKE '%user%' OR routine_name LIKE '%profile%' OR routine_name LIKE '%handle%');

-- Step 3: Check if user_profiles table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_profiles'
) AS user_profiles_exists;

-- Step 4: If user_profiles exists, check its structure
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'user_profiles'
ORDER BY ordinal_position;

-- Step 5: TEMPORARY FIX - Disable problematic triggers (uncomment to use)
-- This will allow signup to work while you fix the underlying issue
-- DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Step 6: Check for any other constraints that might be failing
-- Check family_members constraint
SELECT 
    constraint_name,
    constraint_type,
    check_clause
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.check_constraints cc ON tc.constraint_name = cc.constraint_name
WHERE tc.table_schema = 'public' 
  AND tc.table_name = 'family_members'
  AND tc.constraint_type = 'CHECK';

-- Step 7: Verify the family_members constraint allows 'Self'
-- If this returns false, you need to run the migration
SELECT 
    CASE 
        WHEN check_clause LIKE '%Self%' THEN true 
        ELSE false 
    END AS allows_self
FROM information_schema.check_constraints
WHERE constraint_name = 'family_members_relationship_check';

