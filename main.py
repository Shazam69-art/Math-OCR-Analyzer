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

# Mount static files
app.mount("/static", StaticFiles(directory="."), name="static")

# PDFKit setup
def setup_pdfkit():
    """Setup pdfkit configuration."""
    try:
        possible_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "wkhtmltopdf.exe"
        ]
        wkhtmltopdf_path = None
        for path in possible_paths:
            if os.path.exists(path):
                wkhtmltopdf_path = path
                break
        if wkhtmltopdf_path:
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            logger.info(f"Using wkhtmltopdf at: {wkhtmltopdf_path}")
            return config
        else:
            try:
                import subprocess
                subprocess.run(["wkhtmltopdf", "--version"], capture_output=True, check=True)
                config = pdfkit.configuration()
                logger.info("Using wkhtmltopdf from PATH")
                return config
            except:
                logger.warning("wkhtmltopdf not found. PDF generation will be disabled.")
                return None
    except Exception as e:
        logger.warning(f"Could not configure pdfkit: {e}")
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
    """Main analysis endpoint using Gemini with IMPROVED OUTPUT FORMAT."""
    try:
        logger.info(f"Analysis request - Message: {message[:100]}, Files: {len(files)}")
        # ENHANCED SYSTEM PROMPT WITH CLEANER OUTPUT FORMAT - UPDATED FOR SHORT ERROR ANALYSIS AND EXACT COPY
        system_prompt = """You are a **PhD-Level Math Teacher** analyzing student work.
**CRITICAL INSTRUCTIONS FOR OUTPUT:**
1. **ALL MATHEMATICAL EXPRESSIONS MUST BE IN LATEX/MATHJAX FORMAT** - Use $...$ for inline math and $$...$$ for display math. Ensure 100% proper LaTeX for rendering.
2. **PRESERVE STUDENT'S ORIGINAL SOLUTION EXACTLY (100% COPY-PASTE)** - Copy verbatim what the student wrote from the images/files. Do not modify, interpret, or regenerate any part. If text is unclear, copy as visible.
3. **IGNORE STRIKETHROUGH TEXT COMPLETELY** - Strikethrough indicates the student marked it as wrong; do not include it in the student's solution at all.
4. **SEPARATE EACH QUESTION CLEARLY** - Each labeled question gets its OWN analysis section.
5. **ERROR ANALYSIS MUST BE VERY SHORT: ONE-LINER PER ERROR ONLY** - List only the specific errors (e.g., "Step 2: Incorrect application of power rule"). NO corrections, explanations, or breakdowns here. Keep to 1 sentence max per error.
6. **MARK QUESTIONS AS CORRECT** if student's final answer matches the correct answer, even if steps differ.
7. **ONLY MARK ERRORS** when final answer differs significantly or when genuine mathematical mistakes exist.
8. **DO NOT WRITE YOUR OWN ANSWERS IN STUDENT SOLUTION** - Only copy what the student actually submitted as final (ignoring strikethrough).
**OUTPUT FORMAT - FOLLOW EXACTLY:**
## Question [EXACT LABEL]:
**Full Question:** [Copy EXACT question text in MathJax format]
### Student's Solution – Exact Copy:
**Step 1:** [Copy line 1 EXACTLY as written in MathJax - 100% verbatim from image]
**Step 2:** [Copy line 2 EXACTLY as written in MathJax - 100% verbatim from image]
...
### Error Analysis:
**Step X Error:** [One-liner error description only, e.g., "Misapplied substitution rule."]
**Step Y Error:** [One-liner error description only.]
...
### Corrected Solution:
**Step 1:** [Mathematical setup with explanation in MathJax]
**Step 2:** [Detailed derivation in MathJax]
...
**Final Answer:** $$\\boxed{final_answer}$$
---
**PERFORMANCE TABLE (UPDATE BASED ON ACTUAL ERRORS FOUND)**
| Concept No. | Concept (With Explanation) | Example | Status |
|-------------|----------------------------|---------|--------|
| 1 | Basic Formulas | Standard Formula of Integration | **Performance:** Not Tested |
| 2 | Application of Formulae | \( \int x^9 dx = \frac{x^{10}}{10} + C\) | **Performance:** Not Tested |
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
**UPDATE TABLE BASED ON ACTUAL ANALYSIS:** For each concept tested, update status like: "Performance: Tested 2 Times - Perfect 2 (Q.1, Q.3)" or "Performance: Tested 1 Time - Mistakes 1 (Q.2)"
## Performance Insights
[Provide insights with mathematical references in MathJax where needed]"""
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
    """IMPROVED parsing of AI response with better structure and error detection."""
    questions = []
    if not response_text:
        return {"questions": questions}
    # IMPROVED QUESTION PARSING - SEPARATE EACH QUESTION CLEARLY
    question_sections = re.split(r'## Question\s+', response_text)
    # Remove empty sections and header
    question_sections = [section for section in question_sections if
                         section.strip() and not section.startswith('Questions found')]
    for i, section in enumerate(question_sections, 1):
        try:
            # Extract question ID - improved pattern matching
            question_id_match = re.search(r'^([A-Z]?[0-9]+[a-z]?(?:\([a-z]\))?[^:\n]*):?', section)
            if question_id_match:
                question_id = question_id_match.group(1).strip()
            else:
                # Try alternative patterns
                alt_match = re.search(r'^(Q?[0-9]+[a-z]?(?:\s*\([a-z]\))?)', section)
                question_id = alt_match.group(1).strip() if alt_match else f"Q{i}"
            # Extract question text - CLEANED TO REMOVE STUDENT SOLUTION CONTENT
            question_text = "Question content not extracted"
            if '**Full Question:**' in section:
                question_part = section.split('**Full Question:**')[1]
                if '###' in question_part:
                    question_text = question_part.split('###')[0].strip()
                else:
                    question_text = question_part.strip()
            # Clean question text from student solution content
            question_text = re.sub(r'### Student\'s Solution.*?###', '', question_text, flags=re.DOTALL).strip()
            # Extract student work - PRESERVE EXACTLY AS SUBMITTED
            steps = []
            if '### Student\'s Solution' in section:
                solution_part = section.split('### Student\'s Solution')[1]
                if '###' in solution_part:
                    solution_section = solution_part.split('###')[0]
                else:
                    solution_section = solution_part
                # Extract steps exactly as written - SIMPLE PARSING
                step_patterns = [
                    r'\*\*Step\s+\d+:\*\*\s*(.*?)(?=\*\*Step\s+\d+:|###|\*\*Analysis|\Z)',
                    r'Step\s+\d+:\s*(.*?)(?=Step\s+\d+:|###|\*\*Analysis|\Z)'
                ]
                for pattern in step_patterns:
                    step_matches = re.findall(pattern, solution_section, re.DOTALL | re.IGNORECASE)
                    if step_matches:
                        steps = [match.strip() for match in step_matches if match.strip()]
                        break
            if not steps:
                steps = ["No solution provided"]
            # SIMPLE ERROR DETECTION - NO COMPLEX BREAKDOWNS - UPDATED FOR ONE-LINERS ONLY
            mistakes = []
            has_errors = False
            # Look for error patterns with SIMPLE matching
            if '### Error Analysis' in section:
                error_part = section.split('### Error Analysis')[1]
                if '###' in error_part:
                    error_section = error_part.split('###')[0]
                else:
                    error_section = error_part
                # Simple error pattern matching - ONE-LINER ONLY, NO CORRECTION EXTRACTION
                error_patterns = [
                    r'\*\*Step\s*(\d+)\s*Error:\*\*\s*(.*?)(?=\*\*Step\s*\d+\s*Error:|\Z)',
                    r'Step\s*(\d+)\s*Error:\s*(.*?)(?=Step\s*\d+\s*Error:|\Z)'
                ]
                for pattern in error_patterns:
                    error_matches = re.findall(pattern, error_section, re.DOTALL | re.IGNORECASE)
                    for match in error_matches:
                        step_num, error_desc = match
                        if error_desc.strip():
                            has_errors = True
                            mistakes.append({
                                "step": step_num,
                                "status": "Error",
                                "desc": error_desc.strip()  # One-liner only, no correction here
                            })
            # Extract corrected solution
            corrected_steps = []
            if '### Corrected Solution' in section:
                correct_part = section.split('### Corrected Solution')[1]
                if '##' in correct_part:
                    correct_section = correct_part.split('##')[0]
                else:
                    correct_section = correct_part
                # Extract steps from corrected solution
                step_pattern = r'\*\*Step\s+\d+:\*\*\s*(.*?)(?=\*\*Step\s+\d+:|\*\*Final Answer|\Z)'
                step_matches = re.findall(step_pattern, correct_section, re.DOTALL)
                corrected_steps = [match.strip() for match in step_matches if match.strip()]
            # Extract final answer - PROPER MATHJAX FORMAT
            final_answer = ""
            final_match = re.search(r'\\boxed{(.*?)}', section)
            if final_match:
                final_answer = f"$$\\boxed{{{final_match.group(1)}}}$$"
            elif '**Final Answer:**' in section:
                answer_part = section.split('**Final Answer:**')[1]
                if '\\boxed' in answer_part:
                    boxed_match = re.search(r'\\boxed{(.*?)}', answer_part)
                    final_answer = f"$$\\boxed{{{boxed_match.group(1)}}}$$" if boxed_match else ""
                else:
                    final_answer_text = answer_part.split('\n')[0].strip()
                    final_answer = f"$${final_answer_text}$$" if final_answer_text else ""
            questions.append({
                "id": question_id,
                "questionText": question_text[:500] + "..." if len(question_text) > 500 else question_text,
                "steps": steps,
                "mistakes": mistakes,
                "hasErrors": has_errors,
                "correctedSteps": corrected_steps or ["Complete solution will be shown after analysis"],
                "finalAnswer": final_answer or "Answer will be determined after analysis"
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
Evaluate $\\int x^9 dx$
**Modified Question:**
Evaluate $\\int x^7 dx$
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


def format_math_for_pdf(text):
    """Format mathematical content for PDF - PROPER LATEX TO UNICODE CONVERSION."""
    if not text:
        return ""

    formatted = text

    # Convert line breaks
    formatted = formatted.replace('\n', '<br>')

    # Basic formatting for bold text
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)

    # Remove math delimiters first
    formatted = formatted.replace('$$', '').replace('$', '')
    formatted = formatted.replace('\\[', '').replace('\\]', '')
    formatted = formatted.replace('\\(', '').replace('\\)', '')

    # FIXED: Handle the specific pattern that's causing issues
    # Convert \int to proper integral symbol and fix function names
    formatted = formatted.replace('\\int', '∫')
    formatted = formatted.replace('\\tan', 'tan')
    formatted = formatted.replace('\\sin', 'sin')
    formatted = formatted.replace('\\cos', 'cos')
    formatted = formatted.replace('\\cot', 'cot')
    formatted = formatted.replace('\\sec', 'sec')
    formatted = formatted.replace('\\csc', 'csc')

    # FIXED: Handle inverse trigonometric functions properly
    formatted = formatted.replace('\\cos^{-1}', 'cos⁻¹')
    formatted = formatted.replace('\\sin^{-1}', 'sin⁻¹')
    formatted = formatted.replace('\\tan^{-1}', 'tan⁻¹')

    # FIXED: Handle fractions properly
    formatted = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'<sup>\1</sup>⁄<sub>\2</sub>', formatted)

    # FIXED: Handle square roots properly
    formatted = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', formatted)

    # FIXED: Handle exponents properly
    formatted = re.sub(r'\^\{([^}]+)\}', r'<sup>\1</sup>', formatted)
    formatted = re.sub(r'\^([0-9]+)', r'<sup>\1</sup>', formatted)  # Handle simple exponents like x^2

    # FIXED: Handle subscripts properly
    formatted = re.sub(r'_\{([^}]+)\}', r'<sub>\1</sub>', formatted)

    # FIXED: Remove remaining backslashes from common functions
    formatted = re.sub(r'\\([a-zA-Z]+)', r'\1', formatted)

    # FIXED: Clean up braces
    formatted = re.sub(r'\{([^}]+)\}', r'\1', formatted)

    # FIXED: Remove specific problematic patterns
    formatted = formatted.replace('textEvaluate', 'Evaluate')
    formatted = formatted.replace('\(f\)', '')  # Remove the (f) artifact

    # FIXED: Clean up any remaining LaTeX artifacts
    formatted = re.sub(r'\\,', ' ', formatted)
    formatted = re.sub(r'\\ ', ' ', formatted)

    # FIXED: Wrap in proper math styling with better CSS
    formatted = f'<div style="font-family: \'Cambria Math\', \'Times New Roman\', serif; font-size: 14px; line-height: 1.6; text-align: center;">{formatted}</div>'

    return formatted


def parse_performance_table_for_pdf(table_text):
    """Parse performance table for PDF rendering."""
    rows = table_text.split('\n')
    table_html = '<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 12px;">'
    # Add header
    table_html += '<thead><tr style="background: #34495e; color: white;">'
    header_cells = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
    for cell in header_cells:
        table_html += f'<th style="padding: 12px; border: 1px solid #7f8c8d; text-align: left;">{format_math_for_pdf(cell)}</th>'
    table_html += '</tr></thead><tbody>'
    # Add rows
    for row in rows[2:]:
        if not row.strip() or not row.strip().startswith('|'):
            continue
        cells = [cell.strip() for cell in row.split('|') if cell.strip()]
        if len(cells) >= 4:
            table_html += '<tr>'
            for i, cell in enumerate(cells):
                cell_content = format_math_for_pdf(cell)
                if i == 3: # Status column
                    status_class = get_status_class_for_pdf(cell)
                    table_html += f'<td style="padding: 12px; border: 1px solid #7f8c8d;"><span class="{status_class}">{cell_content}</span></td>'
                else:
                    table_html += f'<td style="padding: 12px; border: 1px solid #7f8c8d;">{cell_content}</td>'
            table_html += '</tr>'
    table_html += '</tbody></table>'
    return table_html

def get_status_class_for_pdf(status_text):
    """Get CSS class for status in PDF."""
    text = status_text.lower()
    if 'perfect' in text or '100%' in text or 'excellent' in text:
        return 'status-perfect'
    elif 'mistake' in text or 'error' in text or 'wrong' in text:
        return 'status-error'
    elif 'partial' in text or '50%' in text or 'needs improvement' in text:
        return 'status-partial'
    elif 'not tested' in text:
        return 'status-not-tested'
    return ''

@app.post("/generate-performance-pdf")
async def generate_performance_pdf(request: Request):
    """Generate PDF for performance report - SIMPLIFIED without external dependencies."""
    try:
        data = await request.form()
        analysis_json = data.get("analysis_data", "{}")
        analysis_data = json.loads(analysis_json)
        analysis_text = analysis_data.get('analysis', '')
        if not pdfkit_config:
            return JSONResponse({
                "success": False,
                "error": "PDF generation not configured. Please install wkhtmltopdf."
            })
        # Extract table and insights
        table_match = re.search(r'\| Concept No\. \| Concept.*?Performance Insights', analysis_text, re.DOTALL)
        table_html = '<p>Performance data not available</p>'
        if table_match:
            table_text = table_match.group(0)
            table_html = parse_performance_table_for_pdf(table_text)
        insights_match = re.search(r'## Performance Insights[\s\S]*$', analysis_text)
        insights_html = '<p>Performance insights not available</p>'
        if insights_match:
            insights_text = insights_match.group(0).replace('## Performance Insights', '').strip()
            insights_html = f'''
            <div style="page-break-before: always; margin-top: 40px;">
                <h2 style="color: #2c3e50; padding-bottom: 10px; border-bottom: 2px solid #3498db;">Performance Insights</h2>
                <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3498db;">
                    <div style="font-size: 14px; line-height: 1.6;">{format_math_for_pdf(insights_text)}</div>
                </div>
            </div>
            '''
        # SIMPLIFIED HTML template without external dependencies
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Math Performance Report</title>
    <style>
        body {
            font-family: "Times New Roman", Times, serif;
            margin: 20px;
            line-height: 1.6;
            font-size: 14px;
            color: #2c3e50;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }
        h2 {
            color: #2c3e50;
            margin-top: 30px;
            padding-bottom: 8px;
            border-bottom: 2px solid #bdc3c7;
        }
        .status-error {
            background: #ffebee;
            color: #c62828;
            padding: 6px 10px;
            border-radius: 4px;
            font-weight: bold;
            border: 1px solid #ef5350;
        }
        .status-perfect {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 6px 10px;
            border-radius: 4px;
            font-weight: bold;
            border: 1px solid #4caf50;
        }
        .status-partial {
            background: #fff3e0;
            color: #ef6c00;
            padding: 6px 10px;
            border-radius: 4px;
            font-weight: bold;
            border: 1px solid #ff9800;
        }
        .status-not-tested {
            background: #f5f5f5;
            color: #757575;
            padding: 6px 10px;
            border-radius: 4px;
            font-weight: bold;
            border: 1px solid #bdbdbd;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 12px;
            padding-top: 15px;
            border-top: 1px solid #bdc3c7;
        }
        .report-info {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 15px;
            border-left: 4px solid #3498db;
        }
        .math-expression {
            font-family: "Cambria Math", "Times New Roman", serif;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>Math Performance Analysis Report</h1>
    <div class="report-info">
        <p><strong>Generated:</strong> {{ timestamp }}</p>
    </div>
    <h2>Concept Performance Analysis</h2>
    {{ performance_table }}
    {{ performance_insights }}
    <div class="footer">
        <p>Generated by Math Analyzer • Comprehensive Learning Assessment</p>
    </div>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            performance_table=table_html,
            performance_insights=insights_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        # SIMPLIFIED PDF options - no JavaScript
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
            'disable-javascript': '', # Disable JavaScript to avoid network issues
            'no-stop-slow-scripts': ''
        }
        pdfkit.from_string(html_content, output_path, configuration=pdfkit_config, options=pdf_options)
        # Return the file
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename='Math_Performance_Report.pdf'
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"PDF generation failed: {str(e)}"
        }, status_code=500)

@app.post("/generate-detailed-pdf")
async def generate_detailed_pdf(request: Request):
    """Generate PDF for detailed analysis report - SIMPLIFIED without external dependencies."""
    try:
        data = await request.form()
        analysis_json = data.get("analysis_data", "{}")
        analysis_data = json.loads(analysis_json)
        detailed_data = analysis_data.get('detailed_data', {})
        if not pdfkit_config:
            return JSONResponse({
                "success": False,
                "error": "PDF generation not configured. Please install wkhtmltopdf."
            })
        # Generate HTML for detailed analysis
        detailed_html = generate_detailed_analysis_html(detailed_data)
        # SIMPLIFIED HTML template
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Detailed Analysis Report</title>
    <style>
        body {
            font-family: "Times New Roman", Times, serif;
            margin: 15px;
            line-height: 1.6;
            font-size: 13px;
            color: #2c3e50;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 12px;
        }
        .question-analysis {
            margin: 20px 0;
            border: 1px solid #bdc3c7;
            border-radius: 8px;
            padding: 0;
            overflow: hidden;
            background: white;
        }
        .question-header {
            background: #34495e;
            color: white;
            padding: 15px;
            font-weight: bold;
        }
        .analysis-section {
            padding: 15px;
            border-bottom: 1px solid #ecf0f1;
        }
        .analysis-section:last-child {
            border-bottom: none;
        }
        .step-item {
            background: #f8f9fa;
            padding: 12px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }
        .error-item {
            background: #ffebee;
            border-left: 4px solid #e74c3c;
            color: #c62828;
        }
        .correct-item {
            background: #e8f5e9;
            border-left: 4px solid #2e7d32;
            color: #1b5e20;
        }
        .math-expression {
            font-family: "Cambria Math", "Times New Roman", serif;
            font-style: italic;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #7f8c8d;
            font-size: 11px;
            padding-top: 12px;
            border-top: 1px solid #bdc3c7;
        }
        .report-info {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 15px;
            border-left: 4px solid #3498db;
        }
    </style>
</head>
<body>
    <h1>Detailed Analysis Report</h1>
    <div class="report-info">
        <p><strong>Generated:</strong> {{ timestamp }}</p>
    </div>
    {{ detailed_content }}
    <div class="footer">
        <p>Generated by Math Analyzer • Question-by-Question Analysis</p>
    </div>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            detailed_content=detailed_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        # SIMPLIFIED PDF options
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
            'disable-javascript': '',
            'no-stop-slow-scripts': ''
        }
        pdfkit.from_string(html_content, output_path, configuration=pdfkit_config, options=pdf_options)
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename='Detailed_Analysis_Report.pdf'
        )
    except Exception as e:
        logger.error(f"Detailed PDF generation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Detailed PDF generation failed: {str(e)}"
        }, status_code=500)

def generate_detailed_analysis_html(detailed_data):
    """Generate HTML for detailed analysis content - UPDATED FOR SHORT ERRORS."""
    html = ""
    for q in detailed_data.get('questions', []):
        has_errors = q.get('hasErrors', False)
        html += f"""
        <div class="question-analysis">
            <div class="question-header">
                {q['id']} - Question Analysis {'🔴 Errors Found' if has_errors else '🟢 No Major Errors'}
            </div>
            <div class="analysis-section">
                <h3>📝 Question:</h3>
                <div class="step-item math-expression">{format_math_for_pdf(q.get('questionText', 'No question text'))}</div>
            </div>
            <div class="analysis-section">
                <h3>✍️ Student's Solution:</h3>
        """
        for i, step in enumerate(q.get('steps', [])):
            html += f'<div class="step-item math-expression"><strong>Step {i + 1}:</strong><br>{format_math_for_pdf(step)}</div>'
        html += """
            </div>
            <div class="analysis-section">
                <h3>🔍 Error Analysis:</h3>
        """
        if has_errors and q.get('mistakes'):
            for mistake in q['mistakes']:
                html += f"""
                <div class="step-item error-item">
                    <strong>Step {mistake.get('step', 'N/A')}:</strong><br>
                    <div class="math-expression">{format_math_for_pdf(mistake.get('desc', 'No description'))}</div>
                </div>
                """
        else:
            html += '<div class="step-item correct-item"><strong>✓ No Conceptual Errors Found</strong><br><em>Solution appears mathematically correct</em></div>'
        html += """
            </div>
            <div class="analysis-section">
                <h3>✅ Correct Solution:</h3>
        """
        for i, step in enumerate(q.get('correctedSteps', [])):
            html += f'<div class="step-item correct-item math-expression"><strong>Step {i + 1}:</strong><br>{format_math_for_pdf(step)}</div>'
        html += """
            </div>
        </div>
        """
    return html

@app.post("/generate-practice-pdf")
async def generate_practice_pdf(request: Request):
    """Generate PDF for practice paper - FIXED PARSING FOR 'Based on Question' AND FULL CONTENT DISPLAY."""
    try:
        data = await request.form()
        practice_json = data.get("practice_paper", "{}")
        practice_data = json.loads(practice_json)
        practice_content = practice_data.get('content', '')
        if not pdfkit_config:
            return JSONResponse({
                "success": False,
                "error": "PDF generation not configured. Please install wkhtmltopdf."
            })
        # FIXED Parse practice content - Split on '### Based on Question '
        practice_html = """
        <div style="text-align: center; margin-bottom: 25px;">
            <h1 style="color: #2c3e50; border-bottom: 3px solid #2c3e50; padding-bottom: 12px;">
                Practice Paper Based on Your Conceptual Errors
            </h1>
        </div>
        <div style="margin: 20px 0;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; background: white;">
                <thead>
                    <tr style="background: #2c3e50; color: white;">
                        <th style="padding: 15px; text-align: center; font-weight: bold; border-bottom: 2px solid #3498db; width: 15%;">
                            Q.No.
                        </th>
                        <th style="padding: 15px; text-align: center; font-weight: bold; border-bottom: 2px solid #3498db; width: 42.5%;">
                            Original Question
                        </th>
                        <th style="padding: 15px; text-align: center; font-weight: bold; border-bottom: 2px solid #3498db; width: 42.5%;">
                            Redesigned Question
                        </th>
                    </tr>
                </thead>
                <tbody>
        """
        # FIXED: Split on correct pattern '### Based on Question ' and improve extraction (trim extras)
        question_blocks = re.split(r'### Based on Question ', practice_content)[1:]  # Skip initial part
        unmatched_count = 0
        for block in question_blocks:
            # Extract question number from header (first line)
            question_match = re.match(r'([^\n]+)', block)
            if question_match:
                question_number = re.sub(r'[\*\s]+', '', question_match.group(1).strip())  # Clean bold/spaces
                block_after_header = block.split('\n', 1)[1] if '\n' in block else block
                # IMPROVED: Extract original - trim bold and leading/trailing
                original_match = re.search(r'\*\*Original Question:\*\*\s*(.*?)(?=\*\*Modified Question:|\-{3,}|---|\Z)', block_after_header, re.DOTALL | re.IGNORECASE)
                original_question = re.sub(r'[\*\s]+', '', original_match.group(1).strip()) if original_match else "Not available"
                # Extract modified
                modified_match = re.search(r'\*\*Modified Question:\*\*\s*(.*?)(?=\-{3,}|---|\Z)', block_after_header, re.DOTALL | re.IGNORECASE)
                modified_question = re.sub(r'[\*\s]+', '', modified_match.group(1).strip()) if modified_match else "Not available"
                if original_question == "Not available" or modified_question == "Not available":
                    unmatched_count += 1
                    logger.warning(f"Unmatched content in block for {question_number}")
                practice_html += f"""
                    <tr>
                        <td style="padding: 20px; border-bottom: 1px solid #e9ecef; vertical-align: middle; text-align: center; font-weight: bold; color: #2c3e50; background: #e3f2fd;">
                            {question_number}
                        </td>
                        <td style="padding: 20px; border-bottom: 1px solid #e9ecef; vertical-align: top; text-align: center; background: #f8fafc; border-right: 1px dashed #bdc3c7;">
                            <div style="font-family: 'Cambria Math', 'Times New Roman', serif; font-size: 13px; text-align: center; padding: 15px; background: white; border-radius: 5px; border: 1px solid #e9ecef;">
                                {format_math_for_pdf(original_question)}
                            </div>
                        </td>
                        <td style="padding: 20px; border-bottom: 1px solid #e9ecef; vertical-align: top; text-align: center; background: #f0fff4;">
                            <div style="font-family: 'Cambria Math', 'Times New Roman', serif; font-size: 13px; text-align: center; padding: 15px; background: white; border-radius: 5px; border: 1px solid #e9ecef;">
                                {format_math_for_pdf(modified_question)}
                            </div>
                        </td>
                    </tr>
                """
        if unmatched_count > 0:
            logger.warning(f"{unmatched_count} blocks had parsing issues - check LLM output format")
        practice_html += """
                </tbody>
            </table>
        </div>
        """
        # SIMPLIFIED HTML template
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Targeted Practice Paper</title>
 <style>
    body {
        font-family: "Times New Roman", Times, serif;
        margin: 20px;
        line-height: 1.6;
        font-size: 13px;
        color: #2c3e50;
    }
    .footer {
        text-align: center;
        margin-top: 30px;
        color: #7f8c8d;
        font-size: 11px;
        padding-top: 12px;
        border-top: 1px solid #bdc3c7;
    }
    table tr:nth-child(even) {
        background: #f8f9fa;
    }
    .math-expression {
        font-family: "Cambria Math", "Times New Roman", serif;
        font-size: 14px;
        line-height: 1.8;
        text-align: center;
    }
    sup {
        font-size: 0.8em;
        vertical-align: super;
        line-height: 0;
    }
    sub {
        font-size: 0.8em;
        vertical-align: sub;
        line-height: 0;
    }
</style>
</head>
<body>
    {{ practice_content }}
    <div class="footer">
        <p>Generated by Math Analyzer • {{ timestamp }}</p>
    </div>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            practice_content=practice_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        # SIMPLIFIED PDF options
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
            'disable-javascript': '',
            'no-stop-slow-scripts': ''
        }
        pdfkit.from_string(html_content, output_path, configuration=pdfkit_config, options=pdf_options)
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename='Practice_Paper_Based_on_Conceptual_Errors.pdf'
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"PDF generation failed: {str(e)}"
        }, status_code=500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

