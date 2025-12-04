# Fix: Vercel Can't Find package.json

## The Error

```
npm error path /vercel/path0/package.json
npm error errno -2
npm error enoent Could not read package.json
```

This means Vercel is looking for `package.json` in the root directory, but your Next.js app is in the `frontend/` folder.

## The Solution: Set Root Directory in Vercel Dashboard

You **MUST** set the Root Directory in Vercel's project settings. This cannot be done via config files alone.

## Step-by-Step Instructions

### Method 1: Fix in Existing Project (Easiest)

1. **Go to Vercel Dashboard**
   - Visit: https://vercel.com/dashboard
   - Sign in if needed

2. **Open Your Project**
   - Click on your **FinAI** project (or whatever you named it)

3. **Go to Settings**
   - Click **"Settings"** in the top navigation bar
   - (It's next to "Deployments" and "Analytics")

4. **Open General Settings**
   - In the left sidebar, under "Project Settings"
   - Click **"General"** (it should be selected by default)

5. **Find Root Directory**
   - Scroll down the page
   - Look for **"Root Directory"** section
   - You'll see it shows either:
     - Empty/blank
     - Or `/` (root)
     - Or something else

6. **Edit Root Directory**
   - Click the **"Edit"** button next to "Root Directory"
   - A text input will appear
   - Type exactly: `frontend`
   - **DO NOT** type `frontend/` (no trailing slash)
   - **DO NOT** type `/frontend` (no leading slash)
   - Just: `frontend`

7. **Save**
   - Click **"Save"** or **"Continue"**
   - Wait for it to save (you'll see a confirmation)

8. **Redeploy**
   - Go to **"Deployments"** tab (top navigation)
   - Find your latest deployment (the one that failed)
   - Click the three dots (⋯) on the right
   - Click **"Redeploy"**
   - Confirm the redeploy

### Method 2: Delete and Re-import (If Method 1 doesn't work)

1. **Delete Current Project**
   - Go to Settings → General
   - Scroll to the very bottom
   - Click **"Delete Project"**
   - Confirm deletion

2. **Create New Project**
   - Click **"Add New..."** → **"Project"**
   - Import your GitHub repository again

3. **Configure BEFORE Deploying**
   - **IMPORTANT**: Do NOT click "Deploy" yet!
   - Scroll down to find **"Root Directory"**
   - Click **"Edit"** next to it
   - Enter: `frontend`
   - Click **"Continue"** or **"Save"**

4. **Add Environment Variable**
   - Scroll to **"Environment Variables"**
   - Add: `NEXT_PUBLIC_API_URL` = `http://localhost:8000`
   - Select all environments
   - Click **"Save"**

5. **Now Deploy**
   - Click **"Deploy"**
   - This time it should work!

## How to Verify It's Set Correctly

After setting the root directory, check:

1. **In Settings → General:**
   - Root Directory should show: `frontend`

2. **In the build logs (after redeploy):**
   - You should see: `Running "install" command: npm install...`
   - NOT: `cd frontend && npm install`
   - The build should find `package.json` successfully

3. **Build commands should be:**
   - Install: `npm install` (not `cd frontend && npm install`)
   - Build: `npm run build` (not `cd frontend && npm run build`)
   - Output: `.next` (not `frontend/.next`)

## Visual Guide

When you're in Settings → General, you should see:

```
┌─────────────────────────────────────┐
│ Project Settings                    │
├─────────────────────────────────────┤
│ General                             │
│ Environment Variables               │
│ Git                                 │
│ ...                                 │
└─────────────────────────────────────┘

Scroll down to:

┌─────────────────────────────────────┐
│ Root Directory                      │
│                                     │
│ [frontend]  [Edit]                  │
│                                     │
│ The directory within your project   │
│ that contains the code to build.    │
└─────────────────────────────────────┘
```

## Common Mistakes

❌ **Wrong**: Setting it to `/frontend` (leading slash)
❌ **Wrong**: Setting it to `frontend/` (trailing slash)  
❌ **Wrong**: Setting it to `./frontend` (relative path)
✅ **Correct**: Just `frontend`

❌ **Wrong**: Only updating `vercel.json` file (this doesn't work alone)
✅ **Correct**: Setting it in Vercel Dashboard Settings

## Still Not Working?

1. **Check your repository structure:**
   - Make sure `frontend/package.json` exists in your GitHub repo
   - Go to: https://github.com/BharadwajKrishnan/FinAI
   - Verify you can see `frontend/package.json`

2. **Push latest changes:**
   ```bash
   git push origin main
   ```
   Then redeploy in Vercel

3. **Check Vercel logs:**
   - Go to your deployment
   - Click on the failed build
   - Check "Build Logs" for more details

4. **Try Method 2** (delete and re-import)

## Why This Happens

Vercel needs to know where your Next.js app is located. By default, it assumes the root directory. Since your app is in a subfolder (`frontend/`), you must explicitly tell Vercel where to look.

The `vercel.json` file I created helps, but the **Root Directory** setting in the dashboard is the primary way Vercel determines where to build from.

