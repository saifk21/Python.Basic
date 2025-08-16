# AnyCode Generator

A minimal full-stack app to generate and save code in any language.

- Backend: FastAPI, with OpenAI API integration (fallback to heuristic sample if no key)
- Frontend: Vite + React + TypeScript

## Prerequisites
- Node.js 18+
- Python 3.10+

## Setup

### Backend
```
cd /workspace/anycode/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: set your API key
export OPENAI_API_KEY=sk-...
# Optional: change model
export OPENAI_MODEL=gpt-4o-mini
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```
cd /workspace/anycode/frontend
npm install
npm run dev
```

Open http://localhost:5173

## Notes
- Without `OPENAI_API_KEY`, the backend returns simple fallback examples.
- Saved code is stored under `/workspace/anycode/jobs/<job_id>`.