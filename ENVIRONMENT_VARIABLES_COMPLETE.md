# Complete Environment Variables Guide

## For Backend Deployment (Render/Railway/Fly.io)

When deploying your backend, you need to add these environment variables:

### Required Variables

1. **SUPABASE_URL**
   - **Value**: `https://fuvloymbqvdmxasxajif.supabase.co`
   - **What it does**: Your Supabase project URL

2. **SUPABASE_KEY**
   - **Value**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1dmxveW1icXZkbXhhc3hhamlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NzYyMzAsImV4cCI6MjA4MDM1MjIzMH0.HoeQ8dgAz4pZhyNpNHc_UeRiReZHcfFOIa23PHT-dYI`
   - **What it does**: Your Supabase anon/public key for API access

3. **GEMINI_API_KEY**
   - **Value**: `AIzaSyBPTUGTDhGcCP_bDdwQTjAShQvZTic6shc`
   - **What it does**: API key for Google Gemini LLM

4. **GEMINI_MODEL**
   - **Value**: `gemini-2.5-flash`
   - **What it does**: Which Gemini model to use

5. **LLM_PROVIDER**
   - **Value**: `gemini`
   - **What it does**: Which LLM provider to use (currently only Gemini)

### Optional Variables

6. **ALLOWED_ORIGINS** (Optional but recommended)
   - **Value**: `https://your-app.vercel.app,http://localhost:3000`
   - **What it does**: Comma-separated list of allowed frontend URLs for CORS
   - **Note**: If not set, backend will auto-detect Vercel URL from `VERCEL_URL` env var

7. **VERCEL_URL** (Optional)
   - **Value**: Your Vercel frontend URL (e.g., `your-app.vercel.app`)
   - **What it does**: Auto-adds to CORS allowed origins
   - **Note**: Usually set automatically if deploying from Vercel, but you can set manually

8. **FINNHUB_API_KEY** (Optional - for stock search)
   - **Value**: `d4otov1r01qnosaam4v0d4otov1r01qnosaam4vg`
   - **What it does**: API key for Finnhub stock search (if you re-enable stock search later)

## For Frontend Deployment (Vercel)

When deploying your frontend on Vercel, you need:

### Required Variables

1. **NEXT_PUBLIC_API_URL**
   - **Value**: Your backend URL (e.g., `https://your-app.railway.app` or `https://your-app.onrender.com`)
   - **What it does**: Tells frontend where to send API requests
   - **Important**: Must start with `NEXT_PUBLIC_` to be accessible in the browser

## Complete Setup Instructions

### Step 1: Deploy Backend (Render Example)

1. Go to https://render.com
2. Create new Web Service
3. Connect your GitHub repo
4. Set Root Directory to: `backend`
5. Add these environment variables:

```
SUPABASE_URL=https://fuvloymbqvdmxasxajif.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1dmxveW1icXZkbXhhc3hhamlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NzYyMzAsImV4cCI6MjA4MDM1MjIzMH0.HoeQ8dgAz4pZhyNpNHc_UeRiReZHcfFOIa23PHT-dYI
GEMINI_API_KEY=AIzaSyBPTUGTDhGcCP_bDdwQTjAShQvZTic6shc
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER=gemini
ALLOWED_ORIGINS=https://your-app.vercel.app,http://localhost:3000
```

6. Deploy and copy your backend URL

### Step 2: Update Frontend (Vercel)

1. Go to Vercel dashboard
2. Your project → Settings → Environment Variables
3. Add/Update:

```
NEXT_PUBLIC_API_URL=https://your-backend-url.onrender.com
```

4. Redeploy frontend

## Quick Copy-Paste for Render

When adding environment variables in Render, copy-paste these one by one:

**Variable 1:**
- Key: `SUPABASE_URL`
- Value: `https://fuvloymbqvdmxasxajif.supabase.co`

**Variable 2:**
- Key: `SUPABASE_KEY`
- Value: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1dmxveW1icXZkbXhhc3hhamlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3NzYyMzAsImV4cCI6MjA4MDM1MjIzMH0.HoeQ8dgAz4pZhyNpNHc_UeRiReZHcfFOIa23PHT-dYI`

**Variable 3:**
- Key: `GEMINI_API_KEY`
- Value: `AIzaSyBPTUGTDhGcCP_bDdwQTjAShQvZTic6shc`

**Variable 4:**
- Key: `GEMINI_MODEL`
- Value: `gemini-2.5-flash`

**Variable 5:**
- Key: `LLM_PROVIDER`
- Value: `gemini`

**Variable 6 (After you get your Vercel URL):**
- Key: `ALLOWED_ORIGINS`
- Value: `https://your-app.vercel.app,http://localhost:3000`
- Replace `your-app.vercel.app` with your actual Vercel URL

## Quick Copy-Paste for Vercel

**Variable 1:**
- Key: `NEXT_PUBLIC_API_URL`
- Value: `https://your-backend-url.onrender.com` (or your Railway/Fly.io URL)
- Replace with your actual backend URL after deployment

## Summary Table

### Backend (Render/Railway/Fly.io)
| Variable | Required? | Example Value |
|----------|-----------|---------------|
| `SUPABASE_URL` | ✅ Yes | `https://fuvloymbqvdmxasxajif.supabase.co` |
| `SUPABASE_KEY` | ✅ Yes | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `GEMINI_API_KEY` | ✅ Yes | `AIzaSyBPTUGTDhGcCP_bDdwQTjAShQvZTic6shc` |
| `GEMINI_MODEL` | ✅ Yes | `gemini-2.5-flash` |
| `LLM_PROVIDER` | ✅ Yes | `gemini` |
| `ALLOWED_ORIGINS` | ⚠️ Recommended | `https://your-app.vercel.app,http://localhost:3000` |
| `FINNHUB_API_KEY` | ❌ Optional | `d4otov1r01qnosaam4v0d4otov1r01qnosaam4vg` |

### Frontend (Vercel)
| Variable | Required? | Example Value |
|----------|-----------|---------------|
| `NEXT_PUBLIC_API_URL` | ✅ Yes | `https://your-backend.onrender.com` |

## Important Notes

1. **Backend variables** go in Render/Railway/Fly.io (NOT in Vercel)
2. **Frontend variables** go in Vercel (only `NEXT_PUBLIC_API_URL`)
3. **Never commit** these values to GitHub (they're in `.gitignore`)
4. **Update `NEXT_PUBLIC_API_URL`** in Vercel AFTER you deploy backend and get the URL
5. **Update `ALLOWED_ORIGINS`** in backend AFTER you know your Vercel URL

## Troubleshooting

### Backend can't connect to Supabase
- Check `SUPABASE_URL` and `SUPABASE_KEY` are correct
- Make sure no extra spaces in values

### Frontend can't connect to backend
- Check `NEXT_PUBLIC_API_URL` points to your backend URL
- Make sure it starts with `https://` (not `http://`)
- Verify backend is actually running

### CORS errors
- Add your Vercel URL to `ALLOWED_ORIGINS` in backend
- Format: `https://your-app.vercel.app,http://localhost:3000`

