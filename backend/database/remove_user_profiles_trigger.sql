-- Remove the trigger that tries to create user_profiles on signup
-- This is needed because the user_profiles table has been removed

-- Step 1: Drop the trigger that creates profiles on signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Step 2: Drop the function that creates profiles (if it exists)
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;

-- Step 3: Verify the trigger is gone
SELECT 
    trigger_name,
    event_object_table
FROM information_schema.triggers 
WHERE event_object_table = 'users' 
  AND event_object_schema = 'auth'
  AND trigger_name = 'on_auth_user_created';

-- If the above query returns no rows, the trigger has been successfully removed
-- Signup should now work!

