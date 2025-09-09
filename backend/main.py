import os
import tempfile
import requests
import pdfplumber
import docx
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer, util

app = FastAPI(title="Resume Matcher (AI + API)")

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Load Sentence-BERT model
# ---------------------------
print("Loading AI embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded.")

# ---------------------------
# Helpers: Extract Resume Text
# ---------------------------
def extract_text_from_pdf(file_path):
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)

def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs if p.text])

# ---------------------------
# Upload Resume Endpoint
# ---------------------------
@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    ext = os.path.splitext(filename)[1].lower()

    # Save temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Extract text
    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(tmp_path)
        elif ext == ".docx":
            text = extract_text_from_docx(tmp_path)
        elif ext == ".txt":
            text = content.decode("utf-8", errors="ignore")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from resume")

    resume_embedding = model.encode(text, convert_to_tensor=True)
    words_count = len(text.split())
    chars_count = len(text)

    # ---------------------------
    # Fetch Jobs from API
    # ---------------------------
    url = "https://remotive.com/api/remote-jobs"
    try:
        res = requests.get(url)
        res.raise_for_status()
        jobs = res.json().get("jobs", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch jobs: {str(e)}")

    if not jobs:
        return JSONResponse({
            "resume_summary": {"words": words_count, "chars": chars_count},
            "top_matches": [],
            "message": "No jobs available from API."
        })

    # ---------------------------
    # Prepare job texts & filter empty
    # ---------------------------
    job_texts, job_data = [], []
    for j in jobs[:50]:  # limit for speed
        title = j.get("title", "")
        desc = j.get("description", "")
        text_block = " ".join([title, desc]).strip()
        if text_block:
            job_texts.append(text_block)
            job_data.append({
                "title": title,
                "company": j.get("company_name"),
                "location": j.get("candidate_required_location"),
                "mode": j.get("job_type"),
                "description": desc[:200] + "..."
            })

    if not job_texts:
        return JSONResponse({
            "resume_summary": {"words": words_count, "chars": chars_count},
            "top_matches": [],
            "message": "No suitable jobs found in API data."
        })

    # ---------------------------
    # Compute similarity
    # ---------------------------
    job_embeddings = model.encode(job_texts, convert_to_tensor=True)
    cos_scores = util.cos_sim(resume_embedding, job_embeddings)[0].cpu().tolist()

    # Pair jobs with scores
    results = []
    for job, score in zip(job_data, cos_scores):
        job["score"] = round(float(score), 4)
        results.append(job)

    # Sort by similarity
    results.sort(key=lambda x: x["score"], reverse=True)

    # Filter by threshold (0.3)
    top = [j for j in results if j["score"] > 0.3][:5]

    if not top:
        return JSONResponse({
            "resume_summary": {"words": words_count, "chars": chars_count},
            "top_matches": [],
            "message": "No suitable jobs found for this resume."
        })

    return JSONResponse({
        "resume_summary": {"words": words_count, "chars": chars_count},
        "top_matches": top
    })
