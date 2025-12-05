import os
import base64
import io
import json
import logging
import asyncio
import uvicorn
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles  # <-- Make sure this is imported
from PIL import Image
from pdf2image import convert_from_bytes
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI(title="Math OCR Analyzer")


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for WebSocket connections and analysis jobs
active_connections = {}
analysis_jobs = {}

# Store uploaded files temporarily (in production, use proper storage)
uploaded_files = {}

def pil_to_base64_png(im: Image.Image) -> str:
    """Convert PIL Image to base64 PNG string."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def pdf_to_images(pdf_bytes: bytes, max_pages: int = 10) -> List[str]:
    """Convert PDF to list of base64 encoded images."""
    try:
        images = convert_from_bytes(
            pdf_bytes,
            first_page=1,
            last_page=max_pages,
            dpi=150
        )
        
        image_b64_list = []
        for img in images:
            # Resize if too large
            if img.width > 1200:
                img.thumbnail((1200, 1200))
            image_b64_list.append(pil_to_base64_png(img))
        
        return image_b64_list
    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        return []

async def process_image_file(file: UploadFile) -> List[str]:
    """Process image file and return base64 encoded images."""
    content = await file.read()
    
    if file.content_type == "application/pdf":
        return pdf_to_images(content)
    elif file.content_type.startswith("image/"):
        image = Image.open(io.BytesIO(content))
        if image.size[0] > 1200:
            image.thumbnail((1200, 1200))
        return [pil_to_base64_png(image)]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/upload")
async def upload_files(
    question_files: List[UploadFile] = File(...),
    answer_files: List[UploadFile] = File(...),
    analysis_sheet: str = "integration"
):
    """Upload and process question/answer files."""
    try:
        job_id = str(uuid.uuid4())
        
        # Process question files
        question_images = []
        for file in question_files[:5]:  # Limit to 5 question files
            images = await process_image_file(file)
            question_images.extend(images)
        
        # Process answer files
        answer_images = []
        for file in answer_files[:5]:  # Limit to 5 answer files
            images = await process_image_file(file)
            answer_images.extend(images)
        
        # Store job data
        uploaded_files[job_id] = {
            "question_images": question_images,
            "answer_images": answer_images,
            "analysis_sheet": analysis_sheet,
            "created_at": datetime.now().isoformat(),
            "status": "uploaded"
        }
        
        return JSONResponse({
            "success": True,
            "job_id": job_id,
            "message": f"Uploaded {len(question_images)} question images and {len(answer_images)} answer images",
            "total_images": len(question_images) + len(answer_images)
        })
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Upload failed: {str(e)}"
        }, status_code=500)

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time analysis streaming."""
    await websocket.accept()
    active_connections[job_id] = websocket
    
    try:
        while True:
            # Wait for client to start analysis
            data = await websocket.receive_json()
            
            if data.get("action") == "start_analysis":
                await start_analysis(job_id, websocket)
            elif data.get("action") == "cancel":
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Analysis failed: {str(e)}"
        })
    finally:
        if job_id in active_connections:
            del active_connections[job_id]

async def start_analysis(job_id: str, websocket: WebSocket):
    """Start analysis process with streaming updates."""
    if job_id not in uploaded_files:
        await websocket.send_json({
            "type": "error",
            "message": "Job not found. Please upload files first."
        })
        return
    
    job_data = uploaded_files[job_id]
    
    # System prompt for math analysis - MOVED BEFORE try-except block
    system_prompt = """CRITICAL: You are analyzing scanned math exam papers. You MUST follow these rules STRICTLY:

1. EXTRACT EVERY SINGLE QUESTION from the images. Do NOT miss any.
2. Question numbers must be EXACT as shown (e.g., "1", "2(a)", "Q3", "Question 4").
3. For each question, show student's answer EXACTLY as written - preserve all symbols, formatting.
4. Find MATHEMATICAL errors only (not theoretical):
   - Incorrect calculations
   - Wrong formulas applied  
   - Missing steps in solution
   - Algebraic errors
   - Arithmetic mistakes
   - Sign errors
   - Units/conversion errors
5. Provide CORRECT SOLUTION with proper MathJax formatting:
   - Use $...$ for inline math
   - Use $$...$$ for display math
   - Escape properly: \\int, \\frac, \\sqrt, \\sin, \\cos
6. NO EXPLANATION SECTION - Only show: Original Question, Student's Answer, Mistakes, Correct Solution
7. If student's answer is correct: Mark as "MATCH: YES" and still show correct solution.
8. If you're unsure about a question, still include it with "Unable to analyze completely" in mistakes.

OUTPUT FORMAT FOR EACH QUESTION (strictly follow):
---
QUESTION [EXACT_NUMBER_FROM_IMAGE]:
[Question text in MathJax]

STUDENT'S ANSWER:
[Student's answer exactly as written in MathJax]

MISTAKES:
- [Mathematical error 1: e.g., "Incorrect: 2+2=5, Should be: 2+2=4"]
- [Mathematical error 2]

CORRECT SOLUTION:
[Complete correct solution in MathJax]

MATCH: [YES/NO]
---

IMPORTANT: Analyze ALL visible questions. If there are multiple parts (a, b, c), treat each as separate.
If student left blank, write "BLANK" as student answer and provide full solution."""
    
    try:
        # Send progress updates
        await send_progress(websocket, 10, "Processing uploaded images...")
        
        # Prepare images for Gemini (limit to reasonable number)
        gemini_contents = []
        
        # Add question images (max 3)
        for img_b64 in job_data["question_images"][:3]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })
        
        await send_progress(websocket, 25, "Extracting text from questions...")
        
        # Add answer images (max 3)
        for img_b64 in job_data["answer_images"][:3]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })
        
        await send_progress(websocket, 40, "Analyzing student answers...")
        
        await send_progress(websocket, 60, "Running AI analysis...")
        
        # Call Gemini with timeout - using a nested try-except for TimeoutError
        try:
            response = await asyncio.wait_for(
                model.generate_content_async([system_prompt] + gemini_contents),
                timeout=120.0  # 2 minute timeout
            )
            analysis_text = response.text
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "message": "Analysis timed out. Please try with fewer images or smaller files."
            })
            return
        
        await send_progress(websocket, 80, "Parsing analysis results...")
        
        # Parse the response
        questions = parse_gemini_response(analysis_text)
        
        await send_progress(websocket, 90, "Generating final report...")
        
        # Store results
        analysis_jobs[job_id] = {
            "questions": questions,
            "raw_analysis": analysis_text,
            "completed_at": datetime.now().isoformat()
        }
        
        # Send final results
        await websocket.send_json({
            "type": "result",
            "data": {
                "sheetName": job_data["analysis_sheet"],
                "questions": questions
            }
        })
        
        await send_progress(websocket, 100, "Analysis complete!")
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Analysis failed: {str(e)}"
        })



async def send_progress(websocket: WebSocket, progress: int, message: str):
    """Send progress update to client."""
    await websocket.send_json({
        "type": "progress",
        "progress": progress,
        "message": message
    })
    # Small delay to allow UI updates
    await asyncio.sleep(0.1)

def parse_gemini_response(text: str) -> List[Dict[str, Any]]:
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
                "number": "",
                "originalQuestion": "",
                "studentAnswer": "",
                "correctAnswer": "",
                "mistakes": [],
                "isCorrect": False
            }
            
            current_section = None
            for line in lines:
                line = line.strip()
                
                if line.startswith("QUESTION"):
                    # Extract question number
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        question_data["number"] = parts[0].replace("QUESTION", "").strip()
                        question_data["originalQuestion"] = parts[1].strip()
                    else:
                        question_data["number"] = line.replace("QUESTION", "").strip()
                
                elif line == "STUDENT'S ANSWER:":
                    current_section = "student"
                elif line == "MISTAKES:":
                    current_section = "mistakes"
                elif line == "CORRECT SOLUTION:":
                    current_section = "correct"
                elif line.startswith("MATCH:"):
                    question_data["isCorrect"] = "YES" in line.upper()
                    current_section = None
                
                elif current_section == "student" and line and not line.startswith(("MISTAKES:", "CORRECT SOLUTION:", "MATCH:")):
                    question_data["studentAnswer"] += line + "\n"
                elif current_section == "mistakes" and line and line.startswith("-"):
                    mistake = line[1:].strip()
                    if mistake and "no mistakes" not in mistake.lower():
                        question_data["mistakes"].append(mistake)
                elif current_section == "correct" and line and not line.startswith("MATCH:"):
                    question_data["correctAnswer"] += line + "\n"
            
            # Clean up text
            for key in ["originalQuestion", "studentAnswer", "correctAnswer"]:
                if question_data[key]:
                    question_data[key] = question_data[key].strip()
            
            # Generate ID
            question_data["id"] = f"Q{len(questions)+1}"
            
            questions.append(question_data)
            
        except Exception as e:
            logger.error(f"Error parsing section: {e}")
            continue
    
    return questions


@app.post("/api/generate-paper")
async def generate_practice_paper(request: dict):
    """Generate practice paper from analysis results."""
    try:
        job_id = request.get("job_id")
        question_ids = request.get("question_ids", [])
        
        if job_id not in analysis_jobs:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        
        job = analysis_jobs[job_id]
        selected_questions = [q for q in job["questions"] if q["id"] in question_ids and not q["isCorrect"]]
        
        if not selected_questions:
            raise HTTPException(status_code=400, detail="No questions selected for redesign")
        
        # Generate redesigned questions
        redesigned_content = generate_redesigned_paper(selected_questions)
        
        # Create downloadable file
        filename = f"practice_paper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = Path("generated_papers") / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, "w") as f:
            f.write(redesigned_content)
        
        return JSONResponse({
            "success": True,
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "message": f"Generated practice paper with {len(selected_questions)} questions"
        })
        
    except Exception as e:
        logger.error(f"Paper generation error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Paper generation failed: {str(e)}"
        }, status_code=500)

def generate_redesigned_paper(questions: List[Dict[str, Any]]) -> str:
    """Generate practice paper with redesigned questions."""
    content = "PRACTICE PAPER - MATH PROBLEMS\n"
    content += "=" * 50 + "\n\n"
    
    for i, question in enumerate(questions, 1):
        content += f"Question {i} (Based on {question['number']})\n"
        content += "-" * 30 + "\n\n"
        
        # Generate redesigned version
        redesigned = redesign_question(question["originalQuestion"])
        content += f"{redesigned}\n\n"
        
        content += "Common Error to Avoid:\n"
        if question["mistakes"]:
            content += f"• {question['mistakes'][0]}\n\n"
        
        content += "Space for Solution:\n"
        content += "\n" * 5
        content += "=" * 50 + "\n\n"
    
    return content

def redesign_question(question_text: str) -> str:
    """Redesign question by changing coefficients/variables."""
    # Simple coefficient/variable replacement
    replacements = {
        '3': '5', '2': '4', '1': '3', '4': '6',
        'x': 't', 'y': 'z',
        '\\sin': '\\cos', '\\cos': '\\sin',
        'a': 'm', 'b': 'n'
    }
    
    redesigned = question_text
    for old, new in replacements.items():
        redesigned = redesigned.replace(old, new)
    
    return redesigned

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Download generated practice paper."""
    filepath = Path("generated_papers") / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="text/plain"
    )

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status of analysis job."""
    if job_id in analysis_jobs:
        return JSONResponse({
            "status": "completed",
            "job_id": job_id,
            "questions_count": len(analysis_jobs[job_id]["questions"])
        })
    elif job_id in uploaded_files:
        return JSONResponse({
            "status": "uploaded",
            "job_id": job_id
        })
    else:
        raise HTTPException(status_code=404, detail="Job not found")

@app.delete("/api/cleanup")
async def cleanup_old_files():
    """Clean up old uploaded files and analysis jobs."""
    cutoff_time = datetime.now().timestamp() - 3600  # 1 hour ago
    
    # Clean uploaded files
    jobs_to_remove = []
    for job_id, data in uploaded_files.items():
        created_time = datetime.fromisoformat(data["created_at"]).timestamp()
        if created_time < cutoff_time:
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del uploaded_files[job_id]
    
    # Clean analysis jobs
    jobs_to_remove = []
    for job_id, data in analysis_jobs.items():
        if job_id not in uploaded_files:
            jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del analysis_jobs[job_id]
    
    return JSONResponse({
        "success": True,
        "cleaned_files": len(jobs_to_remove),
        "message": f"Cleaned up {len(jobs_to_remove)} old jobs"
    })

# FIX: Serve static files from current directory
app.mount("/", StaticFiles(directory=".", html=True), name="static")



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)







