// User database
const userDatabase = {
    'teacher@math.com': { 
        password: 'password', 
        name: 'Dr. Mathematics', 
        role: 'teacher'
    },
    'student@math.com': { 
        password: 'password', 
        name: 'Student Learner', 
        role: 'student'
    },
    'admin@math.com': { 
        password: 'password', 
        name: 'Admin User', 
        role: 'admin'
    }
};

// Current user state
let currentUser = null;
let questionFiles = [];
let answerFiles = [];
let analysisResults = null;

// DOM Elements
const loginPage = document.getElementById('login-page');
const dashboardPage = document.getElementById('dashboard-page');
const loginForm = document.querySelector('.login-form');
const userName = document.getElementById('user-name');
const dashboardUserName = document.getElementById('dashboard-user-name');
const logoutBtn = document.getElementById('logout-btn');
const uploadQuestionBtn = document.getElementById('upload-question-btn');
const uploadAnswerBtn = document.getElementById('upload-answer-btn');
const questionUpload = document.getElementById('question-upload');
const answerUpload = document.getElementById('answer-upload');
const questionFileList = document.getElementById('question-file-list');
const answerFileList = document.getElementById('answer-file-list');
const analysisSheet = document.getElementById('analysis-sheet');
const beginAnalysisBtn = document.getElementById('begin-analysis-btn');
const progressSection = document.getElementById('progress-section');
const progressText = document.getElementById('progress-text');
const progressFill = document.getElementById('progress-fill');
const progressDetails = document.getElementById('progress-details');
const resultsSection = document.getElementById('results-section');
const totalQuestions = document.getElementById('total-questions');
const detailedAnalysisBtn = document.getElementById('detailed-analysis-btn');
const generatePaperBtn = document.getElementById('generate-paper-btn');
const analysisResultsDiv = document.getElementById('analysis-results');
const generatePaperModal = document.getElementById('generate-paper-modal');
const closeModal = document.getElementById('close-modal');
const questionSelectorList = document.getElementById('question-selector-list');
const previewContent = document.getElementById('preview-content');
const generateFinalBtn = document.getElementById('generate-final-btn');

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is already logged in
    const savedUser = localStorage.getItem('math_ocr_user');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        loadDashboard();
        return;
    }

    // Set up login form
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        handleLogin();
    });

    // Social login buttons
    document.getElementById('google-login').addEventListener('click', function() {
        alert('Google authentication would be implemented in production');
    });

    document.getElementById('apple-login').addEventListener('click', function() {
        alert('Apple authentication would be implemented in production');
    });
});

// Handle login
function handleLogin() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    if (!email || !password) {
        alert('Please enter both email and password');
        return;
    }

    // Check credentials
    if (userDatabase[email] && userDatabase[email].password === password) {
        currentUser = {
            email: email,
            name: userDatabase[email].name,
            role: userDatabase[email].role
        };
        
        // Store user in localStorage
        localStorage.setItem('math_ocr_user', JSON.stringify(currentUser));
        loadDashboard();
    } else {
        alert('Invalid email or password. Try: teacher@math.com / password');
    }
}

// Load dashboard
function loadDashboard() {
    userName.textContent = currentUser.name.split(' ')[0];
    dashboardUserName.textContent = currentUser.name;
    showPage('dashboard-page');
    
    // Setup event listeners
    setupDashboardEvents();
}

// Setup dashboard event listeners
function setupDashboardEvents() {
    // Logout
    logoutBtn.addEventListener('click', handleLogout);
    
    // File uploads
    uploadQuestionBtn.addEventListener('click', () => questionUpload.click());
    uploadAnswerBtn.addEventListener('click', () => answerUpload.click());
    
    questionUpload.addEventListener('change', (e) => handleFileUpload(e, 'question'));
    answerUpload.addEventListener('change', (e) => handleFileUpload(e, 'answer'));
    
    // Analysis sheet selection
    analysisSheet.addEventListener('change', updateAnalysisButton);
    
    // Begin analysis
    beginAnalysisBtn.addEventListener('click', beginAnalysis);
    
    // Results buttons
    detailedAnalysisBtn.addEventListener('click', showDetailedAnalysis);
    generatePaperBtn.addEventListener('click', showGeneratePaperModal);
    
    // Modal controls
    closeModal.addEventListener('click', () => generatePaperModal.style.display = 'none');
    generateFinalBtn.addEventListener('click', generatePracticePaper);
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === generatePaperModal) {
            generatePaperModal.style.display = 'none';
        }
    });
}

// Handle file upload
function handleFileUpload(event, type) {
    const files = Array.from(event.target.files);
    const fileListDiv = type === 'question' ? questionFileList : answerFileList;
    const fileArray = type === 'question' ? questionFiles : answerFiles;
    
    // Clear existing files
    fileArray.length = 0;
    
    if (files.length === 0) {
        fileListDiv.innerHTML = '<p>No files selected</p>';
        updateAnalysisButton();
        return;
    }
    
    // Store files
    files.forEach(file => {
        fileArray.push({
            name: file.name,
            size: file.size,
            type: file.type,
            file: file
        });
    });
    
    // Update UI
    fileListDiv.innerHTML = files.map(file => 
        `<div class="file-item">
            <i class="fas fa-file"></i>
            <span>${file.name} (${formatFileSize(file.size)})</span>
        </div>`
    ).join('');
    
    updateAnalysisButton();
}

// Update analysis button state
function updateAnalysisButton() {
    const hasFiles = questionFiles.length > 0 && answerFiles.length > 0;
    const hasSheet = analysisSheet.value !== '';
    beginAnalysisBtn.disabled = !(hasFiles && hasSheet);
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Begin analysis
async function beginAnalysis() {
    if (questionFiles.length === 0 || answerFiles.length === 0) {
        alert('Please upload both question and answer files');
        return;
    }
    
    if (!analysisSheet.value) {
        alert('Please select an analysis sheet');
        return;
    }
    
    // Show progress section
    progressSection.style.display = 'block';
    resultsSection.style.display = 'none';
    analysisResultsDiv.classList.remove('active');
    
    // Reset progress
    progressFill.style.width = '0%';
    progressDetails.innerHTML = '';
    
    // Simulate analysis process with streaming updates
    await simulateAnalysisProcess();
}

// Simulate analysis with streaming updates
async function simulateAnalysisProcess() {
    const steps = [
        { text: 'Processing uploaded files...', duration: 1000, progress: 10 },
        { text: 'Extracting text from documents...', duration: 1500, progress: 25 },
        { text: 'Identifying mathematical equations...', duration: 2000, progress: 40 },
        { text: 'Analyzing question structure...', duration: 1500, progress: 55 },
        { text: 'Evaluating student solutions...', duration: 2000, progress: 70 },
        { text: 'Checking for mathematical errors...', duration: 1500, progress: 85 },
        { text: 'Generating detailed analysis...', duration: 1000, progress: 100 }
    ];
    
    for (const step of steps) {
        progressText.textContent = step.text;
        progressFill.style.width = step.progress + '%';
        
        // Add streaming update
        const updateDiv = document.createElement('p');
        updateDiv.textContent = step.text;
        updateDiv.classList.add('success');
        progressDetails.appendChild(updateDiv);
        progressDetails.scrollTop = progressDetails.scrollHeight;
        
        // Wait for step duration
        await wait(step.duration);
    }
    
    // Complete analysis
    progressText.textContent = 'Analysis complete!';
    
    // Generate sample analysis results
    analysisResults = generateSampleAnalysis();
    
    // Show results after delay
    await wait(1000);
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Update stats
    totalQuestions.textContent = `${analysisResults.questions.length} questions analyzed`;
}

// Wait function
function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Generate sample analysis data
function generateSampleAnalysis() {
    return {
        sheetName: analysisSheet.options[analysisSheet.selectedIndex].text,
        questions: [
            {
                id: 'Q1',
                number: '1(a)',
                originalQuestion: 'Evaluate $\\int (3x^2 + 2x + 1) \\, dx$',
                studentAnswer: '$\\int (3x^2 + 2x + 1) \\, dx = x^3 + x^2 + x$',
                correctAnswer: '$\\int (3x^2 + 2x + 1) \\, dx = x^3 + x^2 + x + C$',
                mistakes: ['Missing constant of integration (C)'],
                isCorrect: false,
                explanation: 'When evaluating indefinite integrals, always include the constant of integration.'
            },
            {
                id: 'Q2',
                number: '1(b)',
                originalQuestion: 'Find $\\frac{d}{dx}(\\sin(x^2))$',
                studentAnswer: '$\\frac{d}{dx}(\\sin(x^2)) = \\cos(x^2)$',
                correctAnswer: '$\\frac{d}{dx}(\\sin(x^2)) = 2x\\cos(x^2)$',
                mistakes: ['Incorrect application of chain rule'],
                isCorrect: false,
                explanation: 'Apply chain rule: $\\frac{d}{dx}\\sin(f(x)) = f\'(x)\\cos(f(x))$'
            },
            {
                id: 'Q3',
                number: '2',
                originalQuestion: 'Solve $\\frac{d^2y}{dx^2} - 3\\frac{dy}{dx} + 2y = 0$',
                studentAnswer: '$y = Ae^x + Be^{2x}$',
                correctAnswer: '$y = Ae^x + Be^{2x}$',
                mistakes: [],
                isCorrect: true,
                explanation: 'Correct solution to the homogeneous second-order differential equation.'
            },
            {
                id: 'Q4',
                number: '3(a)',
                originalQuestion: 'Evaluate $\\lim_{x \\to 0} \\frac{\\sin(3x)}{x}$',
                studentAnswer: '$\\lim_{x \\to 0} \\frac{\\sin(3x)}{x} = 1$',
                correctAnswer: '$\\lim_{x \\to 0} \\frac{\\sin(3x)}{x} = 3$',
                mistakes: ['Forgot to multiply by 3 from the angle'],
                isCorrect: false,
                explanation: 'Using limit identity: $\\lim_{x \\to 0} \\frac{\\sin(kx)}{x} = k$'
            },
            {
                id: 'Q5',
                number: '4',
                originalQuestion: 'Find the area between $y = x^2$ and $y = x$ from $x = 0$ to $x = 1$',
                studentAnswer: 'Area = $\\int_0^1 (x - x^2) dx = \\frac{1}{6}$',
                correctAnswer: 'Area = $\\int_0^1 (x - x^2) dx = \\frac{1}{6}$',
                mistakes: [],
                isCorrect: true,
                explanation: 'Correct application of area between curves formula.'
            }
        ]
    };
}

// Show detailed analysis
// Show detailed analysis
function showDetailedAnalysis() {
    if (!analysisResults) {
        alert('Please complete analysis first');
        return;
    }
    
    analysisResultsDiv.innerHTML = `
        <div class="analysis-header">
            <h3>${analysisResults.sheetName}</h3>
            <p>Detailed analysis of student work</p>
        </div>
        ${analysisResults.questions.map(question => `
            <div class="question-item">
                <div class="question-header">
                    <span class="question-number">${question.number}</span>
                    <span class="question-status ${question.isCorrect ? 'status-correct' : 'status-incorrect'}">
                        ${question.isCorrect ? '✓ Correct' : '✗ Needs Review'}
                    </span>
                </div>
                
                <div class="question-content">
                    <div class="section-title">Original Question</div>
                    <div class="math-content">${question.originalQuestion}</div>
                    
                    <div class="section-title">Student's Answer</div>
                    <div class="math-content">${question.studentAnswer}</div>
                    
                    ${!question.isCorrect ? `
                        <div class="section-title">Mathematical Errors Found</div>
                        <ul class="mistakes-list">
                            ${question.mistakes.map(mistake => `
                                <li class="mistake-item">${mistake}</li>
                            `).join('')}
                        </ul>
                    ` : ''}
                    
                    <div class="section-title">${question.isCorrect ? 'Correct Answer' : 'Correct Solution'}</div>
                    <div class="math-content">${question.correctAnswer}</div>
                </div>
            </div>
        `).join('')}
    `;
    
    analysisResultsDiv.classList.add('active');
    
    // FORCE MathJax to render - FIXED!
    if (window.MathJax) {
        MathJax.typesetPromise([analysisResultsDiv]).then(() => {
            console.log('MathJax rendering complete');
        }).catch((err) => {
            console.error('MathJax rendering error:', err);
            // Try again after a short delay
            setTimeout(() => {
                if (window.MathJax) {
                    MathJax.typesetPromise([analysisResultsDiv]);
                }
            }, 500);
        });
    }
}
// Show generate paper modal
function showGeneratePaperModal() {
    if (!analysisResults) {
        alert('Please complete analysis first');
        return;
    }
    
    // Populate question selector
    questionSelectorList.innerHTML = analysisResults.questions
        .filter(q => !q.isCorrect) // Only show incorrect questions
        .map(question => `
            <label class="question-checkbox">
                <input type="checkbox" value="${question.id}" checked>
                <span>${question.number}</span>
            </label>
        `).join('');
    
    // Generate preview
    generatePreview();
    
    // Show modal
    generatePaperModal.style.display = 'flex';
}

// Generate preview of redesigned questions
function generatePreview() {
    const selectedQuestions = analysisResults.questions.filter(q => !q.isCorrect);
    
    previewContent.innerHTML = selectedQuestions.map((question, index) => `
        <div class="preview-item">
            <div class="preview-header">
                <strong>${question.number} (Redesigned)</strong>
            </div>
            <div class="original-question">
                <strong>Original:</strong> ${question.originalQuestion}
            </div>
            <div class="redesigned-question">
                <strong>Redesigned:</strong> ${generateRedesignedQuestion(question)}
            </div>
            ${index < selectedQuestions.length - 1 ? '<hr>' : ''}
        </div>
    `).join('');
    
    // Typeset MathJax
    if (window.MathJax) {
        MathJax.typesetPromise([previewContent]);
    }
}

// Generate redesigned question
function generateRedesignedQuestion(question) {
    const original = question.originalQuestion;
    
    // Simple redesign by changing coefficients/variables
    if (original.includes('\\int')) {
        return original
            .replace('3x^2', '4x^2')
            .replace('2x', '3x')
            .replace('1', '2');
    } else if (original.includes('\\frac{d}{dx}')) {
        return original
            .replace('\\sin(x^2)', '\\cos(x^3)')
            .replace('x^2', 'x^3');
    } else if (original.includes('\\lim')) {
        return original
            .replace('\\sin(3x)', '\\sin(4x)')
            .replace('3x', '4x');
    } else {
        // Default redesign
        return original
            .replace('3', '5')
            .replace('2', '4')
            .replace('1', '3');
    }
}

// Generate practice paper
function generatePracticePaper() {
    const selectedIds = Array.from(
        document.querySelectorAll('.question-checkbox input:checked')
    ).map(input => input.value);
    
    const selectedQuestions = analysisResults.questions.filter(q => 
        selectedIds.includes(q.id) && !q.isCorrect
    );
    
    if (selectedQuestions.length === 0) {
        alert('Please select at least one question to redesign');
        return;
    }
    
    // Create practice paper content
    let paperContent = `Practice Paper - ${analysisResults.sheetName}\n\n`;
    paperContent += '='.repeat(50) + '\n\n';
    
    selectedQuestions.forEach((question, index) => {
        paperContent += `${index + 1}. ${generateRedesignedQuestion(question)}\n\n`;
        paperContent += `   Based on original question: ${question.number}\n`;
        paperContent += `   Student error: ${question.mistakes[0]}\n\n`;
        paperContent += '   Space for solution:\n\n'.repeat(3);
          paperContent += '-'.repeat(50) + '\n\n';
    });
    
    // Create and download file
    const blob = new Blob([paperContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Practice_Paper_${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    // Close modal
    generatePaperModal.style.display = 'none';
    
    alert('Practice paper downloaded successfully!');
}

// Show specific page
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show the requested page
    document.getElementById(pageId).classList.add('active');
}

// Handle logout
function handleLogout() {
    currentUser = null;
    localStorage.removeItem('math_ocr_user');
    showPage('login-page');
    
    // Clear login form
    document.getElementById('email').value = '';
    document.getElementById('password').value = '';
    
    // Reset state
    questionFiles = [];
    answerFiles = [];
    analysisResults = null;
    questionFileList.innerHTML = '<p>No files selected</p>';
    answerFileList.innerHTML = '<p>No files selected</p>';
    analysisSheet.value = '';
    progressSection.style.display = 'none';
    resultsSection.style.display = 'none';
    analysisResultsDiv.classList.remove('active');
    analysisResultsDiv.innerHTML = '';
}

// Handle page visibility
function handleVisibilityChange() {
    if (!document.hidden && currentUser) {
        // Refresh MathJax when page becomes visible
        if (window.MathJax && analysisResultsDiv.classList.contains('active')) {
            MathJax.typesetPromise([analysisResultsDiv]);
        }
    }
}

// Initialize visibility handler
document.addEventListener('visibilitychange', handleVisibilityChange);

// Real file upload to backend (for actual implementation)
async function uploadFilesToBackend() {
    if (questionFiles.length === 0 || answerFiles.length === 0) {
        return false;
    }
    
    const formData = new FormData();
    
    // Add question files
    questionFiles.forEach((fileObj, index) => {
        formData.append('question_files', fileObj.file);
    });
    
    // Add answer files
    answerFiles.forEach((fileObj, index) => {
        formData.append('answer_files', fileObj.file);
    });
    
    // Add analysis sheet info
    formData.append('analysis_sheet', analysisSheet.value);
    
    try {
        // This is where you would make the actual API call
        // const response = await fetch('/api/analyze', {
        //     method: 'POST',
        //     body: formData
        // });
        
        // For now, we'll use the simulated version
        return true;
    } catch (error) {
        console.error('Upload error:', error);
        alert('Failed to upload files. Please try again.');
        return false;
    }
}

// Real-time WebSocket connection for streaming analysis
function setupWebSocket() {
    // This would be implemented for real-time updates
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = () => {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    if (data.type === 'progress') {
        progressText.textContent = data.message;
        progressFill.style.width = data.progress + '%';
        
        const updateDiv = document.createElement('p');
        updateDiv.textContent = data.message;
        updateDiv.classList.add('success');
        progressDetails.appendChild(updateDiv);
        progressDetails.scrollTop = progressDetails.scrollHeight;
    } else if (data.type === 'result') {
        analysisResults = data.data;
        progressSection.style.display = 'none';
        resultsSection.style.display = 'block';
        totalQuestions.textContent = `${analysisResults.questions.length} questions analyzed`;
    } else if (data.type === 'error') {
        const errorDiv = document.createElement('p');
        errorDiv.textContent = `Error: ${data.message}`;
        errorDiv.classList.add('error');
        progressDetails.appendChild(errorDiv);
        progressDetails.scrollTop = progressDetails.scrollHeight;
    }
}

// Initialize WebSocket on dashboard load
if (dashboardPage.classList.contains('active')) {
    // setupWebSocket(); // Uncomment for real WebSocket implementation
}

// Additional helper functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Handle window resize
window.addEventListener('resize', debounce(() => {
    // Re-render MathJax on resize
    if (window.MathJax && analysisResultsDiv.classList.contains('active')) {
        MathJax.typesetPromise([analysisResultsDiv]);
    }
}, 250));

// Prevent form submission on enter in inputs
document.querySelectorAll('input').forEach(input => {
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && input.type !== 'submit') {
            e.preventDefault();
        }
    });
});

// Enhanced error handling
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    // You could send this to an error tracking service
});

// Unload handler
window.addEventListener('beforeunload', (event) => {
    if (progressSection.style.display === 'block') {
        // Warn user if analysis is in progress
        event.preventDefault();
        event.returnValue = 'Analysis is in progress. Are you sure you want to leave?';
        return event.returnValue;
    }
});

// Initialize MathJax typesetting for dynamic content
function refreshMathJax() {
    if (window.MathJax) {
        MathJax.typesetPromise();
    }
}

// Make functions available globally for event handlers
window.handleLogout = handleLogout;
window.showDetailedAnalysis = showDetailedAnalysis;
window.showGeneratePaperModal = showGeneratePaperModal;
window.generatePracticePaper = generatePracticePaper;



        
