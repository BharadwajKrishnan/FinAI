# FinanceApp Backend

Python FastAPI backend for FinanceApp with Supabase integration.

## Setup

### 1. Database Setup

First, you need to create the database schema in Supabase:

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Open the file `database/schema.sql` from this project
4. Copy and paste the entire SQL script into the SQL Editor
5. Click **Run** to execute the script

This will create all necessary tables:
- `assets` - Financial assets (stocks, mutual funds, bank accounts, fixed deposits)
- `user_profiles` - Extended user information

See `DATABASE_SETUP.md` for detailed instructions.

### 2. Environment Setup

1. Create a virtual environment (if not already created):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the backend directory:
```bash
SUPABASE_URL=https://fuvloymbqvdmxasxajif.supabase.co
SUPABASE_KEY=your_supabase_anon_key
PORT=8000
ENVIRONMENT=development

# Stock Search API (Finnhub)
# Get your free API key at: https://finnhub.io/register
FINNHUB_API_KEY=your_finnhub_api_key
```

**Note:** 
- Replace `your_supabase_anon_key` with your actual Supabase anon key from your project settings.
- Replace `your_finnhub_api_key` with your Finnhub API key. Get a free API key at https://finnhub.io/register (free tier: 60 calls/minute)

### 3. Run the Server

```bash
python main.py
```

The API will be available at `http://localhost:8000`

For development with auto-reload:
```bash
uvicorn main:app --reload --port 8000
```

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register a new user
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user info (requires auth)

### Assets
- `GET /api/assets` - Get all assets (requires auth)
  - Query params: `asset_type` (stock, mutual_fund, bank_account, fixed_deposit), `is_active`
- `POST /api/assets` - Create a new asset (requires auth)
- `GET /api/assets/{id}` - Get a specific asset (requires auth)
- `PUT /api/assets/{id}` - Update an asset (requires auth)
- `DELETE /api/assets/{id}` - Delete an asset (requires auth)
- `GET /api/assets/summary/total` - Get total portfolio value (requires auth)
- `GET /api/assets/summary/by-type` - Get assets grouped by type (requires auth)

### Chat/LLM
- `POST /api/chat/` - Send a chat message and get LLM response (requires auth)
  - Body: `{"message": "string", "conversation_history": [...]}`
  - See `LLM_SETUP.md` for LLM provider configuration

## Authentication

All endpoints except `/api/auth/signup` and `/api/auth/login` require authentication.

Include the access token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## Project Structure

```
backend/
├── database/
│   ├── schema.sql          # Database schema (run in Supabase SQL Editor)
│   └── supabase_client.py  # Supabase client initialization
├── routers/
│   ├── assets.py          # Asset endpoints
│   └── chat.py            # Chat/LLM endpoints
├── services/
│   └── llm_service.py     # LLM service for AI chat
├── models.py              # Pydantic models
├── auth.py                # Authentication dependencies
├── main.py                # FastAPI application
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── LLM_SETUP.md          # LLM integration guide
```

## Features

- ✅ User authentication with Supabase Auth
- ✅ Row Level Security (RLS) enabled on all tables
- ✅ CRUD operations for financial assets (stocks, mutual funds, bank accounts, fixed deposits)
- ✅ Portfolio summary and aggregation endpoints
- ✅ User profile management
- ✅ JWT token-based authentication
- ✅ Support for multiple asset types in a unified table structure
- ✅ LLM chat integration (OpenAI, Anthropic, Ollama) - see `LLM_SETUP.md`
