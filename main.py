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
import pdfkit
from jinja2 import Template
import tempfile

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # You should set this as an environment variable in Railway
    GEMINI_API_KEY = "AIzaSyCnWDsYjgpqDmujB4xNS5-kW5ClvBv_Hcc"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

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

# Serve static files from current directory
app.mount("/static", StaticFiles(directory="."), name="static")

# PDFKit configuration - DISABLED FOR CLOUD
pdfkit_config = None

def setup_pdfkit():
    """PDFKit setup - disabled for cloud deployment"""
    logger.warning("PDF generation disabled - wkhtmltopdf not available in cloud")
    return None

pdfkit_config = setup_pdfkit()

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

# Serve the main application
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

@app.get("/style.css")
async def serve_css():
    return FileResponse("style.css")

# FIXED: Added proper route for the main interface
@app.get("/main")
async def serve_main():
    return FileResponse("index.html")

@app.post("/analyze-chat")
async def analyze_chat(
        message: str = Form(""),
        files: List[UploadFile] = File([])
):
    """Main analysis endpoint using Gemini"""
    try:
        logger.info(f"Analysis request - Message: {message[:100]}, Files: {len(files)}")
        
        # FIXED: Use raw strings to avoid escape sequence warnings
        system_prompt = r"""You are a **PhD-Level Math Teacher** analyzing student work.
**CRITICAL INSTRUCTIONS FOR OUTPUT:**
1. **ALL MATHEMATICAL EXPRESSIONS MUST BE IN LATEX/MATHJAX FORMAT** - Use $...$ for inline math and $$...$$ for display math.
2. **PRESERVE STUDENT'S ORIGINAL SOLUTION EXACTLY** - Copy verbatim what the student wrote from the images/files.
3. **IGNORE STRIKETHROUGH TEXT COMPLETELY** - Do not include strikethrough text in analysis.
4. **SEPARATE EACH QUESTION CLEARLY** - Each labeled question gets its OWN analysis section.
5. **ERROR ANALYSIS MUST BE VERY SHORT: ONE-LINER PER ERROR ONLY** - List only specific errors briefly.

**OUTPUT FORMAT:**
## Question [LABEL]:
**Full Question:** [Question text in MathJax]
### Student's Solution:
**Step 1:** [Copy line 1 EXACTLY in MathJax]
**Step 2:** [Copy line 2 EXACTLY in MathJax]
### Error Analysis:
**Step X Error:** [One-liner error description]
### Corrected Solution:
**Step 1:** [Mathematical setup in MathJax]
**Final Answer:** $$\boxed{final_answer}$$

[Include performance table and insights as before]"""
        
        # Process files
        file_contents = []
        file_descriptions = []
        for file in files:
            if file.content_type in ["application/pdf", "image/jpeg", "image/png", "image/jpg"]:
                pages = await process_uploaded_file(file)
                for page_b64 in pages:
                    file_contents.append({
                        "mime_type": "image/png",
                        "data": base64.b64decode(page_b64)
                    })
                file_descriptions.append(f"Processed {file.filename} ({len(pages)} pages)")
        
        # Prepare content for Gemini
        contents = [system_prompt]
        if message:
            contents.append(f"User request: {message}")
        contents.extend(file_contents)
        
        # Call Gemini
        response = model.generate_content(contents)
        ai_response = response.text
        
        # Parse detailed data for frontend
        detailed_data = parse_detailed_data_improved(ai_response)
        logger.info(f"Analysis completed. Found {len(detailed_data.get('questions', []))} questions")
        
        return JSONResponse({
            "status": "success",
            "response": ai_response,
            "detailed_data": detailed_data,
            "files_processed": file_descriptions
        })
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

def parse_detailed_data_improved(response_text):
    """Parse AI response for frontend display"""
    questions = []
    if not response_text:
        return {"questions": questions}
    
    # Simple question parsing
    question_sections = re.split(r'## Question\s+', response_text)
    question_sections = [section for section in question_sections if section.strip()]
    
    for i, section in enumerate(question_sections, 1):
        try:
            # Extract question ID
            question_id_match = re.search(r'^([A-Z]?[0-9]+[a-z]?(?:\([a-z]\))?[^:\n]*):?', section)
            question_id = question_id_match.group(1).strip() if question_id_match else f"Q{i}"
            
            # Extract question text
            question_text = "Question content"
            if '**Full Question:**' in section:
                question_part = section.split('**Full Question:**')[1]
                if '###' in question_part:
                    question_text = question_part.split('###')[0].strip()
            
            # Extract student work
            steps = []
            if '### Student\'s Solution' in section:
                solution_part = section.split('### Student\'s Solution')[1]
                if '###' in solution_part:
                    solution_section = solution_part.split('###')[0]
                    # Simple step extraction
                    step_matches = re.findall(r'\*\*Step\s+\d+:\*\*\s*(.*?)(?=\*\*Step\s+\d+:|###|\Z)', solution_section, re.DOTALL)
                    steps = [match.strip() for match in step_matches if match.strip()]
            
            if not steps:
                steps = ["No solution provided"]
            
            # Error detection
            mistakes = []
            has_errors = False
            if '### Error Analysis' in section:
                error_part = section.split('### Error Analysis')[1]
                if '###' in error_part:
                    error_section = error_part.split('###')[0]
                    error_matches = re.findall(r'\*\*Step\s*(\d+)\s*Error:\*\*\s*(.*?)(?=\*\*Step\s*\d+\s*Error:|\Z)', error_section, re.DOTALL)
                    for step_num, error_desc in error_matches:
                        if error_desc.strip():
                            has_errors = True
                            mistakes.append({
                                "step": step_num,
                                "status": "Error",
                                "desc": error_desc.strip()
                            })
            
            questions.append({
                "id": question_id,
                "questionText": question_text[:500] + "..." if len(question_text) > 500 else question_text,
                "steps": steps,
                "mistakes": mistakes,
                "hasErrors": has_errors,
                "correctedSteps": ["Complete solution will be shown after analysis"],
                "finalAnswer": "Answer will be determined after analysis"
            })
        except Exception as e:
            logger.error(f"Error parsing question {i}: {e}")
            questions.append({
                "id": f"Q{i}",
                "questionText": f"Question {i}",
                "steps": ["Analysis in progress"],
                "mistakes": [],
                "hasErrors": False,
                "correctedSteps": ["Solution analysis"],
                "finalAnswer": "Answer pending"
            })
    
    return {"questions": questions}

@app.post("/create-practice-paper")
async def create_practice_paper(request: dict):
    """Create practice paper based on mistakes"""
    try:
        detailed_data = request.get("detailed_data", {})
        questions_with_errors = []
        
        for q in detailed_data.get("questions", []):
            if q.get('hasErrors', False) and q.get('mistakes'):
                questions_with_errors.append(q)
        
        logger.info(f"Found {len(questions_with_errors)} questions with errors for practice paper")
        
        if not questions_with_errors:
            return JSONResponse({
                "success": False,
                "error": "No questions with errors found. Your solutions appear to be correct!"
            })
        
        # Simple practice paper prompt
        practice_prompt = f"""Create {len(questions_with_errors)} practice questions based on these errors.
        Focus on the same mathematical concepts but with different values.
        Format each as: '### Based on Question [NUMBER]' followed by the new question in MathJax."""
        
        response = model.generate_content(practice_prompt)
        practice_paper = response.text
        
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

# PDF endpoints - return simple messages since PDF generation is disabled
@app.post("/generate-performance-pdf")
async def generate_performance_pdf():
    return JSONResponse({
        "success": False,
        "error": "PDF generation is currently disabled in cloud deployment"
    })

@app.post("/generate-detailed-pdf")
async def generate_detailed_pdf():
    return JSONResponse({
        "success": False,
        "error": "PDF generation is currently disabled in cloud deployment"
    })

@app.post("/generate-practice-pdf")
async def generate_practice_pdf():
    return JSONResponse({
        "success": False,
        "error": "PDF generation is currently disabled in cloud deployment"
    })

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Math OCR Analyzer API is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
