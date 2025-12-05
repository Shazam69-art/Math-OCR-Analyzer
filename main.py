import os
import base64
import io
import json
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from PIL import Image
import pypdfium2 as pdfium
import google.generativeai as genai
from typing import List
import logging
from datetime import datetime
import re
from fastapi import Request
from fastapi.responses import StreamingResponse

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")  # Changed to 1.5-flash for better compatibility

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CAS Education Math OCR Analyzer API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="."), name="static")

def pil_to_base64_png(im: Image.Image) -> str:
    """Convert PIL Image to base64 PNG string."""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def pdf_all_pages_to_png_b64(pdf_bytes: bytes, dpi: int = 150) -> list:
    """Render ALL pages of a PDF to PNG and return list of base64 strings."""
    try:
        doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
        if len(doc) == 0:
            return []
        scale = dpi / 72.0
        pages_b64 = []
        for i in range(len(doc)):
            page = doc[i]
            bitmap = page.render(scale=scale).to_pil()
            page_b64 = pil_to_base64_png(bitmap)
            pages_b64.append(page_b64)
        return pages_b64
    except Exception as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"PDF processing error: {str(e)}")

async def process_uploaded_file(file: UploadFile) -> List[str]:
    """Process uploaded file and return base64 encoded pages."""
    content = await file.read()
    if file.content_type == "application/pdf":
        return pdf_all_pages_to_png_b64(content)
    elif file.content_type.startswith("image/"):
        image = Image.open(io.BytesIO(content))
        return [pil_to_base64_png(image)]
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/style.css")
async def serve_css():
    return FileResponse("style.css")

@app.post("/analyze-chat")
async def analyze_chat(
        message: str = Form(""),
        files: List[UploadFile] = File([])
):
    """Main analysis endpoint using Gemini with STREAMING to prevent timeout."""
    try:
        logger.info(f"Analysis request - Message: {message[:100]}, Files: {len(files)}")
        
        # Create a streaming response
        async def generate():
            try:
                # Send initial status
                yield json.dumps({"status": "processing", "progress": 10, "message": "Starting analysis..."}) + "\n"
                
                # Process files (OPTIMIZED - limit files and pages)
                file_contents = []
                file_descriptions = []
                
                # Limit to max 2 files to prevent timeout
                files_to_process = files[:2]
                
                for file_idx, file in enumerate(files_to_process):
                    yield json.dumps({
                        "status": "processing", 
                        "progress": 20 + (file_idx * 15), 
                        "message": f"Processing {file.filename}..."
                    }) + "\n"
                    
                    if file.content_type in ["application/pdf", "image/jpeg", "image/png", "image/jpg"]:
                        content = await file.read()
                        file_descriptions.append(f"Processed {file.filename}")
                        
                        if file.content_type == "application/pdf":
                            pages = pdf_all_pages_to_png_b64(content)
                            for page_b64 in pages[:2]:  # Limit to 2 pages
                                file_contents.append({
                                    "mime_type": "image/png",
                                    "data": base64.b64decode(page_b64)
                                })
                        else:
                            image = Image.open(io.BytesIO(content))
                            if image.size[0] > 1000:
                                image.thumbnail((1000, 1000))
                            page_b64 = pil_to_base64_png(image)
                            file_contents.append({
                                "mime_type": "image/png",
                                "data": base64.b64decode(page_b64)
                            })
                
                # Send processing update
                yield json.dumps({
                    "status": "processing", 
                    "progress": 60, 
                    "message": "Sending to Gemini for analysis..."
                }) + "\n"
                
                # Prepare content for Gemini
                system_prompt = """Analyze math work. Output format:

Question [ID]:
Question: [text]
Student: [solution]
Errors: [brief]
Correct: [solution]

Keep under 200 words."""
                
                user_prompt = f"User request: {message}\n\nAnalyze these math documents:"
                
                # Prepare the content for Gemini
                contents = []
                if file_contents:
                    # Use only the first image to avoid timeouts
                    contents = [user_prompt] + file_contents[:1]
                else:
                    contents = [user_prompt]
                
                # Get response from Gemini
                response = model.generate_content(contents)
                full_response = response.text
                
                # Parse detailed data
                detailed_data = parse_detailed_data_improved(full_response)
                
                # Send completion
                yield json.dumps({
                    "status": "complete",
                    "response": full_response,
                    "detailed_data": detailed_data,
                    "files_processed": file_descriptions,
                    "progress": 100
                }) + "\n"
                
            except Exception as e:
                logger.error(f"Streaming analysis failed: {str(e)}")
                yield json.dumps({
                    "status": "error",
                    "error": f"Analysis failed: {str(e)}",
                    "progress": 0
                }) + "\n"
        
        # Return as streaming response
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache, no-transform"
            }
        )
        
    except Exception as e:
        logger.error(f"Analysis setup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis setup failed: {str(e)}")

def parse_detailed_data_improved(response_text):
    """Parse AI response into structured data."""
    questions = []
    if not response_text:
        return {"questions": questions}
    
    # Simple parsing - split by question markers
    lines = response_text.split('\n')
    current_question = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for question start
        if line.lower().startswith('question') or line.startswith('Q'):
            if current_question:
                questions.append(current_question)
            
            # Extract question ID
            question_id = line.split(':')[0].strip() if ':' in line else f"Q{len(questions)+1}"
            current_question = {
                "id": question_id,
                "questionText": "",
                "steps": [],
                "mistakes": [],
                "hasErrors": False,
                "correctedSteps": [],
                "finalAnswer": ""
            }
        
        # Look for question text
        elif line.lower().startswith('question:'):
            if current_question:
                current_question["questionText"] = line.replace('Question:', '').strip()
        
        # Look for student solution
        elif line.lower().startswith('student:'):
            if current_question:
                current_question["steps"].append(line.replace('Student:', '').strip())
        
        # Look for errors
        elif line.lower().startswith('errors:'):
            if current_question:
                error_desc = line.replace('Errors:', '').strip()
                if error_desc and error_desc.lower() != 'none':
                    current_question["hasErrors"] = True
                    current_question["mistakes"].append({
                        "step": 1,
                        "status": "Error",
                        "desc": error_desc
                    })
        
        # Look for correct solution
        elif line.lower().startswith('correct:'):
            if current_question:
                current_question["correctedSteps"].append(line.replace('Correct:', '').strip())
    
    # Add the last question
    if current_question:
        questions.append(current_question)
    
    # If no questions were parsed, create a default one
    if not questions:
        questions = [{
            "id": "Q1",
            "questionText": "Math problem analysis",
            "steps": ["Student's solution will appear here"],
            "mistakes": [],
            "hasErrors": False,
            "correctedSteps": ["Correct solution will appear here"],
            "finalAnswer": ""
        }]
    
    return {"questions": questions}

@app.post("/create-practice-paper")
async def create_practice_paper(request: dict):
    """Create practice paper based on mistakes."""
    try:
        detailed_data = request.get("detailed_data", {})
        questions_with_errors = []
        
        for q in detailed_data.get("questions", []):
            if q.get('hasErrors', False):
                questions_with_errors.append(q)
        
        if not questions_with_errors:
            return JSONResponse({
                "success": False,
                "error": "No questions with errors found."
            })
        
        # Create simple practice questions
        practice_questions = []
        for i, q in enumerate(questions_with_errors):
            practice_questions.append(f"### Practice Question {i+1}\nBased on: {q['id']}\n\nSolve a similar problem focusing on the same concept.")
        
        practice_paper = "\n\n".join(practice_questions)
        
        return JSONResponse({
            "success": True,
            "practice_paper": practice_paper,
            "questions_used": len(questions_with_errors)
        })
        
    except Exception as e:
        logger.error(f"Practice paper creation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Practice paper creation failed: {str(e)}"
        }, status_code=500)

@app.post("/generate-performance-pdf")
async def generate_performance_pdf(request: Request):
    """Simple PDF endpoint - returns JSON for now."""
    try:
        return JSONResponse({
            "success": True,
            "message": "PDF generation would be implemented here",
            "pdf_url": "#"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"PDF generation error: {str(e)}"
        }, status_code=500)

@app.post("/generate-detailed-pdf")
async def generate_detailed_pdf(request: Request):
    """Simple PDF endpoint - returns JSON for now."""
    try:
        return JSONResponse({
            "success": True,
            "message": "Detailed PDF would be generated here",
            "pdf_url": "#"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"PDF generation error: {str(e)}"
        }, status_code=500)

@app.post("/generate-practice-pdf")
async def generate_practice_pdf(request: Request):
    """Simple PDF endpoint - returns JSON for now."""
    try:
        return JSONResponse({
            "success": True,
            "message": "Practice PDF would be generated here",
            "pdf_url": "#"
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"PDF generation error: {str(e)}"
        }, status_code=500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

