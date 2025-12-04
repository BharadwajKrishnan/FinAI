# Quick GitHub Setup Guide

Follow these steps to push your code to GitHub and deploy to Vercel.

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `FinanceAgent` (or your preferred name)
3. Description: "Financial asset management app with AI chat assistant"
4. Choose **Public** or **Private**
5. **DO NOT** check "Add a README file" (we already have one)
6. **DO NOT** check "Add .gitignore" (we already have one)
7. Click **"Create repository"**

## Step 2: Push Your Code

After creating the repository, GitHub will show you commands. Use these instead:

```bash
# Make sure you're in the FinanceAgent directory
cd /Users/bharadwaj/Applications/FinanceAgent

# Add the GitHub remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/FinanceAgent.git

# If you named your repository differently, use that name instead of FinanceAgent

# Rename branch to main (if needed)
git branch -M main

# Push your code
git push -u origin main
```

**Note**: If you haven't set up Git credentials, you'll be prompted to:
- Enter your GitHub username
- Enter a Personal Access Token (not your password)

To create a Personal Access Token:
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a name like "FinanceAgent"
4. Select scopes: `repo` (full control of private repositories)
5. Click "Generate token"
6. Copy the token and use it as your password when pushing

## Step 3: Verify Upload

1. Go to your GitHub repository page
2. You should see all your files:
   - `frontend/` folder
   - `backend/` folder
   - `README.md`
   - `.gitignore`
   - etc.

## Step 4: Deploy to Vercel

1. Go to https://vercel.com
2. Sign in with GitHub
3. Click "Add New..." → "Project"
4. Find and select your `FinanceAgent` repository
5. Configure:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: Click "Edit" → Type `frontend` → Click "Continue" (CRITICAL STEP!)
   - **Build Command**: `npm run build` (will auto-detect after setting root directory)
   - **Output Directory**: `.next` (will auto-detect after setting root directory)
   - **Install Command**: `npm install` (will auto-detect after setting root directory)
   
   **IMPORTANT**: If you don't set Root Directory to `frontend`, the build will fail with "No such file or directory" error!
6. Add Environment Variable:
   - Click "Environment Variables" section
   - Click "Add" or "Add Environment Variable"
   - **Name**: `NEXT_PUBLIC_API_URL`
   - **Value**: `http://localhost:8000` (you'll update this after deploying backend)
   - **Environments**: Select all (Production, Preview, Development)
   - Click "Save"
7. Click "Deploy"

## Step 5: Deploy Backend (Railway - Recommended)

1. Go to https://railway.app
2. Sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your `FinanceAgent` repository
5. In the service settings:
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add Environment Variables:
   - `SUPABASE_URL` = your Supabase URL
   - `SUPABASE_KEY` = your Supabase key
   - `GEMINI_API_KEY` = your Gemini API key
   - `GEMINI_MODEL` = `gemini-2.5-flash`
   - `LLM_PROVIDER` = `gemini`
7. Railway will give you a URL like `https://your-app.railway.app`

## Step 6: Update Vercel Environment Variable

1. Go back to Vercel dashboard (https://vercel.com/dashboard)
2. Click on your **FinanceAgent** project
3. Click **Settings** (top navigation bar)
4. Click **Environment Variables** (left sidebar)
5. Find `NEXT_PUBLIC_API_URL` and click the three dots (⋯) → **Edit**
   - Or click **Add New** if it doesn't exist
6. Update the **Value** to your Railway backend URL (e.g., `https://your-app.railway.app`)
7. Make sure all environments are selected (Production, Preview, Development)
8. Click **Save**
9. Go to **Deployments** tab
10. Click the three dots (⋯) on the latest deployment → **Redeploy**

**See `VERCEL_ENV_VARS.md` for detailed instructions and troubleshooting.**

## Troubleshooting

### Git Push Issues

**Error: "remote: Support for password authentication was removed"**
- Use a Personal Access Token instead of password
- See Step 2 above for how to create one

**Error: "Permission denied"**
- Make sure you're using the correct repository URL
- Check that you have access to the repository

### Vercel Build Issues

**Error: "Build failed"**
- Make sure Root Directory is set to `frontend`
- Check that `package.json` exists in the `frontend` folder

**Error: "Module not found"**
- Make sure all dependencies are in `frontend/package.json`
- Check that `node_modules` is in `.gitignore` (it should be)

### Backend Deployment Issues

**Error: "Port already in use"**
- Make sure you're using `$PORT` in the start command (Railway provides this)

**Error: "Module not found"**
- Make sure `requirements.txt` is in the `backend` folder
- Check that all dependencies are listed

## Next Steps

After deployment:
1. Test your app at the Vercel URL
2. Test backend API endpoints
3. Update CORS settings in `backend/main.py` to include your Vercel domain
4. Set up custom domain (optional)

For detailed deployment instructions, see `DEPLOYMENT.md`.

