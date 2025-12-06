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
import google.generativeai as genai
from typing import List
import logging
from datetime import datetime
import re
from fastapi import Request
# Add these imports (around line 8)
import asyncio
import httpx
from fastapi import BackgroundTasks
from contextlib import asynccontextmanager

# Add this after other imports (around line 15-20)
TIMEOUT = 300  # 5 minutes timeout for Gemini API

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    "gemini-2.5-flash",  # Using flash model for faster response
    generation_config={
        "temperature": 0.1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }
)


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

async def process_uploaded_file(file: UploadFile) -> List[str]:
    """Process uploaded file and return base64 encoded pages."""
    content = await file.read()
    
    if file.content_type == "application/pdf":
        # For PDF files, we'll just return a placeholder since pypdfium2 is not available
        # In production, you should install pypdfium2 or use an alternative PDF library
        logger.warning("PDF processing requires pypdfium2. Install it for full functionality.")
        raise HTTPException(status_code=400, detail="PDF processing is not available. Please install pypdfium2 or convert PDFs to images.")
    
    elif file.content_type.startswith("image/"):
        try:
            image = Image.open(io.BytesIO(content))
            return [pil_to_base64_png(image)]
        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Image processing error: {str(e)}")
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
    files: List[UploadFile] = File([]),
    background_tasks: BackgroundTasks = None
):
    """Main analysis endpoint with timeout handling."""
    try:
        logger.info(f"Analysis request - Message: {message[:100]}, Files: {len(files)}")
        
        # ENHANCED SYSTEM PROMPT WITH PERFORMANCE TABLE
        system_prompt = r"""You are a **PhD-Level Math Teacher** analyzing student work.

**CRITICAL INSTRUCTIONS FOR OUTPUT:**
1. **ALL MATHEMATICAL EXPRESSIONS MUST BE IN LATEX/MATHJAX FORMAT** - Use $...$ for inline math and $$...$$ for display math.
2. **STUDENT SOLUTION PRESERVATION - COPY EXACTLY:** 
   - Copy VERBATIM what the student wrote from the images
   - If student wrote "$x^2 + 3x$", output "$x^2 + 3x$" exactly
   - If student made mistake like "$x^2 + 3x = 5x$", output it EXACTLY
   - DO NOT correct student mistakes in their solution section
   - DO NOT add explanatory text like "the student wrote..."
3. **IGNORE STRIKETHROUGH TEXT COMPLETELY**
4. **SEPARATE EACH QUESTION CLEARLY**
5. **ERROR ANALYSIS - SHORT AND MATHEMATICAL:**
   - Format: "Step X: [Brief error in 5-10 words with MathJax]"
   - Example: "Step 2: Wrong derivative: $\frac{d}{dx}x^3 = 3x^2$"
   - NO long English explanations
6. **QUESTION IDENTIFICATION:** If unclear from images, mark as "Question [number]"
7. **FINAL LLM SOLUTION:** 100% complete with ALL steps

**OUTPUT FORMAT - FOLLOW EXACTLY:**
## Question [Number or Label]:
**Question:** [Best interpretation from image in MathJax]
### Student's Solution (Exact Copy):
[Copy EXACTLY what student wrote, line by line in MathJax]
### Error Analysis:
Step X: [Short mathematical error with MathJax]
### Corrected Solution:
Step 1: [Complete step in MathJax]
Step 2: [Complete step in MathJax]
...
**Final Answer:** $$\boxed{answer}$$

**PERFORMANCE TABLE (UPDATE BASED ON ACTUAL ERRORS FOUND)**
| Concept No. | Concept (With Explanation) | Example | Status |
|-------------|----------------------------|---------|--------|
| 1 | Basic Formulas | Standard Formula of Integration | **Performance:** Not Tested |
| 2 | Application of Formulae | \(\int x^9 dx = \frac{x^{10}}{10} + C\) | **Performance:** Not Tested |
| 3 | Basic Trigonometric Ratios Integration | Integration of \(\sin x, \cos x, \tan x, \sec x, \cot x, \csc x\) | **Performance:** Not Tested |
| 4 | Basic Squares & Cubes Trigonometric Ratios Integration | \(\int \tan^2 x dx, \int \cot^2 x dx, \int \sin^2 2x dx, \int \cos^2 2x dx\) | **Performance:** Not Tested |
| 5 | Integration of Linear Functions via Substitution | \(\int (3x+5)^7 dx, \int (4-9x)^5 dx, \int \sec^2 (3x+5) dx\) | **Performance:** Not Tested |
| 6 | Basic Substitution (level 1) | \(\int \frac{\log x}{x} dx, \int \frac{\sec^2 (\log x)}{x} dx, \int \frac{e^{\tan^{-1}x}}{1+x^2} dx, \int \frac{\sin \sqrt{x}}{\sqrt{x}} dx\) | **Performance:** Not Tested |
| 7 | Substitution (Some Simplification Involved) (level 2) | \(\int \frac{2x}{(2x+1)^2} dx, \int \frac{2+3x}{3-2x} dx\) | **Performance:** Not Tested |
| 8 | Complex Substitution (Some Simplification Involved) (level 3) | \(\int \frac{dx}{x \sqrt{x^6 - 1}}, \int \frac{x^2 \tan^{-1} x^3}{1+x^6} dx\) | **Performance:** Not Tested |
| 9 | Substitution with Square root | \(\int \frac{x-1}{\sqrt{x+4}} dx, \int x \sqrt{x+2} dx\) | **Performance:** Not Tested |
| 10 | Same order Integration (Solving by adding and subtraction) | \(\int \frac{3x^2}{1+x^2} dx\) | **Performance:** Not Tested |
| 11 | Using formulae & completing the square methods<br/>(i) \(\int \frac{dx}{a^2 - x^2} = \frac{1}{2a} \log \left\lvert \frac{a + x}{a - x} \right\rvert + C\)<br/>(ii) \(\int \frac{dx}{x^2 - a^2} = \frac{1}{2a} \log \left\lvert \frac{x - a}{x + a} \right\rvert + C\) | \(\int \frac{dx}{x^2 + 8x + 20}\) | **Performance:** Not Tested |
| 12 | Standard Integrals<br/>(i) \(\int \frac{dx}{\sqrt{a^2 - x^2}} = \sin^{-1} \frac{x}{a} + C\)<br/>(ii) \(\int \frac{dx}{\sqrt{x^2 - a^2}} = \log \left\lvert x + \sqrt{x^2 - a^2} \right\rvert + C\)<br/>(iii) \(\int \frac{dx}{\sqrt{x^2 + a^2}} = \log \left\lvert x + \sqrt{x^2 + a^2} \right\rvert + C\) | **Evaluate:**<br/>(i) \(\int \frac{dx}{\sqrt{9 - 25x^2}}\)<br/>(ii) \(\int \frac{dx}{\sqrt{x^2 - 3x + 2}}\) | **Performance:** Not Tested |
| 13 | Integration of Linear In Numerator and Quadratic (or Sq Root of Quadratic) In Denominator.<br/>Integrals of the form:<br/>\( \int \frac{(px + q)}{\sqrt{(ax^2 + bx + c)}} dx \)<br/>\( \int \frac{(px + q)}{(ax^2 + bx + c)} dx \) | \(\int \frac{(5x + 3)}{\sqrt{x^2 + 4x + 10}} dx\)<br/>\( \int \frac{(2x + 1)}{(4 - 3x - x^2)} dx\) | **Performance:** Not Tested |
| 14 | By Parts (ILATE)<br/>\( \int (uv) dx = u \int v dx - \int \left( \frac{du}{dx} \int v dx \right) dx \) | (i) \(\int x \sec^2 x dx\) | **Performance:** Not Tested |
| 15 | By Part - In which "1" has to be taken as one of the functions to start solving. | \(\int \log x dx\)<br/>(ii) \(\int \tan^{-1} x dx\) | **Performance:** Not Tested |
| 16 | Inverse Trigonometric By Parts | (ii) \(\int \tan^{-1} x dx\) | **Performance:** Not Tested |
| 17 | Integrals of the form \(\int e^x [f(x) + f'(x)] dx\) | (ii) \(\int e^x \left( \frac{1}{x^2} - \frac{2}{x^3} \right) dx\) | **Performance:** Not Tested |
| 18 | Integration of (e^x)(sinx)<br/>Where terms keeps on repeating.<br/>\( \int e^{2x} \sin x dx \) | \(\int e^{3x} \sin 4x dx\)<br/>\( \int e^{3x} \sin 4x dx\) | **Performance:** Not Tested |
**UPDATE TABLE BASED ON ACTUAL ANALYSIS:** For each concept tested, update status.
## Performance Insights
[Provide insights with MathJax where needed]"""
        
        # Check file count for timeout prevention
        if len(files) > 8:
            raise HTTPException(
                status_code=400,
                detail="Too many files (maximum 8). Please analyze 2-3 questions at a time."
            )
        
        # Process files
        file_contents = []
        file_descriptions = []
        for file in files:
            if file.content_type in ["application/pdf", "image/jpeg", "image/png", "image/jpg"]:
                try:
                    pages = await process_uploaded_file(file)
                    for page_b64 in pages:
                        file_contents.append({
                            "mime_type": "image/png",
                            "data": base64.b64decode(page_b64)
                        })
                    file_descriptions.append(f"Processed {file.filename} ({len(pages)} pages)")
                except HTTPException as he:
                    raise he
                except Exception as e:
                    logger.error(f"Error processing file {file.filename}: {str(e)}")
                    file_descriptions.append(f"Failed to process {file.filename}: {str(e)}")
        
        if not file_contents:
            raise HTTPException(status_code=400, detail="No valid image files processed")
        
        # Prepare content for Gemini
        contents = [system_prompt]
        if message:
            contents.append(f"User request: {message}")
        contents.extend(file_contents)
        
        # Call Gemini with timeout handling
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(contents),
                timeout=TIMEOUT
            )
            ai_response = response.text
        except asyncio.TimeoutError:
            logger.error("Gemini API timeout")
            raise HTTPException(
                status_code=504, 
                detail="Analysis timed out. Try with fewer files (2-3 questions maximum)."
            )
        except Exception as genai_error:
            logger.error(f"Gemini API error: {str(genai_error)}")
            raise HTTPException(status_code=500, detail="Analysis service error. Please try with fewer files.")
        
        # Parse detailed data
        detailed_data = parse_detailed_data_fixed(ai_response)
        logger.info(f"Analysis completed. Found {len(detailed_data.get('questions', []))} questions")
        
        return JSONResponse({
            "status": "success",
            "response": ai_response,
            "detailed_data": detailed_data,
            "files_processed": file_descriptions
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

def parse_detailed_data_fixed(response_text):
    """FIXED parsing that preserves student solutions exactly and keeps table."""
    questions = []
    if not response_text:
        return {"questions": questions}
    
    # Split response to separate questions from table
    table_start = response_text.find("## Performance Insights")
    if table_start == -1:
        table_start = response_text.find("PERFORMANCE TABLE")
    if table_start == -1:
        table_start = len(response_text)
    
    # Get questions section (before table)
    questions_section = response_text[:table_start]
    
    # Split by question markers
    question_patterns = [
        r'## Question\s+',
        r'## Q\.?\s*\d+',
        r'\*\*\d+\.\*\*'
    ]
    
    question_sections = []
    for pattern in question_patterns:
        if re.search(pattern, questions_section, re.IGNORECASE):
            question_sections = re.split(pattern, questions_section, flags=re.IGNORECASE)
            break
    
    if not question_sections or len(question_sections) < 2:
        # Try simple split
        question_sections = re.split(r'\n##\s+', questions_section)
    
    # Remove empty sections
    question_sections = [s for s in question_sections if s.strip() and len(s.strip()) > 20]
    
    for i, section in enumerate(question_sections, 1):
        try:
            # Extract question ID
            id_patterns = [
                r'^([A-Z]?[0-9]+[a-z]?(?:\([a-z]\))?[^:\n]*):?',
                r'^(Q?[0-9]+[a-z]?(?:\s*\([a-z]\))?)',
                r'^([^:\n]+)'
            ]
            
            question_id = f"Q{i}"
            for pattern in id_patterns:
                id_match = re.search(pattern, section)
                if id_match:
                    question_id = id_match.group(1).strip()
                    break
            
            # Extract question text - SIMPLIFIED
            question_text = "Question"
            q_match = re.search(r'\*\*Question:\*\*\s*(.*?)(?=\n###|\n\*\*|\Z)', section, re.DOTALL)
            if q_match:
                question_text = q_match.group(1).strip()
            elif '**Question:**' in section:
                parts = section.split('**Question:**', 1)
                if len(parts) > 1:
                    question_text = parts[1].split('\n')[0].strip()
            
            # CRITICAL: Extract student solution EXACTLY
            student_solution = []
            if '### Student\'s Solution' in section:
                # Get everything between Student's Solution and next section
                sol_sections = re.split(r'### (?:Student\'s Solution|Error Analysis|Corrected Solution)', section, flags=re.IGNORECASE)
                if len(sol_sections) > 1:
                    student_text = sol_sections[1]
                    # Clean but preserve math
                    lines = [line.strip() for line in student_text.split('\n') if line.strip()]
                    # Remove any explanatory text
                    clean_lines = []
                    for line in lines:
                        if not line.startswith(('Note:', 'The student', 'Here the student', 'Student wrote:')):
                            clean_lines.append(line)
                    student_solution = clean_lines[:10]  # Limit to 10 lines
            
            if not student_solution or len(student_solution) == 0:
                student_solution = ["No clear solution in image"]
            
            # Extract errors - SIMPLE
            mistakes = []
            if '### Error Analysis' in section:
                error_sections = re.split(r'### Error Analysis:', section, flags=re.IGNORECASE)
                if len(error_sections) > 1:
                    error_text = error_sections[1].split('###')[0] if '###' in error_sections[1] else error_sections[1]
                    # Find step errors
                    step_pattern = r'Step\s*(\d+)[:\s]+(.*?)(?=Step\s*\d+|\Z)'
                    step_matches = re.findall(step_pattern, error_text, re.DOTALL | re.IGNORECASE)
                    for step_num, error_desc in step_matches:
                        if error_desc.strip():
                            mistakes.append({
                                "step": step_num,
                                "status": "Error",
                                "desc": error_desc.strip()[:100]
                            })
            
            # Extract corrected solution
            corrected_steps = []
            if '### Corrected Solution' in section:
                correct_sections = re.split(r'### Corrected Solution:', section, flags=re.IGNORECASE)
                if len(correct_sections) > 1:
                    correct_text = correct_sections[1].split('**Final Answer:**')[0] if '**Final Answer:**' in correct_sections[1] else correct_sections[1]
                    # Extract steps
                    step_matches = re.findall(r'Step\s*\d+[:\s]+(.*?)(?=Step\s*\d+|\Z)', correct_text, re.DOTALL | re.IGNORECASE)
                    if step_matches:
                        corrected_steps = [match.strip() for match in step_matches[:8]]
            
            # Final answer
            final_answer = ""
            boxed_match = re.search(r'\\boxed{(.*?)}', section)
            if boxed_match:
                final_answer = f"$$\\boxed{{{boxed_match.group(1)}}}$$"
            
            questions.append({
                "id": question_id,
                "questionText": question_text[:400],
                "steps": student_solution,
                "mistakes": mistakes,
                "hasErrors": len(mistakes) > 0,
                "correctedSteps": corrected_steps or ["Complete solution will be shown"],
                "finalAnswer": final_answer or ""
            })
            
        except Exception as e:
            logger.error(f"Error parsing question {i}: {e}")
            questions.append({
                "id": f"Q{i}",
                "questionText": f"Question {i}",
                "steps": ["Processing student work..."],
                "mistakes": [],
                "hasErrors": False,
                "correctedSteps": ["Analysis in progress"],
                "finalAnswer": ""
            })
    
    return {"questions": questions}

@app.post("/analyze-feedback")
async def analyze_feedback(request: dict):
    """Handle user feedback for specific questions and provide updated analysis."""
    try:
        question = request.get("question", {})
        feedback = request.get("feedback", "")
        original_analysis = request.get("original_analysis", "")
        
        if not question or not feedback:
            return JSONResponse({
                "success": False,
                "error": "Missing question or feedback data"
            })
        
        # Create prompt for feedback analysis
        feedback_prompt = f"""
        A user has provided feedback on the analysis of Question {question.get('id', 'Unknown')}:
        Original Question: {question.get('questionText', '')}
        User Feedback: {feedback}
        Please re-analyze this specific question considering the user's feedback.
        Focus on:
        1. Addressing the user's specific concerns
        2. Providing clearer mathematical explanations
        3. Ensuring all mathematical expressions are in proper MathJax/LaTeX format
        Provide the updated analysis for this question only.
        """
        
        response = model.generate_content(feedback_prompt)
        updated_analysis = response.text
        
        # Parse the updated analysis to extract the question data
        updated_question = parse_single_question(updated_analysis, question.get('id', f"Q{len(question)}"))
        
        return JSONResponse({
            "success": True,
            "updated_question": updated_question,
            "message": "Analysis updated successfully"
        })
    
    except Exception as e:
        logger.error(f"Feedback analysis failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Feedback analysis failed: {str(e)}"
        }, status_code=500)

def parse_single_question(analysis_text, question_id):
    """Parse a single question from analysis text."""
    return {
        "id": question_id,
        "questionText": extract_question_text(analysis_text),
        "steps": extract_steps(analysis_text),
        "mistakes": extract_mistakes(analysis_text),
        "hasErrors": True,
        "correctedSteps": extract_corrected_steps(analysis_text),
        "finalAnswer": extract_final_answer(analysis_text)
    }

def extract_question_text(text):
    match = re.search(r'Original Question:\s*(.*?)(?=User Feedback|$)', text, re.DOTALL)
    return match.group(1).strip() if match else "Question text not available"

def extract_steps(text):
    return ["Step analysis in progress"]

def extract_mistakes(text):
    return [{
        "step": 1,
        "status": "Error",
        "desc": "Re-analyzed based on user feedback"
    }]

def extract_corrected_steps(text):
    return ["Corrected solution based on user feedback"]

def extract_final_answer(text):
    match = re.search(r'\\boxed{(.*?)}', text)
    return f"$$\\boxed{{{match.group(1)}}}$$" if match else "Final answer pending"

@app.post("/create-practice-paper")
async def create_practice_paper(request: dict):
    """Create practice paper based on ALL mistakes - FIXED TO INCLUDE ALL ERRORS, NO FILTERING."""
    try:
        detailed_data = request.get("detailed_data", {})
        questions_with_errors = []
        
        # Include ALL questions with ANY errors (no genuine filter - pass down completely)
        for q in detailed_data.get("questions", []):
            if q.get('hasErrors', False) and q.get('mistakes'):
                questions_with_errors.append(q)
        
        logger.info(f"Found {len(questions_with_errors)} questions with errors for practice paper")
        
        if not questions_with_errors:
            return JSONResponse({
                "success": False,
                "error": "No questions with errors found. Your solutions appear to be correct!"
            })
        
        # FIXED PRACTICE PAPER PROMPT - Preserves exact question numbers, redesign ALL
        practice_prompt = f"""Create a targeted practice paper with EXACTLY {len(questions_with_errors)} redesigned questions.
**CRITICAL REQUIREMENTS:**
1. For EACH original question, create ONE modified practice question - redesign ALL provided.
2. **PRESERVE THE EXACT QUESTION NUMBER/LABEL from the original** (e.g., if original is "1(a)", use "1(a)" in the output)
3. Focus on the SAME concepts where errors occurred
4. ALL math expressions MUST be in LaTeX/MathJax format ($...$ or $$...$$) for proper rendering.
5. Output ONLY the questions in the specified format below - NO additional text, tables, or commentary. Ensure every question is redesigned.
**QUESTIONS TO REDESIGN (ALL MUST BE INCLUDED):**
{format_questions_for_practice_prompt(questions_with_errors)}
**OUTPUT FORMAT - USE THIS EXACTLY FOR EACH QUESTION:**
### Based on Question [EXACT_QUESTION_NUMBER]
**Original Question:**
[Copy the exact original question in MathJax]
**Modified Question:**
[Modified version testing SAME concepts with different values in MathJax]
---
**EXAMPLE FORMAT:**
If original is Question 1(a), your output must be:
### Based on Question 1(a)
**Original Question:**
Evaluate $\int x^9 dx$
**Modified Question:**
Evaluate $\int x^7 dx$
---
**IMPORTANT:**
- Use the EXACT question number from the original (1(a), 2(b), 3, etc.)
- NO extra text - just "Based on Question"
- Each question must be separated by ---
- Focus on same mathematical concepts with different coefficients/values - redesign EVERY one provided"""
        
        response = model.generate_content(practice_prompt)
        practice_paper = response.text
        
        logger.info(f"Successfully generated practice paper with {len(questions_with_errors)} questions")
        
        return JSONResponse({
            "success": True,
            "practice_paper": practice_paper,
            "questions_used": len(questions_with_errors),
            "message": f"Practice paper created targeting {len(questions_with_errors)} error areas"
        })
    
    except Exception as e:
        logger.error(f"Practice paper creation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Practice paper creation failed: {str(e)}"
        }, status_code=500)

def format_questions_for_practice_prompt(questions_with_errors):
    """Format questions with their errors for the practice paper prompt."""
    formatted = ""
    for q in questions_with_errors:
        formatted += f"\n**Question {q['id']}:** {q['questionText'][:200]}...\n"
        formatted += f"**Errors Found:** {', '.join([m.get('desc', '')[:100] for m in q.get('mistakes', [])])}\n"
    return formatted

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

