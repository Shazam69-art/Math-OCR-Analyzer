import os
import base64
import io
import json
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
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
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def pdf_all_pages_to_png_b64(pdf_bytes: bytes, dpi: int = 150) -> list:
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
    try:
        logger.info(f"Analysis request - Message: {message[:100]}, Files: {len(files)}")
        system_prompt = """You are a **PhD-Level Math Teacher** analyzing student work.
**CRITICAL INSTRUCTIONS FOR OUTPUT:**
1. **ALL MATHEMATICAL EXPRESSIONS MUST USE KATEX-COMPATIBLE LATEX DELIMITERS**:
   - Use `$...$` for inline math (e.g., `$\\int x^2 dx$`).
   - Use `$$...$$` for display math (e.g., `$$\\frac{dx}{dy}$$`).
2. **PRESERVE STUDENT'S ORIGINAL SOLUTION EXACTLY** - do not modify or regenerate.
3. **ERROR ANALYSIS MUST BE SIMPLE AND PRECISE** - only highlight specific mistakes.
4. **FINAL ANSWERS MUST BE IN PLAIN TEXT** (no LaTeX).
**OUTPUT FORMAT (STRICTLY FOLLOW):**
## Question [ID]:
**Full Question:** [LaTeX-wrapped question]
### Student's Solution (Exact Copy):
**Step 1:** `$...$` or `$$...$$`
**Step 2:** `$...$` or `$$...$$`
...
### Error Analysis:
**Step X Error:** [Brief description in LaTeX delimiters]
### Corrected Solution:
**Step 1:** `$...$` or `$$...$$`
**Final Answer:** [Plain text]
---
**PERFORMANCE TABLE (UPDATE BASED ON ACTUAL ERRORS FOUND)**
| Concept No. | Concept (With Explanation) | Example | Status |
|-------------|----------------------------|---------|--------|
| 1 | Basic Formulas | Standard Formula of Integration | **Performance:** Not Tested |
| 2 | Application of Formulae | $\\int x^9 dx = \\frac{x^{10}}{10} + C$ | **Performance:** Not Tested |
...
**UPDATE TABLE BASED ON ACTUAL ANALYSIS:** For each concept tested, update status like: "Performance: Tested 2 Times - Perfect 2 (Q.1, Q.3)" or "Performance: Tested 1 Time - Mistakes 1 (Q.2)"
## Performance Insights
[Provide insights with mathematical references in LaTeX where needed]"""
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
        contents = [system_prompt]
        if message:
            contents.append(f"User request: {message}")
        contents.extend(file_contents)
        response = model.generate_content(contents)
        ai_response = response.text
        detailed_data = parse_detailed_data_strict(ai_response)
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

def parse_detailed_data_strict(response_text):
    questions = []
    if not response_text:
        return {"questions": questions}
    question_sections = re.split(r'## Question\s+', response_text)
    question_sections = [section for section in question_sections if section.strip() and not section.startswith('Questions found')]
    for i, section in enumerate(question_sections, 1):
        try:
            question_id_match = re.search(r'^([A-Z]?[0-9]+[a-z]?(?:\([a-z]\))?[^:\n]*):?', section)
            if question_id_match:
                question_id = question_id_match.group(1).strip()
            else:
                question_id = f"Q{i}"
            question_text = "Question content not extracted"
            if '**Full Question:**' in section:
                question_part = section.split('**Full Question:**')[1]
                if '###' in question_part:
                    question_text = question_part.split('###')[0].strip()
                else:
                    question_text = question_part.strip()
            question_text = re.sub(r'### Student\'s Solution.*?###', '', question_text, flags=re.DOTALL).strip()
            steps = []
            if '### Student\'s Solution' in section:
                solution_part = section.split('### Student\'s Solution')[1]
                if '###' in solution_part:
                    solution_section = solution_part.split('###')[0]
                else:
                    solution_section = solution_part
                step_pattern = r'\*\*Step\s+\d+:\*\*\s*(.*?)(?=\*\*Step\s+\d+:|###|\*\*Analysis|\Z)'
                step_matches = re.findall(step_pattern, solution_section, re.DOTALL)
                steps = [match.strip() for match in step_matches if match.strip()]
            if not steps:
                steps = ["No solution provided"]
            mistakes = []
            has_errors = False
            if '### Error Analysis' in section:
                error_part = section.split('### Error Analysis')[1]
                if '###' in error_part:
                    error_section = error_part.split('###')[0]
                else:
                    error_section = error_part
                error_pattern = r'\*\*Step\s*(\d+)\s*Error:\*\*\s*(.*?)(?=\*\*Step\s*\d+\s*Error:|\*\*Correction:|\Z)'
                error_matches = re.findall(error_pattern, error_section, re.DOTALL | re.IGNORECASE)
                for match in error_matches:
                    step_num, error_desc = match
                    if error_desc.strip():
                        has_errors = True
                        mistakes.append({
                            "step": step_num,
                            "status": "Error",
                            "desc": error_desc.strip(),
                            "correction": ""
                        })
            corrected_steps = []
            if '### Corrected Solution' in section:
                correct_part = section.split('### Corrected Solution')[1]
                if '##' in correct_part:
                    correct_section = correct_part.split('##')[0]
                else:
                    correct_section = correct_part
                step_pattern = r'\*\*Step\s+\d+:\*\*\s*(.*?)(?=\*\*Step\s+\d+:|\*\*Final Answer|\Z)'
                step_matches = re.findall(step_pattern, correct_section, re.DOTALL)
                corrected_steps = [match.strip() for match in step_matches if match.strip()]
            final_answer = ""
            if '**Final Answer:**' in section:
                answer_part = section.split('**Final Answer:**')[1]
                final_answer_text = re.sub(r'\$.*?\$', '', answer_part.split('\n')[0].strip())
                final_answer = re.sub(r'\\boxed{.*?}', '', final_answer_text).strip()
            if not final_answer:
                final_match = re.search(r'\\boxed{(.*?)}', section)
                if final_match:
                    final_answer = final_match.group(1).strip()
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
    try:
        question = request.get("question", {})
        feedback = request.get("feedback", "")
        original_analysis = request.get("original_analysis", "")
        if not question or not feedback:
            return JSONResponse({
                "success": False,
                "error": "Missing question or feedback data"
            })
        feedback_prompt = f"""
        A user has provided feedback on the analysis of Question {question.get('id', 'Unknown')}:
        Original Question: {question.get('questionText', '')}
        User Feedback: {feedback}
        Please re-analyze this specific question considering the user's feedback.
        Focus on:
        1. Addressing the user's specific concerns
        2. Providing clearer mathematical explanations
        3. Ensuring all mathematical expressions are in proper LaTeX format compatible with KaTeX
        4. Maintaining the structured format for the analysis
        5. Final answers must be in plain text without LaTeX
        Provide the updated analysis for this question only.
        """
        response = model.generate_content(feedback_prompt)
        updated_analysis = response.text
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
        "desc": "Re-analyzed based on user feedback",
        "correction": ""
    }]

def extract_corrected_steps(text):
    return ["Corrected solution based on user feedback"]

def extract_final_answer(text):
    match = re.search(r'Final Answer:\s*([^\n$]+)', text)
    return match.group(1).strip() if match else "Final answer pending"

@app.post("/create-practice-paper")
async def create_practice_paper(request: dict):
    try:
        detailed_data = request.get("detailed_data", {})
        questions_with_genuine_errors = []
        for q in detailed_data.get("questions", []):
            if not q.get('hasErrors', False) or not q.get('mistakes'):
                continue
            has_genuine_errors = False
            for mistake in q.get('mistakes', []):
                desc = (mistake.get('desc', '') + mistake.get('error', '')).lower()
                if any(keyword in desc for keyword in ['concept', 'method', 'approach', 'incorrect', 'wrong', 'error']):
                    if not any(minor_keyword in desc for minor_keyword in ['minor', 'formatting', 'presentation', 'typo']):
                        has_genuine_errors = True
                        break
            if has_genuine_errors:
                questions_with_genuine_errors.append(q)
        logger.info(f"Found {len(questions_with_genuine_errors)} questions with genuine errors for practice paper")
        if not questions_with_genuine_errors:
            return JSONResponse({
                "success": False,
                "error": "No questions with genuine conceptual errors found. Your solutions appear to be correct!"
            })
        practice_prompt = f"""Create a targeted practice paper with EXACTLY {len(questions_with_genuine_errors)} redesigned questions.
**CRITICAL REQUIREMENTS:**
1. For EACH original question with genuine errors, create ONE modified practice question
2. Show BOTH the original question (with original question number) AND the modified version
3. Keep the SAME question numbering as the original
4. DO NOT include any solutions, answers, or motivational text
5. Make the modified questions test the SAME concepts but with DIFFERENT numbers, coefficients, or minor structural changes
6. Focus on the EXACT concepts where genuine errors occurred
7. **ALL MATHEMATICAL EXPRESSIONS MUST BE IN STRICT LATEX FORMAT COMPATIBLE WITH KATEX**
**OUTPUT FORMAT - FOLLOW EXACTLY:**
### Based on Your Work in Question [ORIGINAL_QUESTION_NUMBER]
**Original Question:** [Copy the exact original question text in LaTeX]
**Modified Question [SAME_QUESTION_NUMBER]:** [Create modified version in LaTeX]
Repeat this EXACT structure for each question. DO NOT include any other text, instructions, solutions, or motivational content."""
        response = model.generate_content(practice_prompt)
        practice_paper = response.text
        logger.info(f"Successfully generated practice paper with {len(questions_with_genuine_errors)} questions")
        return JSONResponse({
            "success": True,
            "practice_paper": practice_paper,
            "questions_used": len(questions_with_genuine_errors),
            "message": f"Practice paper created targeting {len(questions_with_genuine_errors)} problematic areas"
        })
    except Exception as e:
        logger.error(f"Practice paper creation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Practice paper creation failed: {str(e)}"
        }, status_code=500)

@app.post("/generate-performance-pdf")
async def generate_performance_pdf(request: Request):
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
            <div style="page-break-before: always;">
                <h2 style="color: #2c3e50; margin-top: 40px; padding-bottom: 10px; border-bottom: 2px solid #3498db;">Performance Insights</h2>
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin: 25px 0;">
                    <div style="font-size: 15px; line-height: 1.8;">{format_math_for_pdf_katex(insights_text)}</div>
                </div>
            </div>
            '''
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Math Performance Report</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <style>
        body {
            font-family: "Times New Roman", Times, serif;
            margin: 25px;
            line-height: 1.7;
            font-size: 14px;
            color: #2c3e50;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 20px;
            margin-bottom: 30px;
            font-size: 24px;
        }
        h2 {
            color: #2c3e50;
            margin-top: 40px;
            padding-bottom: 10px;
            border-bottom: 2px solid #bdc3c7;
            font-size: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 13px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        th, td {
            border: 1px solid #7f8c8d;
            padding: 14px;
            text-align: left;
            vertical-align: top;
        }
        th {
            background-color: #34495e;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }
        .performance-table tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        .math-expression {
            font-family: "Cambria Math", "Times New Roman", serif;
            font-size: 14px;
            margin: 8px 0;
            line-height: 1.6;
            text-align: center;
        }
        .status-error {
            background-color: #ffebee;
            color: #c62828;
            padding: 8px 12px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #ef5350;
        }
        .status-perfect {
            background-color: #e8f5e8;
            color: #2e7d32;
            padding: 8px 12px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #4caf50;
        }
        .status-partial {
            background-color: #fff3e0;
            color: #ef6c00;
            padding: 8px 12px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #ff9800;
        }
        .status-not-tested {
            background-color: #f5f5f5;
            color: #757575;
            padding: 8px 12px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid #bdbdbd;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #7f8c8d;
            font-size: 12px;
            padding-top: 20px;
            border-top: 2px solid #bdc3c7;
        }
        .concept-explanation {
            font-size: 12px;
            color: #546e7a;
            margin-top: 6px;
            line-height: 1.5;
            font-style: italic;
        }
        .report-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #3498db;
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
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
            onload="renderMathInElement(document.body);"></script>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            performance_table=table_html,
            performance_insights=insights_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
        }
        pdfkit.from_string(html_content, output_path, configuration=pdfkit_config, options=pdf_options)
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

def format_math_for_pdf_katex(text):
    if not text:
        return ""
    formatted = text
    formatted = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', formatted)
    formatted = re.sub(r'\\\((.*?)\\\)', r'$\1$', formatted)
    formatted = formatted.replace('\n', '<br>')
    return formatted

def parse_performance_table_for_pdf(table_text):
    rows = table_text.split('\n')
    table_html = '<table class="performance-table">'
    table_html += '<thead><tr>'
    header_cells = [cell.strip() for cell in rows[0].split('|') if cell.strip()]
    for cell in header_cells:
        table_html += f'<th>{cell}</th>'
    table_html += '</tr></thead><tbody>'
    for row in rows[2:]:
        if not row.strip() or not row.strip().startswith('|'):
            continue
        cells = [cell.strip() for cell in row.split('|') if cell.strip()]
        if len(cells) >= 4:
            table_html += '<tr>'
            for i, cell in enumerate(cells):
                cell_content = format_math_for_pdf_katex(cell)
                if i == 3:
                    status_class = get_status_class_for_pdf(cell)
                    table_html += f'<td><span class="{status_class}">{cell_content}</span></td>'
                else:
                    if '<br/>' in cell_content:
                        parts = cell_content.split('<br/>')
                        table_html += f'<td><div class="math-expression">{parts[0]}</div><div class="concept-explanation">{parts[1]}</div></td>'
                    else:
                        table_html += f'<td><div class="math-expression">{cell_content}</div></td>'
            table_html += '</tr>'
    table_html += '</tbody></table>'
    return table_html

def get_status_class_for_pdf(status_text):
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

@app.post("/generate-detailed-pdf")
async def generate_detailed_pdf(request: Request):
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
        detailed_html = generate_detailed_analysis_html_katex(detailed_data)
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Detailed Analysis Report</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <style>
        body {
            font-family: "Times New Roman", Times, serif;
            margin: 20px;
            line-height: 1.7;
            font-size: 13px;
            color: #2c3e50;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            font-size: 22px;
        }
        h2 {
            color: #2c3e50;
            margin-top: 35px;
            padding-bottom: 8px;
            border-bottom: 2px solid #bdc3c7;
            font-size: 18px;
        }
        h3 {
            color: #34495e;
            margin: 25px 0 12px 0;
            font-size: 16px;
        }
        .question-analysis {
            margin: 30px 0;
            border: 2px solid #bdc3c7;
            border-radius: 10px;
            padding: 0;
            overflow: hidden;
            background: white;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }
        .question-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            font-weight: bold;
            font-size: 17px;
        }
        .analysis-section {
            padding: 25px;
            border-bottom: 1px solid #ecf0f1;
        }
        .analysis-section:last-child {
            border-bottom: none;
        }
        .step-item {
            background: #f8f9fa;
            padding: 18px;
            margin: 12px 0;
            border-radius: 8px;
            border-left: 5px solid #3498db;
            font-size: 14px;
        }
        .error-item {
            background: #ffebee;
            border-left: 5px solid #e74c3c;
            color: #c62828;
        }
        .correct-item {
            background: #e8f5e9;
            border-left: 5px solid #2e7d32;
            color: #1b5e20;
        }
        .math-expression {
            font-family: "Cambria Math", "Times New Roman", serif;
            font-size: 15px;
            margin: 10px 0;
            line-height: 1.8;
            text-align: center;
        }
        .final-answer {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 10px;
            margin: 18px 0;
            text-align: center;
            font-weight: bold;
            font-size: 17px;
            border: 3px solid #2196f3;
            font-family: "Times New Roman", serif;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #7f8c8d;
            font-size: 12px;
            padding-top: 20px;
            border-top: 2px solid #bdc3c7;
        }
        .report-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #3498db;
        }
        .simple-error-box {
            background: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
        }
        .error-summary {
            padding: 12px;
            margin: 10px 0;
            background: #fff;
            border-left: 4px solid #e53e3e;
            border-radius: 4px;
            font-size: 14px;
            line-height: 1.5;
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
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
            onload="renderMathInElement(document.body);"></script>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            detailed_content=detailed_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
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

def generate_detailed_analysis_html_katex(detailed_data):
    html = ""
    for q in detailed_data.get('questions', []):
        has_errors = q.get('hasErrors', False)
        html += f"""
        <div class="question-analysis">
            <div class="question-header">
                {q['id']} - Question Analysis {'🔴 Errors Found' if has_errors else '🟢 No Major Errors'}
            </div>
            <div class="analysis-section">
                <h3>📝 Original Question:</h3>
                <div class="step-item math-expression">{format_math_for_pdf_katex(q.get('questionText', 'No question text'))}</div>
            </div>
            <div class="analysis-section">
                <h3>✍️ Student's Exact Solution:</h3>
        """
        for i, step in enumerate(q.get('steps', [])):
            html += f'<div class="step-item math-expression"><strong>Step {i + 1}:</strong><br>{format_math_for_pdf_katex(step)}</div>'
        html += """
            </div>
            <div class="analysis-section">
                <h3>🔍 Error Analysis:</h3>
                <div class="simple-error-box">
        """
        if has_errors and q.get('mistakes'):
            for mistake in q['mistakes']:
                html += f"""
                <div class="error-summary">
                    <strong>Step {mistake.get('step', 'N/A')}:</strong> {format_math_for_pdf_katex(mistake.get('desc', 'No description'))}
                </div>
                """
        else:
            html += '<div class="error-summary" style="border-left-color: #38a169; background: #f0fff4;"><strong>✓ No Conceptual Errors Found</strong><br><em>Solution appears mathematically correct</em></div>'
        html += """
                </div>
            </div>
            <div class="analysis-section">
                <h3>✅ Correct Solution:</h3>
        """
        for i, step in enumerate(q.get('correctedSteps', [])):
            html += f'<div class="step-item correct-item math-expression"><strong>Step {i + 1}:</strong><br>{format_math_for_pdf_katex(step)}</div>'
        if q.get('finalAnswer'):
            html += f'<div class="final-answer">🎯 Final Answer: {q["finalAnswer"]}</div>'
        html += """
            </div>
        </div>
        """
    return html

@app.post("/generate-practice-pdf")
async def generate_practice_pdf(request: Request):
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
        practice_html = """
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #2c3e50; border-bottom: 3px solid #2c3e50; padding-bottom: 15px;">
                Targeted Practice Paper
            </h1>
            <h2 style="color: #34495e;">Based on Your Conceptual Errors</h2>
        </div>
        """
        question_blocks = practice_content.split('### Based on Your Work in Question')
        for block in question_blocks[1:]:
            question_match = re.search(r'Question\s+([^:]+):', block)
            original_match = re.search(r'Original Question:\s*(.*?)(?=Modified Question|$)', block, re.DOTALL)
            modified_match = re.search(r'Modified Question\s*\[([^\]]+)\]:\s*(.*?)(?=### Based on Your Work|$)', block, re.DOTALL)
            if question_match and original_match and modified_match:
                question_number = question_match[1].strip()
                original_question = original_match[1].strip()
                modified_question = modified_match[2].strip()
                practice_html += f"""
                <div style="margin: 35px 0; border: 2px solid #bdc3c7; border-radius: 10px; overflow: hidden;">
                    <div style="background: #f8f9fa; padding: 20px; border-bottom: 2px solid #dee2e6;">
                        <h4 style="margin: 0; color: #2c3e50;">Question {question_number}</h4>
                    </div>
                    <div style="padding: 25px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div style="border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; background: #f8f9fa;">
                            <h5 style="margin-top: 0; color: #34495e;">Original Question:</h5>
                            <div style="font-family: 'Cambria Math', serif; font-size: 14px; margin: 10px 0; line-height: 1.8; text-align: center; padding: 10px; background: white; border-radius: 5px;">
                                {format_math_for_pdf_katex(original_question)}
                            </div>
                        </div>
                        <div style="border: 1px solid #c3e6cb; padding: 15px; border-radius: 8px; background: #f0fff4;">
                            <h5 style="margin-top: 0; color: #28a745;">Practice Question:</h5>
                            <div style="font-family: 'Cambria Math', serif; font-size: 14px; margin: 10px 0; line-height: 1.8; text-align: center; padding: 10px; background: white; border-radius: 5px;">
                                {format_math_for_pdf_katex(modified_question)}
                            </div>
                        </div>
                    </div>
                </div>
                """
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Targeted Practice Paper</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <style>
        body {
            font-family: "Times New Roman", Times, serif;
            margin: 25px;
            line-height: 1.7;
            font-size: 14px;
            color: #2c3e50;
        }
        .math-expression {
            font-family: "Cambria Math", "Times New Roman", serif;
            font-size: 14px;
            margin: 10px 0;
            line-height: 1.8;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #7f8c8d;
            font-size: 12px;
            padding-top: 20px;
            border-top: 2px solid #bdc3c7;
        }
    </style>
</head>
<body>
    {{ practice_content }}
    <div class="footer">
        <p>Generated by Math Analyzer • {{ timestamp }}</p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
            onload="renderMathInElement(document.body);"></script>
</body>
</html>"""
        template = Template(html_template)
        html_content = template.render(
            practice_content=practice_html,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            output_path = tmp_file.name
        pdf_options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': "UTF-8",
        }
        pdfkit.from_string(html_content, output_path, configuration=pdfkit_config, options=pdf_options)
        return FileResponse(
            output_path,
            media_type='application/pdf',
            filename='Targeted_Practice_Paper.pdf'
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"PDF generation failed: {str(e)}"
        }, status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
