# How to Start FinanceApp

## Quick Start Commands

### Start Backend (Python FastAPI)

Open a terminal and run:
```bash
cd /Users/bharadwaj/Applications/FinanceAgent/backend
source ../venv/bin/activate
python main.py
```

The backend will be available at: `http://localhost:8000`

### Start Frontend (Next.js)

Open a **NEW** terminal window and run:
```bash
cd /Users/bharadwaj/Applications/FinanceAgent/frontend
npm run dev
```

The frontend will be available at: `http://localhost:3000`

## Important Notes

1. **You need TWO terminal windows** - one for backend, one for frontend
2. **Backend must be running first** before you can login
3. **Frontend must be in the `frontend` directory** to run `npm run dev`

## Verify Everything is Running

1. Check backend: Open `http://localhost:8000` in browser - should show:
   ```json
   {"message":"FinanceApp API","status":"running"}
   ```

2. Check frontend: Open `http://localhost:3000` in browser - should show the login page

## Troubleshooting

### Backend not starting?
- Make sure you're in the `backend` directory
- Make sure virtual environment is activated: `source ../venv/bin/activate`
- Check if port 8000 is already in use

### Frontend not starting?
- Make sure you're in the `frontend` directory (NOT root)
- Make sure Node.js is installed: `node -v`
- Try deleting `node_modules` and `.next` folder, then run `npm install` again

### Login not working?
- Make sure backend is running on port 8000
- Check browser console for errors
- Check backend terminal for error messages

