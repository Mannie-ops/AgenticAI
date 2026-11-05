import os, re, time, sqlite3
from pathlib import Path
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).parent
DB = ROOT / "posts.db"
MODEL = os.getenv("MODEL", "gemini-3.8-flash")
KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
app = FastAPI(title="The Writing Studio")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class Generate(BaseModel):
    topic: str = Field(min_length=5, max_length=240)
    audience: str = "software engineers"
    tone: str = "practical and clear"

class Publish(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    topic: str = ""
    content: str = Field(min_length=100, max_length=50000)

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with connect() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, topic TEXT,
        content TEXT, created_at TEXT)""")


def ask_gemini(prompt):
    if not KEY:
        raise HTTPException(
            503,
            "Missing API key. Add GOOGLE_API_KEY to .env and restart."
        )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": 7000
        }
    }

    last_error = ""

    for attempt in range(3):
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(
                    URL.format(MODEL),
                    headers={"x-goog-api-key": KEY},
                    json=payload
                )

            # Safely read the response, even if it is not JSON.
            try:
                data = r.json()
            except ValueError:
                data = {}

            if r.status_code >= 400:
                if isinstance(data, dict):
                    message = data.get("error", {}).get("message")
                else:
                    message = None

                message = message or r.text[:1500] or "No error details returned."
                last_error = f"Gemini HTTP {r.status_code}: {message}"

                if r.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue

                raise HTTPException(
                    status_code=502,
                    detail=last_error
                )

            if not isinstance(data, dict):
                raise HTTPException(
                    status_code=502,
                    detail="Gemini returned a response that was not valid JSON."
                )

            candidates = data.get("candidates", [])
            parts = (
                candidates[0].get("content", {}).get("parts", [])
                if candidates else []
            )

            result = "\n".join(
                p.get("text", "") for p in parts if p.get("text")
            )

            if not result.strip():
                raise HTTPException(
                    status_code=502,
                    detail=f"Gemini returned no text. Response: {str(data)[:1000]}"
                )

            return result.strip()

        except httpx.RequestError as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue

            raise HTTPException(
                status_code=502,
                detail="Could not connect to Gemini: " + last_error
            )

    raise HTTPException(status_code=502, detail=last_error)


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status":"ok","model":MODEL,"api_key_configured":bool(KEY)}

@app.get("/api/posts")
def posts():
    with connect() as c:
        rows = c.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return [dict(x) for x in rows]

@app.get("/api/posts/{post_id}")
def post(post_id:int):
    with connect() as c:
        row = c.execute("SELECT * FROM posts WHERE id=?",(post_id,)).fetchone()
    if not row: raise HTTPException(404,"Post not found.")
    return dict(row)

@app.post("/api/generate")
def generate(req:Generate):
    topic, audience, tone = req.topic.strip(), req.audience, req.tone
    outline = ask_gemini(f"""You are the Planning Agent. Create a detailed, useful outline for a technical blog.
Topic: {topic}. Audience: {audience}. Tone: {tone}.
Include title, reader problem, sections, practical example, common mistakes, and conclusion.
Return only the outline in Markdown.""")
    draft = ask_gemini(f"""You are the Technical Blog Writer Agent. Write a complete, accurate and practical blog post.
Topic: {topic}. Audience: {audience}. Tone: {tone}.
Follow this approved outline:\n{outline}
Use a compelling H1, clear explanations, practical steps, a realistic example and conclusion.
Avoid fake statistics and invented citations. Return only the article in Markdown.""")
    final = ask_gemini(f"""You are the Editorial Validation Agent. Review and improve this article for technical
correctness, clarity, structure, usefulness and consistency. Fix repetitions and unclear examples.
Do not invent citations or statistics. Return the complete improved article in Markdown only.
Topic: {topic}\nDraft:\n{draft}""")
    match = re.search(r"^\s*#\s+(.+)$",final,re.M)
    return {"title":match.group(1).strip() if match else topic,"topic":topic,
            "outline":outline,"content":final,
            "agents":["Planner Agent","Writer Agent","Validation Agent"],"model":MODEL}

@app.post("/api/publish")
def publish(req:Publish):
    with connect() as c:
        cur = c.execute("INSERT INTO posts(title,topic,content,created_at) VALUES(?,?,?,?)",
            (req.title.strip(),req.topic.strip(),req.content.strip(),datetime.now(timezone.utc).isoformat()))
        post_id = cur.lastrowid
    return {"id":post_id,"published":True}
