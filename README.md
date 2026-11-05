# The Writing Studio

A FastAPI blogging website with a three-stage Gemini workflow:
1. Planner Agent creates an outline.
2. Writer Agent writes the technical article.
3. Validation Agent reviews and improves it.

Generated posts can be edited, downloaded as Markdown, and published to the homepage. Posts are stored in SQLite.

## Run on macOS

```bash
cd ai_writing_studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
open -e .env
```

Paste your Gemini API key after `GOOGLE_API_KEY=`, save, then run:

```bash
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

Get a key at https://aistudio.google.com/app/apikey. Never upload `.env` to GitHub; it is excluded by `.gitignore`.

## Deploy on Render

Push the folder to GitHub, create a Render Web Service from that repository, and use:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Set `GOOGLE_API_KEY` as a secret environment variable in Render. `render.yaml` is included. SQLite is fine for a demo; use persistent storage or a managed database for durable production data.
