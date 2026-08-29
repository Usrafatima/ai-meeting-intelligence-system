# Speech-to-Text Setup Guide

## Backend Run

Step 1: Create Virtual Environment

```bash
cd backend
python -m venv venv
```

Step 2: Activate Virtual Environment

```bash
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Step 4: Add Gemini API Key in `.env` file

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

Get API key from: https://aistudio.google.com/apikey

Step 5: Start Backend Server

```bash
python -m uvicorn app.main:app --reload
```

Backend runs at: http://localhost:8000

---

## Frontend Run

Step 1: Go to Frontend Folder

```bash
cd frontend
```

Step 2: Install Dependencies

```bash
npm install
```

Step 3: Start Frontend Server

```bash
npm run dev
```

Frontend runs at: http://localhost:3000

---

## How to Use

1. Open browser: http://localhost:3000
2. Sign Up / Login
3. Click "Upload Meeting"
4. Drag & drop audio file (MP3, WAV)
5. Enter meeting title
6. Click "Start Processing"
7. Wait for transcription
8. View transcript in meeting details

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| API key error | Add valid Gemini key in `backend/.env` |
| Port already in use | Change port or stop other app |
