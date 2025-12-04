# Deployment Guide

This guide will help you deploy FinanceAgent to Vercel (frontend) and set up the backend.

## Prerequisites

- GitHub account
- Vercel account (free tier available)
- Backend hosting service (Railway, Render, or similar)

## Step 1: Create GitHub Repository

1. Go to [GitHub](https://github.com) and sign in
2. Click the "+" icon in the top right corner
3. Select "New repository"
4. Name it `FinanceAgent` (or your preferred name)
5. Choose **Public** or **Private**
6. **DO NOT** initialize with README, .gitignore, or license (we already have these)
7. Click "Create repository"

## Step 2: Push Code to GitHub

Run these commands in your terminal (from the FinanceAgent directory):

```bash
# Add GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/FinanceAgent.git

# Rename main branch if needed
git branch -M main

# Push to GitHub
git push -u origin main
```

If you haven't set up Git credentials, GitHub will prompt you to authenticate.

## Step 3: Deploy Frontend to Vercel

1. Go to [Vercel](https://vercel.com) and sign in (use GitHub to sign in)
2. Click "Add New..." → "Project"
3. Import your `FinanceAgent` repository
4. Configure the project:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `frontend` (IMPORTANT!)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
   - **Install Command**: `npm install` (auto-detected)

5. Add Environment Variables:
   - Click "Environment Variables"
   - Add: `NEXT_PUBLIC_API_URL` = `https://your-backend-url.com` (you'll update this after deploying backend)

6. Click "Deploy"

Vercel will automatically build and deploy your frontend. You'll get a URL like `https://finance-agent.vercel.app`

## Step 4: Deploy Backend

### Option A: Railway (Recommended - Easy Setup)

1. Go to [Railway](https://railway.app) and sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `FinanceAgent` repository
4. Configure:
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables in Railway:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   LLM_PROVIDER=gemini
   FINNHUB_API_KEY=your_finnhub_api_key
   ```

6. Railway will automatically deploy and give you a URL like `https://your-app.railway.app`

### Option B: Render

1. Go to [Render](https://render.com) and sign in
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `finance-agent-backend`
   - **Root Directory**: `backend`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. Add environment variables (same as Railway)
6. Click "Create Web Service"

### Option C: Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. In the `backend` directory, run: `fly launch`
3. Follow the prompts
4. Set environment variables: `fly secrets set SUPABASE_URL=...` (repeat for each)

## Step 5: Update Frontend Environment Variable

1. Go back to Vercel dashboard
2. Navigate to your project → Settings → Environment Variables
3. Update `NEXT_PUBLIC_API_URL` to your backend URL (e.g., `https://your-app.railway.app`)
4. Redeploy the frontend (Vercel will auto-redeploy or you can trigger manually)

## Step 6: Configure CORS

Make sure your backend allows requests from your Vercel domain. In `backend/main.py`, update CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-app.vercel.app",  # Add your Vercel URL
    ],
    # ... rest of config
)
```

Commit and push this change, then redeploy the backend.

## Step 7: Test Deployment

1. Visit your Vercel URL
2. Try signing up and logging in
3. Test adding assets
4. Test the chat functionality

## Troubleshooting

### Frontend Issues

- **Build fails**: Check that `Root Directory` is set to `frontend` in Vercel
- **API calls fail**: Verify `NEXT_PUBLIC_API_URL` is correct and backend is running
- **Environment variables not working**: Make sure they start with `NEXT_PUBLIC_` for client-side access

### Backend Issues

- **500 errors**: Check backend logs for missing environment variables
- **CORS errors**: Update CORS settings in `main.py` to include Vercel domain
- **Database connection fails**: Verify Supabase URL and key are correct

## Continuous Deployment

Both Vercel and Railway/Render support automatic deployments:
- Push to `main` branch → Auto-deploy
- Create a pull request → Preview deployment (Vercel)

## Custom Domain (Optional)

### Vercel
1. Go to Project Settings → Domains
2. Add your custom domain
3. Follow DNS configuration instructions

### Backend
- Railway: Add custom domain in project settings
- Render: Add custom domain in service settings

## Monitoring

- **Vercel**: Check Analytics and Logs in dashboard
- **Railway**: View logs in real-time
- **Render**: Check logs in service dashboard

## Security Notes

- Never commit `.env` files
- Use environment variables for all secrets
- Enable Supabase Row Level Security (RLS) policies
- Use HTTPS for all deployments (automatic with Vercel/Railway/Render)

