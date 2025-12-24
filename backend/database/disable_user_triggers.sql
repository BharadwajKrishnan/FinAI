-- TEMPORARY FIX: Disable triggers that might be causing signup to fail
-- Run this ONLY if you need signup to work immediately
-- You should investigate and fix the root cause afterwards

-- Disable the trigger that creates user_profiles (if it exists)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Verify the trigger is gone
SELECT 
    trigger_name
FROM information_schema.triggers 
WHERE event_object_table = 'users' 
  AND event_object_schema = 'auth'
  AND trigger_name = 'on_auth_user_created';

-- If the above returns no rows, the trigger has been successfully removed
-- Signup should now work, but user_profiles won't be auto-created

