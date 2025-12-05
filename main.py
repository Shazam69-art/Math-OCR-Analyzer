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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI(title="Math Analyzer")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store uploaded files temporarily (base64 images)
question_files = []
answer_files = []
analysis_questions = []  # Store analysis results globally

def pil_to_base64_png(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/style.css")
async def serve_css():
    return FileResponse("style.css")

@app.post("/upload-question")
async def upload_question(files: List[UploadFile] = File(...)):
    global question_files
    try:
        question_files = []
        for file in files[:4]:  # Max 4 images
            if not file.content_type.startswith("image/"):
                raise HTTPException(400, "Only images allowed (jpg, jpeg, png)")
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            if image.size[0] > 800:
                image.thumbnail((800, 800))
            question_files.append(pil_to_base64_png(image))
        return JSONResponse({"success": True, "count": len(question_files)})
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/upload-answer")
async def upload_answer(files: List[UploadFile] = File(...)):
    global answer_files
    try:
        answer_files = []
        for file in files[:4]:  # Max 4 images
            if not file.content_type.startswith("image/"):
                raise HTTPException(400, "Only images allowed (jpg, jpeg, png)")
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            if image.size[0] > 800:
                image.thumbnail((800, 800))
            answer_files.append(pil_to_base64_png(image))
        return JSONResponse({"success": True, "count": len(answer_files)})
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/analyze")
async def analyze():
    global analysis_questions
    try:
        if not question_files or not answer_files:
            raise HTTPException(400, "Upload both question and answer images")

        gemini_contents = []
        for img_b64 in question_files[:4]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({"mime_type": "image/png", "data": img_data})

        for img_b64 in answer_files[:4]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({"mime_type": "image/png", "data": img_data})

        system_prompt = """You are a math tutor analyzing student work. Follow these rules STRICTLY:
1. Analyze EVERY question completely. NEVER skip any question.
2. Extract ALL questions and their numbers EXACTLY as they appear (e.g., "1(a)", "Q2", "Question 3").
3. For each question, show the student's answer EXACTLY as written. Preserve line breaks, symbols, everything. IGNORE strikethroughs.
4. Find mistakes in student's answer. Be BRIEF and PRECISE - just state the simple mathematical error representation in 1 sentence, no theoretical description.
5. Provide your own CORRECTED solution. If student's answer matches yours (even with different steps), mark as correct.
6. Use PERFECT MathJax formatting: $inline$ for inline, $$display$$ for display.
7. Continue until ALL questions are processed. No timeout or skipping.
8. Output format MUST BE:
---
QUESTION [EXACT_NUMBER]:
[Question text in MathJax]
STUDENT'S ANSWER:
[Exact answer text in MathJax]
MISTAKES:
- [Simple math error 1]
- [Simple math error 2] (or "No mistakes found" if correct)
CORRECTED SOLUTION:
[Your solution in MathJax]
MATCH: [YES/NO]
---
"""

        response = model.generate_content([system_prompt] + gemini_contents, stream=True)

        async def generate():
            full_text = ""
            for chunk in response:
                full_text += chunk.text
                yield chunk.text + "\n"
            # Parse server-side for global storage
            questions = parse_gemini_response(full_text)
            analysis_questions = questions

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

def parse_gemini_response(text: str):
    questions = []
    sections = text.split("---")
   
    for section in sections:
        section = section.strip()
        if not section or "QUESTION" not in section:
            continue
           
        try:
            lines = section.split('\n')
            question_data = {
                "id": "",
                "question_text": "",
                "student_answer": "",
                "mistakes": [],
                "corrected_solution": "",
                "is_correct": False
            }
           
            current_section = None
            for line in lines:
                line = line.strip()
               
                if line.startswith("QUESTION"):
                    # Extract question number
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        question_data["id"] = parts[0].replace("QUESTION", "").strip()
                        question_data["question_text"] = parts[1].strip()
                    else:
                        question_data["id"] = line.replace("QUESTION", "").strip()
               
                elif line == "STUDENT'S ANSWER:":
                    current_section = "student"
                elif line == "MISTAKES:":
                    current_section = "mistakes"
                elif line == "CORRECTED SOLUTION:":
                    current_section = "corrected"
                elif line.startswith("MATCH:"):
                    question_data["is_correct"] = "YES" in line.upper()
               
                elif current_section == "student" and line and not line.startsWith(("MISTAKES:", "CORRECTED SOLUTION:", "MATCH:")):
                    question_data["student_answer"] += line + "\n"
                elif current_section == "mistakes" and line and line.startswith("-"):
                    mistake = line[1:].strip()
                    if mistake and "no mistakes" not in mistake.lower():
                        question_data["mistakes"].append(mistake)
                elif current_section == "corrected" and line and not line.startswith("MATCH:"):
                    question_data["corrected_solution"] += line + "\n"
           
            # Clean up text
            for key in ["question_text", "student_answer", "corrected_solution"]:
                if question_data[key]:
                    question_data[key] = question_data[key].strip()
           
            # If no ID, generate one
            if not question_data["id"]:
                question_data["id"] = f"Q{len(questions)+1}"
           
            questions.append(question_data)
           
        except Exception as e:
            logger.error(f"Error parsing section: {e}")
            continue
   
    # If parsing failed, create a simple structure
    if not questions:
        questions = [{
            "id": "Q1",
            "question_text": "Math problem from uploaded files",
            "student_answer": "Student's solution will appear here",
            "mistakes": ["Analysis in progress"],
            "corrected_solution": "Correct solution will appear here",
            "is_correct": False
        }]
   
    return questions

@app.post("/generate-paper")
async def generate_paper():
    global analysis_questions
    try:
        wrong_questions = [q for q in analysis_questions if not q["is_correct"]]
        if not wrong_questions:
            return JSONResponse({"success": True, "questions": []})

        prompt = """Generate a new question paper based on these wrong questions. For each:
- Keep the same question number and structure.
- Make minimal changes: change coefficients, sin to cos, numbers, etc.
- Output in MathJax format.
Format:
---
QUESTION [EXACT_NUMBER]:
[New question text in MathJax]
---
"""
        wrong_text = "\n".join([f"QUESTION {q['id']}: {q['question_text']}" for q in wrong_questions])
        response = model.generate_content(prompt + wrong_text)
        new_questions = parse_generated_response(response.text)
        return JSONResponse({"success": True, "questions": new_questions})
    except Exception as e:
        logger.error(f"Generation error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

def parse_generated_response(text: str):
    questions = []
    sections = text.split("---")
    for section in sections:
        section = section.strip()
        if not section or "QUESTION" not in section:
            continue
        lines = section.split('\n')
        q_data = {"id": "", "new_question": ""}
        for line in lines:
            line = line.strip()
            if line.startswith("QUESTION"):
                parts = line.split(":", 1)
                q_data["id"] = parts[0].replace("QUESTION", "").strip()
                if len(parts) > 1:
                    q_data["new_question"] = parts[1].strip()
            else:
                q_data["new_question"] += line + "\n"
        q_data["new_question"] = q_data["new_question"].strip()
        questions.append(q_data)
    return questions

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

