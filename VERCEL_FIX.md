# Fixing Vercel Build Error: "No such file or directory"

## The Problem

You're seeing this error:
```
sh: line 1: cd: frontend: No such file or directory
Error: Command "cd frontend && npm install" exited with 1
```

This happens because Vercel doesn't know that your Next.js app is in the `frontend` folder.

## The Solution

You need to set the **Root Directory** to `frontend` in your Vercel project settings.

## Step-by-Step Fix

### Option 1: Fix in Existing Project (Recommended)

1. Go to https://vercel.com/dashboard
2. Click on your **FinAI** (or FinanceAgent) project
3. Click **Settings** (top navigation)
4. Click **General** (left sidebar, under "Project Settings")
5. Scroll down to **"Root Directory"**
6. Click **"Edit"**
7. Enter: `frontend`
8. Click **"Save"**
9. Go to **Deployments** tab
10. Click the three dots (⋯) on the latest failed deployment
11. Click **"Redeploy"**

### Option 2: Delete and Re-import (If Option 1 doesn't work)

1. Go to Vercel dashboard
2. Click on your project
3. Go to **Settings** → **General**
4. Scroll to bottom → Click **"Delete Project"**
5. Click **"Add New..."** → **"Project"**
6. Re-import your GitHub repository
7. **BEFORE clicking Deploy**, click **"Edit"** next to "Root Directory"
8. Enter: `frontend`
9. Click **"Continue"**
10. Now add your environment variable (`NEXT_PUBLIC_API_URL`)
11. Click **"Deploy"**

## How to Verify Root Directory is Set

After setting the root directory, you should see:
- **Root Directory**: `frontend` (not empty or `/`)
- **Build Command**: `npm run build` (not `cd frontend && npm run build`)
- **Install Command**: `npm install` (not `cd frontend && npm install`)
- **Output Directory**: `.next` (not `frontend/.next`)

## Why This Happens

Vercel assumes your Next.js app is in the root of your repository. Since your app is in the `frontend/` folder, you need to tell Vercel where to find it.

## After Fixing

Once you set the root directory correctly:
1. The build should succeed
2. Your app will be deployed
3. You'll get a URL like `https://your-app.vercel.app`

## Still Having Issues?

If the build still fails after setting the root directory:

1. **Check your repository structure:**
   ```bash
   # Make sure frontend folder exists
   ls -la frontend/
   ```

2. **Verify package.json exists:**
   ```bash
   ls frontend/package.json
   ```

3. **Check Vercel logs:**
   - Go to your deployment
   - Click on the failed build
   - Check the "Build Logs" tab for detailed error messages

4. **Common issues:**
   - Root directory not saved (make sure you clicked "Save")
   - Typo in root directory (should be exactly `frontend`, not `Frontend` or `frontend/`)
   - Need to redeploy after changing settings

