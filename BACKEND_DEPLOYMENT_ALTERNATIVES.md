# Backend Deployment Alternatives

Here are several alternatives to Railway for deploying your Python FastAPI backend:

## Option 1: Render (Recommended - Free Tier Available) ⭐

### Why Render?
- ✅ Free tier available (with some limitations)
- ✅ Easy setup, similar to Railway
- ✅ Automatic HTTPS
- ✅ Good documentation

### Step-by-Step:

1. **Go to Render**
   - Visit: https://render.com
   - Sign in with GitHub

2. **Create New Web Service**
   - Click **"New +"** button (top right)
   - Select **"Web Service"**

3. **Connect Repository**
   - Click **"Connect account"** if not connected
   - Select your **FinAI** repository
   - Click **"Connect"**

4. **Configure Service**
   - **Name**: `finance-agent-backend` (or your choice)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: `backend` ⚠️ **IMPORTANT!**
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

5. **Add Environment Variables**
   - Scroll to **"Environment Variables"** section
   - Click **"Add Environment Variable"** for each:
     ```
     SUPABASE_URL = your_supabase_url
     SUPABASE_KEY = your_supabase_anon_key
     SUPABASE_SERVICE_ROLE_KEY = your_supabase_service_role_key
     GEMINI_API_KEY = your_gemini_api_key
     GEMINI_MODEL = gemini-2.5-flash
     LLM_PROVIDER = gemini
     ```

6. **Deploy**
   - Click **"Create Web Service"**
   - Wait for deployment (5-10 minutes first time)
   - Once deployed, you'll see a URL like: `https://finance-agent-backend.onrender.com`

7. **Update Vercel**
   - Go to Vercel → Your Project → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_URL` to your Render URL
   - Redeploy frontend

---

## Option 2: Fly.io (Good for Production)

### Why Fly.io?
- ✅ Generous free tier
- ✅ Fast deployments
- ✅ Global edge network
- ⚠️ Requires CLI setup

### Step-by-Step:

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
   Or on macOS:
   ```bash
   brew install flyctl
   ```

2. **Login to Fly.io**
   ```bash
   fly auth login
   ```
   - This will open a browser to sign in

3. **Navigate to Backend Directory**
   ```bash
   cd /Users/bharadwaj/Applications/FinanceAgent/backend
   ```

4. **Launch App**
   ```bash
   fly launch
   ```
   - Follow the prompts:
     - App name: `finance-agent-backend` (or auto-generated)
     - Region: Choose closest
     - PostgreSQL: No (we use Supabase)
     - Redis: No

5. **Set Environment Variables**
   ```bash
   fly secrets set SUPABASE_URL="your_supabase_url"
   fly secrets set SUPABASE_KEY="your_supabase_anon_key"
   fly secrets set SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key"
   fly secrets set GEMINI_API_KEY="your_gemini_api_key"
   fly secrets set GEMINI_MODEL="gemini-2.5-flash"
   fly secrets set LLM_PROVIDER="gemini"
   ```

6. **Deploy**
   ```bash
   fly deploy
   ```

7. **Get Your URL**
   - After deployment, you'll see: `https://finance-agent-backend.fly.dev`
   - Or check with: `fly status`

8. **Update Vercel**
   - Update `NEXT_PUBLIC_API_URL` in Vercel to your Fly.io URL

---

## Option 3: PythonAnywhere (Simple, Free Tier)

### Why PythonAnywhere?
- ✅ Free tier available
- ✅ Simple web interface
- ✅ Good for beginners
- ⚠️ Less modern than other options

### Step-by-Step:

1. **Sign Up**
   - Go to: https://www.pythonanywhere.com
   - Create a free account

2. **Upload Your Code**
   - Go to **"Files"** tab
   - Navigate to `/home/yourusername/`
   - Upload your `backend/` folder contents

3. **Create Web App**
   - Go to **"Web"** tab
   - Click **"Add a new web app"**
   - Choose **"Flask"** (we'll modify it)
   - Select Python 3.10+

4. **Configure**
   - Edit the WSGI file to point to your FastAPI app
   - Set working directory to your backend folder

5. **Set Environment Variables**
   - In the web app settings, add environment variables

6. **Reload**
   - Click **"Reload"** button

**Note**: PythonAnywhere requires more manual configuration. Render or Fly.io are easier.

---

## Option 4: Heroku (Classic, Paid)

### Why Heroku?
- ✅ Very popular
- ✅ Easy deployment
- ⚠️ No free tier anymore (paid only)

### Step-by-Step:

1. **Sign Up**
   - Go to: https://heroku.com
   - Create account (requires credit card for verification)

2. **Install Heroku CLI**
   ```bash
   brew tap heroku/brew && brew install heroku
   ```

3. **Login**
   ```bash
   heroku login
   ```

4. **Create App**
   ```bash
   cd /Users/bharadwaj/Applications/FinanceAgent/backend
   heroku create finance-agent-backend
   ```

5. **Set Environment Variables**
   ```bash
   heroku config:set SUPABASE_URL="your_supabase_url"
   heroku config:set SUPABASE_KEY="your_supabase_anon_key"
   heroku config:set SUPABASE_SERVICE_ROLE_KEY="your_supabase_service_role_key"
   heroku config:set GEMINI_API_KEY="your_gemini_api_key"
   heroku config:set GEMINI_MODEL="gemini-2.5-flash"
   heroku config:set LLM_PROVIDER="gemini"
   ```

6. **Create Procfile**
   ```bash
   echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile
   ```

7. **Deploy**
   ```bash
   git add Procfile
   git commit -m "Add Procfile for Heroku"
   git push heroku main
   ```

---

## Option 5: DigitalOcean App Platform

### Why DigitalOcean?
- ✅ Good performance
- ✅ Simple pricing
- ⚠️ Paid service (but affordable)

### Step-by-Step:

1. **Sign Up**
   - Go to: https://www.digitalocean.com/products/app-platform
   - Create account

2. **Create App**
   - Click **"Create App"**
   - Connect GitHub repository

3. **Configure**
   - **Resource Type**: Web Service
   - **Source**: Your FinAI repo
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Run Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. **Add Environment Variables**
   - Add all required variables in the UI

5. **Deploy**
   - Click **"Create Resources"**
   - Wait for deployment

---

## Comparison

| Service | Free Tier | Ease of Use | Best For |
|---------|-----------|-------------|----------|
| **Render** | ✅ Yes | ⭐⭐⭐⭐⭐ | Beginners, quick setup |
| **Fly.io** | ✅ Yes | ⭐⭐⭐⭐ | Production apps |
| **PythonAnywhere** | ✅ Yes | ⭐⭐⭐ | Learning, simple apps |
| **Heroku** | ❌ No | ⭐⭐⭐⭐ | Established apps |
| **DigitalOcean** | ❌ No | ⭐⭐⭐⭐ | Production, scaling |

## My Recommendation

**For you: Use Render** - It's the easiest alternative to Railway:
- Free tier available
- Simple web interface (no CLI needed)
- Similar to Railway in ease of use
- Automatic HTTPS
- Good documentation

## After Deployment (Any Option)

1. Copy your backend URL
2. Go to Vercel → Settings → Environment Variables
3. Update `NEXT_PUBLIC_API_URL` to your backend URL
4. Redeploy frontend
5. Test your app! 🎉

