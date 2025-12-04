# FinanceAgent

A modern financial asset management application with AI-powered chat assistance. Track your stocks, bank accounts, mutual funds, and fixed deposits across multiple markets (India and Europe).

## Features

- 🔐 **User Authentication**: Secure signup and login with Supabase Auth
- 📊 **Asset Management**: Track stocks, bank accounts, mutual funds, and fixed deposits
- 🌍 **Multi-Market Support**: Separate tracking for India (INR) and Europe (EUR) markets
- 💬 **AI Chat Assistant**: Get financial advice and insights using Google Gemini
- 📈 **Real-time Stock Prices**: Automatic price updates for your stock portfolio
- 💰 **Net Worth Calculator**: Track your total net worth per market
- 📱 **Responsive Design**: Modern UI built with Next.js 15 and Tailwind CSS

## Tech Stack

### Frontend
- **Next.js 15** (App Router)
- **TypeScript**
- **React 18**
- **Tailwind CSS**

### Backend
- **FastAPI** (Python)
- **Supabase** (Database & Authentication)
- **Google Gemini** (LLM)
- **yfinance** (Stock price data)

## Project Structure

```
FinanceAgent/
├── frontend/          # Next.js frontend application
│   ├── app/          # Next.js app router pages
│   ├── components/   # React components
│   └── package.json
├── backend/          # FastAPI backend application
│   ├── routers/      # API route handlers
│   ├── services/     # Business logic services
│   ├── database/     # Database schema and client
│   └── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- Supabase account and project
- Google Gemini API key

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

4. Run the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file:
```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER=gemini
FINNHUB_API_KEY=your_finnhub_api_key  # Optional, for stock search
```

5. Set up the database schema:
   - Run the SQL script in `backend/database/schema.sql` in your Supabase SQL editor
   - Disable email confirmation in Supabase Auth settings (for development)

6. Run the backend server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`

## Deployment

### Frontend (Vercel)

The frontend is configured for Vercel deployment:

1. Push your code to GitHub
2. Import the project in Vercel
3. Set the root directory to `frontend`
4. Add environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_API_URL` - Your backend API URL

### Backend

The backend can be deployed on:
- **Railway**: Easy Python deployment
- **Render**: Free tier available
- **Fly.io**: Good for FastAPI apps
- **AWS/GCP/Azure**: For production scale

Make sure to set all environment variables in your deployment platform.

## Environment Variables

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL

### Backend (.env)
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon key
- `GEMINI_API_KEY` - Google Gemini API key
- `GEMINI_MODEL` - Gemini model name (default: gemini-2.5-flash)
- `LLM_PROVIDER` - LLM provider (default: gemini)
- `FINNHUB_API_KEY` - Finnhub API key (optional)

## API Endpoints

### Authentication
- `POST /api/auth/signup` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Get current user

### Assets
- `GET /api/assets` - Get all assets
- `POST /api/assets` - Create new asset
- `GET /api/assets/{id}` - Get specific asset
- `PUT /api/assets/{id}` - Update asset
- `DELETE /api/assets/{id}` - Delete asset
- `POST /api/assets/update-prices` - Update stock prices
- `GET /api/assets/prices/{asset_id}` - Get stock price

### Chat
- `POST /api/chat/` - Send message to AI assistant

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
