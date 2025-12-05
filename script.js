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
let currentJobId = null;
let websocket = null;

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

// Begin analysis - REAL VERSION
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
    
    try {
        // 1. Upload files to backend
        const uploadResult = await uploadFilesToBackend();
        
        if (uploadResult.success && uploadResult.job_id) {
            currentJobId = uploadResult.job_id;
            
            // 2. Connect WebSocket with job ID and start analysis
            setupWebSocket(currentJobId);
            
        } else {
            throw new Error(uploadResult.error || 'Upload failed');
        }
    } catch (error) {
        console.error('Analysis failed:', error);
        addProgressUpdate(`Error: ${error.message}`, 'error');
        progressText.textContent = 'Analysis failed';
    }
}

// REAL file upload to backend
async function uploadFilesToBackend() {
    if (questionFiles.length === 0 || answerFiles.length === 0) {
        return { success: false, error: 'No files selected' };
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
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        console.log('Upload result:', result);
        return result;
        
    } catch (error) {
        console.error('Upload error:', error);
        return { success: false, error: 'Failed to upload files' };
    }
}

// Setup WebSocket connection
function setupWebSocket(jobId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${jobId}`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = () => {
        console.log('WebSocket connected to', wsUrl);
        addProgressUpdate('Connected to analysis server', 'success');
        
        // Immediately send start analysis message
        websocket.send(JSON.stringify({
            action: 'start_analysis',
            job_id: jobId
        }));
    };
    
    websocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };
    
    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        addProgressUpdate('Connection error', 'error');
    };
    
    websocket.onclose = () => {
        console.log('WebSocket disconnected');
        addProgressUpdate('Disconnected from server', 'warning');
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    console.log('WebSocket message:', data);
    
    if (data.type === 'progress') {
        progressText.textContent = data.message;
        progressFill.style.width = data.progress + '%';
        addProgressUpdate(data.message, 'success');
    } 
    else if (data.type === 'result') {
        analysisResults = data.data;
        progressSection.style.display = 'none';
        resultsSection.style.display = 'block';
        totalQuestions.textContent = `${analysisResults.questions.length} questions analyzed`;
        
        // Auto-show detailed analysis
        showDetailedAnalysis();
    } 
    else if (data.type === 'error') {
        addProgressUpdate(`Error: ${data.message}`, 'error');
        progressText.textContent = 'Analysis failed';
    }
}

// Add progress update to UI
function addProgressUpdate(message, type = 'info') {
    const updateDiv = document.createElement('p');
    updateDiv.textContent = message;
    updateDiv.classList.add(type);
    progressDetails.appendChild(updateDiv);
    progressDetails.scrollTop = progressDetails.scrollHeight;
}

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
                    
                    ${!question.isCorrect && question.mistakes && question.mistakes.length > 0 ? `
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
    
    // Force MathJax to render
    if (window.MathJax) {
        MathJax.typesetPromise([analysisResultsDiv]).catch(err => {
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
    const incorrectQuestions = analysisResults.questions.filter(q => !q.isCorrect);
    if (incorrectQuestions.length === 0) {
        alert('No incorrect questions to redesign!');
        return;
    }
    
    questionSelectorList.innerHTML = incorrectQuestions
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
    const original = question.originalQuestion || '';
    
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
            .replace('1', '3')
            .replace('x', 't')
            .replace('y', 'z');
    }
}

// Generate practice paper
async function generatePracticePaper() {
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
    
    try {
        const response = await fetch('/api/generate-paper', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                job_id: currentJobId,
                question_ids: selectedIds
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Download the file
            window.location.href = result.download_url;
            
            // Close modal
            generatePaperModal.style.display = 'none';
            
            alert('Practice paper downloaded successfully!');
        } else {
            alert(`Error: ${result.error}`);
        }
    } catch (error) {
        console.error('Paper generation error:', error);
        alert('Failed to generate practice paper');
    }
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
    // Close WebSocket if open
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.close();
    }
    
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
    currentJobId = null;
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
    if (!document.hidden && currentUser && window.MathJax) {
        // Refresh MathJax when page becomes visible
        if (analysisResultsDiv.classList.contains('active')) {
            MathJax.typesetPromise([analysisResultsDiv]);
        }
    }
}

// Initialize visibility handler
document.addEventListener('visibilitychange', handleVisibilityChange);

// Debounce function for resize events
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
    if (window.MathJax && analysisResultsDiv.classList.contains('active')) {
        MathJax.typesetPromise([analysisResultsDiv]);
    }
}, 250));

// Make functions available globally for event handlers
window.handleLogout = handleLogout;
window.showDetailedAnalysis = showDetailedAnalysis;
window.showGeneratePaperModal = showGeneratePaperModal;
window.generatePracticePaper = generatePracticePaper;

// Style for progress messages
const style = document.createElement('style');
style.textContent = `
    .success { color: #10b981; }
    .error { color: #ef4444; }
    .warning { color: #f59e0b; }
    .info { color: #3b82f6; }
`;
document.head.appendChild(style);
