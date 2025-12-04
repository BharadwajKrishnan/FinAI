# Vercel Environment Variables Guide

## Required Environment Variables for Vercel

When deploying the **frontend** to Vercel, you need to add the following environment variable:

### 1. `NEXT_PUBLIC_API_URL`

**What it is:** The URL of your backend API server

**How to set it:**

#### During Development (Local):
```
NEXT_PUBLIC_API_URL = http://localhost:8000
```

#### After Backend is Deployed:
```
NEXT_PUBLIC_API_URL = https://your-backend-url.railway.app
```
or
```
NEXT_PUBLIC_API_URL = https://your-backend-url.render.com
```
or
```
NEXT_PUBLIC_API_URL = https://your-backend-url.fly.dev
```

**Where to add it in Vercel:**

1. Go to your Vercel project dashboard
2. Click on **Settings** (top menu)
3. Click on **Environment Variables** (left sidebar)
4. Click **Add New**
5. Enter:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: Your backend URL (e.g., `https://your-app.railway.app`)
   - **Environment**: Select all (Production, Preview, Development)
6. Click **Save**

**Important Notes:**
- The variable name **MUST** start with `NEXT_PUBLIC_` for it to be accessible in the browser
- After adding/updating environment variables, you need to **redeploy** your Vercel project
- You can redeploy by going to **Deployments** tab and clicking the three dots (⋯) → **Redeploy**

## Step-by-Step: Adding Environment Variables in Vercel

### Option 1: During Initial Setup

1. When importing your GitHub repo in Vercel
2. After selecting the repository, you'll see a configuration page
3. Scroll down to **"Environment Variables"** section
4. Click **"Add"** or **"Add Environment Variable"**
5. Add:
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: `http://localhost:8000` (you'll update this later)
6. Click **Deploy**

### Option 2: After Deployment

1. Go to https://vercel.com/dashboard
2. Click on your **FinanceAgent** project
3. Click **Settings** (top navigation)
4. Click **Environment Variables** (left sidebar)
5. Click **Add New** button
6. Fill in:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: Your backend URL
   - **Environments**: Check all boxes (Production, Preview, Development)
7. Click **Save**
8. Go to **Deployments** tab
9. Click the three dots (⋯) on the latest deployment
10. Click **Redeploy**

## Example Values

### If Backend is on Railway:
```
NEXT_PUBLIC_API_URL = https://finance-agent-production.up.railway.app
```

### If Backend is on Render:
```
NEXT_PUBLIC_API_URL = https://finance-agent-backend.onrender.com
```

### If Backend is on Fly.io:
```
NEXT_PUBLIC_API_URL = https://finance-agent-backend.fly.dev
```

### For Local Development (not needed in Vercel, but for reference):
```
NEXT_PUBLIC_API_URL = http://localhost:8000
```

## How to Find Your Backend URL

### Railway:
1. Go to your Railway project
2. Click on your service
3. Look for **"Public Domain"** or **"Settings"** → **"Networking"**
4. Copy the URL (e.g., `https://your-app.railway.app`)

### Render:
1. Go to your Render dashboard
2. Click on your web service
3. Look at the top of the page for the URL
4. Copy the URL (e.g., `https://your-app.onrender.com`)

### Fly.io:
1. Run: `fly status` in your backend directory
2. Or check the Fly.io dashboard
3. Copy the URL (e.g., `https://your-app.fly.dev`)

## Troubleshooting

### Problem: Frontend can't connect to backend
**Solution:** 
- Check that `NEXT_PUBLIC_API_URL` is set correctly
- Make sure the backend URL starts with `https://` (not `http://`)
- Verify the backend is actually running and accessible
- Check CORS settings in backend (should allow your Vercel domain)

### Problem: Environment variable not working
**Solution:**
- Make sure the variable name starts with `NEXT_PUBLIC_`
- Redeploy after adding/updating variables
- Check that you selected all environments (Production, Preview, Development)

### Problem: Getting CORS errors
**Solution:**
- Update `backend/main.py` to include your Vercel domain in `allow_origins`
- Or set `ALLOWED_ORIGINS` environment variable in backend
- Redeploy backend after changes

## Summary

**For Vercel (Frontend), you ONLY need:**
- ✅ `NEXT_PUBLIC_API_URL` = Your backend URL

**You do NOT need to add these in Vercel** (they're for backend only):
- ❌ `SUPABASE_URL` (backend only)
- ❌ `SUPABASE_KEY` (backend only)
- ❌ `GEMINI_API_KEY` (backend only)
- ❌ `GEMINI_MODEL` (backend only)
- ❌ `LLM_PROVIDER` (backend only)

These backend environment variables should be added in Railway/Render/Fly.io, NOT in Vercel.

