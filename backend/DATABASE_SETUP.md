# Database Setup Guide

## Step-by-Step Instructions

### 1. Access Supabase SQL Editor

1. Go to your Supabase project: https://fuvloymbqvdmxasxajif.supabase.co
2. Log in to your Supabase dashboard
3. Click on **SQL Editor** in the left sidebar

### 2. Run the Schema Script

1. Open the file `backend/database/schema.sql` in this project
2. Copy the entire contents of the file
3. Paste it into the Supabase SQL Editor
4. Click the **Run** button (or press `Ctrl+Enter` / `Cmd+Enter`)

### 3. Verify Tables Created

After running the script, verify that the following tables were created:

1. Go to **Table Editor** in the Supabase dashboard
2. You should see these tables:
   - `categories`
   - `accounts`
   - `transactions`
   - `budgets`
   - `user_profiles`

### 4. Verify Row Level Security (RLS)

1. Go to **Authentication** → **Policies** in Supabase dashboard
2. Verify that RLS policies are enabled for all tables
3. Each table should have policies for SELECT, INSERT, UPDATE, and DELETE operations

### 5. Test the Setup

You can test the setup by:

1. Starting your backend server:
   ```bash
   cd backend
   python main.py
   ```

2. Register a new user:
   ```bash
   curl -X POST http://localhost:8000/api/auth/signup \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "testpassword123", "full_name": "Test User"}'
   ```

3. Login:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "testpassword123"}'
   ```

## Troubleshooting

### Error: "relation does not exist"
- Make sure you ran the entire schema.sql script
- Check that all tables were created in the Table Editor

### Error: "permission denied"
- Verify RLS policies are enabled
- Check that the policies allow the operations you're trying to perform

### Error: "duplicate key value"
- This means the table already exists
- You can drop existing tables and re-run the script, or modify the script to use `CREATE TABLE IF NOT EXISTS`

## Next Steps

After setting up the database:

1. Configure your `.env` file with Supabase credentials
2. Start the backend server
3. Test the API endpoints
4. Integrate with your frontend application

