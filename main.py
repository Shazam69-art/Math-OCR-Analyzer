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
from fastapi.staticfiles import StaticFiles
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
uploaded_files = {}

# ========== CUSTOM STATIC FILES FIX ==========
# Create a custom StaticFiles class that excludes WebSocket connections
class WebSocketSafeStaticFiles(StaticFiles):
    async def __call__(self, scope, receive, send):
        # Skip WebSocket connections (scope["type"] == "websocket")
        if scope["type"] == "websocket":
            # Return 404 for WebSocket connections to static files
            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [(b'content-type', b'application/json')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"error": "Not found"}',
            })
            return
        
        # For HTTP requests, use the normal static files handler
        await super().__call__(scope, receive, send)

# ========== ALL YOUR FUNCTIONS ==========
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

# ========== API ROUTES ==========
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
        for file in question_files[:5]:
            images = await process_image_file(file)
            question_images.extend(images)
        
        # Process answer files
        answer_images = []
        for file in answer_files[:5]:
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
    
    try:
        # Wait for client to start analysis
        data = await websocket.receive_json()
        
        if data.get("action") == "start_analysis":
            if job_id not in uploaded_files:
                await websocket.send_json({
                    "type": "error",
                    "message": "Job not found. Please upload files first."
                })
                return
            
            await start_analysis(job_id, websocket)
        elif data.get("action") == "cancel":
            return
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"Analysis failed: {str(e)}"
        })

async def start_analysis(job_id: str, websocket: WebSocket):
    """Start analysis process with streaming updates."""
    if job_id not in uploaded_files:
        await websocket.send_json({
            "type": "error",
            "message": "Job not found. Please upload files first."
        })
        return
    
    job_data = uploaded_files[job_id]
    
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
        await send_progress(websocket, 10, "Processing uploaded images...")
        
        # Prepare images for Gemini
        gemini_contents = []
        
        # Add question images
        for img_b64 in job_data["question_images"][:3]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })
        
        await send_progress(websocket, 25, "Extracting text from questions...")
        
        # Add answer images
        for img_b64 in job_data["answer_images"][:3]:
            img_data = base64.b64decode(img_b64)
            gemini_contents.append({
                "mime_type": "image/png",
                "data": img_data
            })
        
        await send_progress(websocket, 40, "Analyzing student answers...")
        await send_progress(websocket, 60, "Running AI analysis...")
        
        try:
            response = await asyncio.wait_for(
                model.generate_content_async([system_prompt] + gemini_contents),
                timeout=120.0
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
            
            question_data["id"] = f"Q{len(questions)+1}"
            questions.append(question_data)
            
        except Exception as e:
            logger.error(f"Error parsing section: {e}")
            continue
    
    return questions

# ... (keep all your other API routes: generate-paper, download, job, cleanup) ...

# ========== MOUNT STATIC FILES WITH FIX ==========
# Use our custom WebSocket-safe static files handler
app.mount("/", WebSocketSafeStaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
