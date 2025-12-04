# How to Check Existing Users in Supabase

## Important: Users are stored in Supabase Auth, not in your database tables!

When you view your database tables in Supabase (like `user_profiles`, `assets`), you're looking at your **custom tables**. However, **user accounts are stored in Supabase's Authentication system**, which is separate.

## Where to Find Users

### Method 1: Supabase Dashboard (Recommended)

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project: `fuvloymbqvdmxasxajif`
3. Click on **Authentication** in the left sidebar
4. Click on **Users** tab
5. You'll see all registered users here

This is where users are stored when they sign up. The `auth.users` table is managed by Supabase and is separate from your custom database tables.

### Method 2: SQL Editor

You can also query the `auth.users` table directly:

```sql
SELECT id, email, created_at, email_confirmed_at 
FROM auth.users;
```

## Understanding the Two User Systems

1. **`auth.users`** (Supabase Auth)
   - Managed by Supabase
   - Stores: email, password hash, user ID
   - Created automatically when user signs up
   - You can view this in: Authentication → Users

2. **`user_profiles`** (Your Custom Table)
   - Your custom table
   - Stores: name, and other profile data
   - Created automatically by database trigger when user signs up
   - You can view this in: Table Editor → user_profiles

## If You See "User Already Exists" Error

This means the email is already registered in `auth.users`. To fix this:

### Option 1: Use a Different Email
Try signing up with a different email address.

### Option 2: Delete the Existing User
1. Go to Authentication → Users in Supabase Dashboard
2. Find the user with that email
3. Click the three dots (⋯) next to the user
4. Select "Delete user"
5. Try signing up again

### Option 3: Use the Existing Account
If you remember the password, just log in instead of signing up.

## Check if Schema is Set Up

Make sure you've run the database schema:

1. Go to SQL Editor in Supabase
2. Check if `user_profiles` table exists:
   ```sql
   SELECT * FROM user_profiles;
   ```

If the table doesn't exist, you need to run `backend/database/schema.sql` first.

