import os
import base64
import io
import json
import logging
from typing import List, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# State
question_files = []
answer_files = []

def pil_to_base64_png(im: Image.Image) -> str:
    """Convert PIL Image to base64 PNG string."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-question")
async def upload_question(files: List[UploadFile] = File(...)):
    """Upload question files (images only)."""
    global question_files
    try:
        question_files = []
        for file in files[:5]:  # Max 5 files
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            if image.size[0] > 800:
                image.thumbnail((800, 800))
            question_files.append(pil_to_base64_png(image))

        return JSONResponse({
            "success": True,
            "count": len(question_files),
            "message": f"Uploaded {len(files)} question file(s)"
        })
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Upload failed: {str(e)}"
        }, status_code=500)

@app.post("/upload-answer")
async def upload_answer(files: List[UploadFile] = File(...)):
    """Upload answer files (images only)."""
    global answer_files
    try:
        answer_files = []
        for file in files[:5]:  # Max 5 files
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            if image.size[0] > 800:
                image.thumbnail((800, 800))
            answer_files.append(pil_to_base64_png(image))

        return JSONResponse({
            "success": True,
            "count": len(answer_files),
            "message": f"Uploaded {len(files)} answer file(s)"
        })
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Upload failed: {str(e)}"
        }, status_code=500)

@app.post("/analyze")
async def analyze():
    """Analyze uploaded files with Gemini."""
    try:
        if not question_files or not answer_files:
            raise HTTPException(status_code=400, detail="Please upload both question and answer files")

        # Prepare images for Gemini
        gemini_contents = []

        # Add question images
        for img_b64 in question_files[:5]:  # Max 5 question images
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })

        # Add answer images
        for img_b64 in answer_files[:5]:  # Max 5 answer images
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })

        # System prompt for Gemini
        system_prompt = """You are a math tutor analyzing student work. Follow these rules STRICTLY:
1. Extract ALL questions and their numbers EXACTLY as they appear (e.g., "1(a)", "Q2", "Question 3").
2. For each question, show the student's answer EXACTLY as written. Preserve line breaks, symbols, everything. IGNORE strikethroughs.
3. Find mistakes in student's answer. Be BRIEF and PRECISE - just state the error in 1 sentence.
4. Provide your own CORRECTED solution. If student's answer matches yours (even with different steps), mark as correct.
5. Use PERFECT MathJax formatting: $inline$ for inline, $$display$$ for display.
6. Output format MUST BE:
---
QUESTION [EXACT_NUMBER]:
[Question text in MathJax]
STUDENT'S ANSWER:
[Exact answer text in MathJax]
MISTAKES:
- [Brief error 1]
- [Brief error 2] (or "No mistakes found" if correct)
CORRECTED SOLUTION:
[Your solution in MathJax]
MATCH: [YES/NO]
---
"""

        # Get analysis from Gemini
        response = model.generate_content([system_prompt] + gemini_contents)
        analysis_text = response.text

        # Parse the response
        questions = parse_gemini_response(analysis_text)

        return JSONResponse({
            "success": True,
            "questions": questions,
            "raw_analysis": analysis_text
        })

    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Analysis failed: {str(e)}"
        }, status_code=500)

def parse_gemini_response(text: str):
    """Parse Gemini response into structured questions."""
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

                elif current_section == "student" and line and not line.startswith(("MISTAKES:", "CORRECTED SOLUTION:", "MATCH:")):
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

@app.post("/reanalyze-question")
async def reanalyze_question(request: Request):
    """Reanalyze a specific question based on user feedback."""
    try:
        data = await request.json()
        question_id = data.get("question_id", "")
        feedback = data.get("feedback", "")
        original_question = data.get("original_question", {})

        if not feedback or not original_question:
            raise HTTPException(status_code=400, detail="Missing data")

        prompt = f"""Reanalyze this math question based on student feedback:
Original Question {question_id}:
{original_question.get('question_text', '')}
Student's Original Answer:
{original_question.get('student_answer', '')}
Student Feedback: {feedback}
Please provide:
1. Updated mistakes list (be brief)
2. Updated corrected solution
3. Match status (YES/NO)
Format:
MISTAKES:
- [brief mistakes]
CORRECTED SOLUTION:
[your solution]
MATCH: [YES/NO]"""

        response = model.generate_content(prompt)
        text = response.text

        # Parse the response
        mistakes = []
        corrected = ""
        is_correct = False

        lines = text.split('\n')
        current_section = None
        for line in lines:
            line = line.strip()
            if line == "MISTAKES:":
                current_section = "mistakes"
            elif line == "CORRECTED SOLUTION:":
                current_section = "corrected"
            elif line.startswith("MATCH:"):
                is_correct = "YES" in line.upper()
            elif current_section == "mistakes" and line.startswith("-"):
                mistakes.append(line[1:].strip())
            elif current_section == "corrected" and line and not line.startswith("MATCH:"):
                corrected += line + "\n"

        if not corrected:
            corrected = "Solution will be updated after reanalysis"

        return JSONResponse({
            "success": True,
            "updated_mistakes": mistakes,
            "updated_solution": corrected.strip(),
            "is_correct": is_correct,
            "message": "Question reanalyzed successfully"
        })

    except Exception as e:
        logger.error(f"Reanalysis error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Reanalysis failed: {str(e)}"
        }, status_code=500)

@app.post("/generate-question-paper")
async def generate_question_paper(request: Request):
    """Generate a new question paper based on wrong answers."""
    try:
        data = await request.json()
        wrong_questions = data.get("wrong_questions", [])

        if not wrong_questions:
            raise HTTPException(status_code=400, detail="No wrong questions provided")

        prompt = f"""Generate a new question paper based on the following wrong answers.
For each question, make minimal changes (e.g., change coefficients, sin→cos, numbers) to form new questions.
Keep the same structure and difficulty.
Original Questions:
{json.dumps(wrong_questions)}
Output format:
---
QUESTION [NEW_NUMBER]:
[New question text in MathJax]
---
"""

        response = model.generate_content(prompt)
        paper_text = response.text

        return JSONResponse({
            "success": True,
            "question_paper": paper_text
        })

    except Exception as e:
        logger.error(f"Question paper generation error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Question paper generation failed: {str(e)}"
        }, status_code=500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
