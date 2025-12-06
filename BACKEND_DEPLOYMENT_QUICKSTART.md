# Quick Backend Deployment Guide

Your frontend is deployed on Vercel, but you need to deploy the backend so it can connect. Here's the fastest way:

## Option 1: Railway (Recommended - Easiest)

### Step 1: Deploy Backend

1. Go to https://railway.app
2. Sign in with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose your **FinAI** repository
6. Railway will create a service - click on it
7. Go to **Settings** tab
8. Set **Root Directory** to: `backend`
9. Go to **Variables** tab
10. Add these environment variables:

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER=gemini
```

11. Go to **Settings** → **Deploy** section
12. Set **Start Command** to:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

13. Railway will automatically deploy
14. Once deployed, go to **Settings** → **Networking**
15. Click **"Generate Domain"** or use the provided domain
16. Copy the URL (e.g., `https://your-app.railway.app`)

### Step 2: Update Vercel Environment Variable

1. Go to https://vercel.com/dashboard
2. Click your **FinAI** project
3. Go to **Settings** → **Environment Variables**
4. Find `NEXT_PUBLIC_API_URL`
5. Click the three dots (⋯) → **Edit**
6. Update the value to your Railway URL: `https://your-app.railway.app`
7. Make sure all environments are selected
8. Click **Save**
9. Go to **Deployments** tab
10. Click three dots (⋯) on latest deployment → **Redeploy**

### Step 3: Update Backend CORS

1. In Railway, go to **Variables** tab
2. Add a new variable:
   - **Key**: `ALLOWED_ORIGINS`
   - **Value**: Your Vercel URL (e.g., `https://your-app.vercel.app,http://localhost:3000`)
3. Railway will automatically redeploy

## Option 2: Render (Free Tier Available)

### Step 1: Deploy Backend

1. Go to https://render.com
2. Sign in with GitHub
3. Click **"New +"** → **"Web Service"**
4. Connect your **FinAI** repository
5. Configure:
   - **Name**: `finance-agent-backend`
   - **Root Directory**: `backend`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Click **"Advanced"** → Add environment variables (same as Railway)
7. Click **"Create Web Service"**
8. Wait for deployment
9. Copy the URL (e.g., `https://your-app.onrender.com`)

### Step 2 & 3: Same as Railway above

## Finding Your Environment Variables

### Supabase
1. Go to https://supabase.com/dashboard
2. Select your project
3. Go to **Settings** → **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_KEY`

### Gemini API Key
- You already have this: `AIzaSyBPTUGTDhGcCP_bDdwQTjAShQvZTic6shc`

## Quick Checklist

- [ ] Backend deployed on Railway/Render
- [ ] Backend URL copied (e.g., `https://your-app.railway.app`)
- [ ] `NEXT_PUBLIC_API_URL` updated in Vercel
- [ ] Vercel frontend redeployed
- [ ] Backend CORS updated (via `ALLOWED_ORIGINS` or auto-detection)
- [ ] Test login on deployed frontend

## Testing

1. Visit your Vercel URL
2. Try to sign up/login
3. If it works, you're done! 🎉
4. If you get CORS errors, add your Vercel URL to backend `ALLOWED_ORIGINS`

## Troubleshooting

### "Cannot connect to backend server"
- Check that `NEXT_PUBLIC_API_URL` in Vercel points to your backend URL (not localhost)
- Verify backend is running (visit backend URL in browser, should see JSON response)

### CORS Errors
- Add your Vercel URL to backend `ALLOWED_ORIGINS` environment variable
- Format: `https://your-app.vercel.app,http://localhost:3000`

### Backend Not Starting
- Check Railway/Render logs for errors
- Verify all environment variables are set
- Make sure `requirements.txt` has all dependencies

