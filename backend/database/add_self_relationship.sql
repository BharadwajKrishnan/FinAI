-- Migration script to add "Self" as a valid relationship value
-- Run this script in your Supabase SQL editor to update the check constraint

-- Drop the existing check constraint
ALTER TABLE family_members DROP CONSTRAINT IF EXISTS family_members_relationship_check;

-- Add the new check constraint with "Self" included
ALTER TABLE family_members ADD CONSTRAINT family_members_relationship_check 
    CHECK (relationship IN ('Self', 'Son', 'Daughter', 'Spouse', 'Father', 'Mother', 'Grandfather', 'Grandmother', 'Brother', 'Sister'));

