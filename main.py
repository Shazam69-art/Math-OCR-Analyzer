import os
import base64
import io
import json
import logging
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from PIL import Image
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY required")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # or gemini-2.5-flash-exp

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

question_files = []
answer_files = []
analysis_questions = []

def pil_to_base64_png(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/style.css")
async def css():
    return FileResponse("style.css")

@app.post("/upload-question")
async def upload_question(files: List[UploadFile] = File(...)):
    global question_files
    question_files = []
    for file in files[:4]:
        if not file.content_type.startswith("image/"):
            raise HTTPException(400, "Images only")
        img = Image.open(io.BytesIO(await file.read()))
        if img.width > 800: img.thumbnail((800, 800))
        question_files.append(pil_to_base64_png(img))
    return {"success": True, "count": len(question_files)}

@app.post("/upload-answer")
async def upload_answer(files: List[UploadFile] = File(...)):
    global answer_files
    answer_files = []
    for file in files[:4]:
        if not file.content_type.startswith("image/"):
            raise HTTPException(400, "Images only")
        img = Image.open(io.BytesIO(await file.read()))
        if img.width > 800: img.thumbnail((800, 800))
        answer_files.append(pil_to_base64_png(img))
    return {"success": True, "count": len(answer_files)}

@app.post("/analyze")
async def analyze():
    global analysis_questions
    if not question_files or not answer_files:
        raise HTTPException(400, "Upload both")

    contents = []
    for b64 in question_files + answer_files:
        img_data = base64.b64decode(b64)
        contents.append({"mime_type": "image/png", "data": img_data})

    system_prompt = """You are an expert math tutor. Analyze every question in the images.

For each question, output EXACTLY this format (no extra text):

---
QUESTION [NUMBER AS IN IMAGE]:
[Full question in perfect MathJax]

STUDENT'S ANSWER:
[Exact student work in MathJax, preserve steps and line breaks]

MISTAKES:
- [Clear English explanation, e.g., "You forgot the chain rule when differentiating (x² + 1)"]
- [Another mistake in plain English, use MathJax only when showing math]
(If correct, write: - No mistakes found)

CORRECTED SOLUTION:
[Full correct step-by-step solution in clean MathJax]

MATCH: YES or NO
---

Rules:
- Use $...$ inline and $$...$$ display
- Never skip any question
- Be kind but precise
- Always give full corrected solution
"""

    response = model.generate_content([system_prompt] + contents, stream=True)

    async def streamer():
        full = ""
        for chunk in response:
            text = chunk.text
            full += text
            yield text
        # Save for paper generation
        analysis_questions = parse_response(full)
    
    return StreamingResponse(streamer(), media_type="text/plain")

def parse_response(text: str):
    questions = []
    for section in text.split("---"):
        section = section.strip()
        if "QUESTION" not in section: continue
        q = {"id": "", "question_text": "", "student_answer": "", "mistakes": [], "corrected_solution": "", "is_correct": False}
        lines = section.split("\n")
        mode = None
        for line in lines:
            line = line.strip()
            if line.startswith("QUESTION"):
                parts = line.split(":", 1)
                q["id"] = parts[0].replace("QUESTION", "").strip()
                if len(parts) > 1: q["question_text"] = parts[1].strip()
            elif line == "STUDENT'S ANSWER:": mode = "student"
            elif line == "MISTAKES:": mode = "mistakes"
            elif line == "CORRECTED SOLUTION:": mode = "corrected"
            elif line.startswith("MATCH:"): q["is_correct"] = "YES" in line.upper()
            elif mode == "student" and line: q["student_answer"] += line + "\n"
            elif mode == "mistakes" and line.startswith("-"):
                m = line[1:].strip()
                if "no mistakes" not in m.lower():
                    q["mistakes"].append(m)
            elif mode == "corrected" and line: q["corrected_solution"] += line + "\n"
        for k in ["question_text", "student_answer", "corrected_solution"]:
            q[k] = q[k].strip()
        if not q["id"]: q["id"] = f"Q{len(questions)+1}"
        questions.append(q)
    return questions

@app.post("/generate-paper")
async def generate_paper():
    global analysis_questions
    wrong = [q for q in analysis_questions if not q["is_correct"]]
    if not wrong:
        return {"success": True, "questions": []}

    prompt = "Generate new similar questions (change numbers/coeffs, sin→cos, etc.) for these wrong ones. Keep same ID. Use MathJax.\nFormat:\n---\nQUESTION [ID]:\n[New question in MathJax]\n---\n\nWrong questions:\n"
    prompt += "\n".join([f"QUESTION {q['id']}: {q['question_text']}" for q in wrong])

    resp = model.generate_content(prompt)
    new_qs = []
    for sec in resp.text.split("---"):
        sec = sec.strip()
        if "QUESTION" in sec:
            lines = sec.split("\n")
            qid = ""
            text = ""
            for line in lines:
                if line.startswith("QUESTION"):
                    qid = line.replace("QUESTION", "").split(":",1)[0].strip()
                else:
                    text += line + "\n"
            new_qs.append({"id": qid, "new_question": text.strip()})
    return {"success": True, "questions": new_qs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
