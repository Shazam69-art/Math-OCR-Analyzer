// User database with roles linked to emails
const userDatabase = {
    'doctor@mednemesis.com': { 
        password: 'password', 
        name: 'Dr. Jonathan Smith', 
        role: 'doctor',
        specialty: 'Cardiologist'
    },
    'patient@mednemesis.com': { 
        password: 'password', 
        name: 'Sarah Johnson', 
        role: 'patient',
        patientId: 'P-7842'
    },
    'nurse@mednemesis.com': { 
        password: 'password', 
        name: 'Emily Wilson', 
        role: 'nurse',
        department: 'Emergency Care'
    },
    'receptionist@mednemesis.com': { 
        password: 'password', 
        name: 'Michael Brown', 
        role: 'receptionist',
        location: 'Main Reception'
    },
    'pharmacist@mednemesis.com': { 
        password: 'password', 
        name: 'David Chen', 
        role: 'pharmacist',
        pharmacy: 'Central Pharmacy'
    }
};

// Current user state
let currentUser = null;

// DOM Elements
const loginPage = document.getElementById('login-page');
const rolePage = document.getElementById('role-page');
const dashboardContainer = document.getElementById('dashboard-container');

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is already logged in
    const savedUser = localStorage.getItem('mednemesis_user');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        // Directly load their dashboard based on stored role
        loadDashboard(currentUser.role);
        return;
    }

    // Set up login form
    const loginForm = document.querySelector('.login-form');
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

// Handle login process
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
            role: userDatabase[email].role,
            ...userDatabase[email]
        };
        
        // Store user in localStorage
        localStorage.setItem('mednemesis_user', JSON.stringify(currentUser));
        
        // If user already has a role assigned, go directly to dashboard
        if (currentUser.role) {
            loadDashboard(currentUser.role);
        } else {
            // Show role selection (for new users without assigned roles)
            showRoleSelection();
        }
    } else {
        alert('Invalid email or password. Try: doctor@mednemesis.com / password');
    }
}

// Show role selection page
function showRoleSelection() {
    // This would be used for new users without assigned roles
    const roleSelectionHTML = `
        <div class="role-container">
            <div class="role-header">
                <h1>Select Your Role</h1>
                <p>Choose your primary role in the healthcare system</p>
            </div>
            
            <div class="role-grid">
                <div class="role-card" data-role="doctor">
                    <div class="role-icon">
                        <i class="fas fa-user-md"></i>
                    </div>
                    <h3>Doctor</h3>
                    <p>Access patient records, create prescriptions, and manage appointments</p>
                </div>
                
                <div class="role-card" data-role="patient">
                    <div class="role-icon">
                        <i class="fas fa-user-injured"></i>
                    </div>
                    <h3>Patient</h3>
                    <p>View medical records, book appointments, and manage medications</p>
                </div>
                
                <div class="role-card" data-role="nurse">
                    <div class="role-icon">
                        <i class="fas fa-user-nurse"></i>
                    </div>
                    <h3>Nurse</h3>
                    <p>Monitor patient vitals, update charts, and assist with procedures</p>
                </div>
                
                <div class="role-card" data-role="receptionist">
                    <div class="role-icon">
                        <i class="fas fa-concierge-bell"></i>
                    </div>
                    <h3>Receptionist</h3>
                    <p>Manage appointments, handle inquiries, and coordinate schedules</p>
                </div>
                
                <div class="role-card" data-role="pharmacist">
                    <div class="role-icon">
                        <i class="fas fa-prescription-bottle-alt"></i>
                    </div>
                    <h3>Pharmacist</h3>
                    <p>Dispense medications, check interactions, and manage inventory</p>
                </div>
            </div>
            
            <div class="role-footer">
                <button class="back-btn" id="back-to-login">
                    <i class="fas fa-arrow-left"></i>
                    Back to Login
                </button>
            </div>
        </div>
    `;
    
    rolePage.innerHTML = roleSelectionHTML;
    showPage('role-page');
    
    // Add event listeners for role selection
    document.querySelectorAll('.role-card').forEach(card => {
        card.addEventListener('click', function() {
            const role = this.getAttribute('data-role');
            currentUser.role = role;
            localStorage.setItem('mednemesis_user', JSON.stringify(currentUser));
            loadDashboard(role);
        });
    });
    
    document.getElementById('back-to-login').addEventListener('click', function() {
        showPage('login-page');
    });
}

// Load appropriate dashboard based on role
function loadDashboard(role) {
    let dashboardHTML = '';
    
    switch(role) {
        case 'doctor':
            dashboardHTML = getDoctorDashboard();
            break;
        case 'patient':
            dashboardHTML = getPatientDashboard();
            break;
        case 'nurse':
            dashboardHTML = getNurseDashboard();
            break;
        case 'receptionist':
            dashboardHTML = getReceptionistDashboard();
            break;
        case 'pharmacist':
            dashboardHTML = getPharmacistDashboard();
            break;
        default:
            dashboardHTML = getPatientDashboard();
    }
    
    dashboardContainer.innerHTML = dashboardHTML;
    showPage('dashboard-container');
    
    // Add logout functionality
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Add AI chat functionality if present
    setupAIChat();
}

// Doctor Dashboard
function getDoctorDashboard() {
    return `
        <div class="dashboard-container">
            <header class="dashboard-header">
                <div class="header-left">
                    <h1>Doctor Dashboard</h1>
                    <p>Welcome back, ${currentUser.name}</p>
                </div>
                <div class="header-right">
                    <div class="user-menu">
                        <div class="user-info">
                            <span class="user-name">${currentUser.name}</span>
                            <span class="user-role">${currentUser.specialty}</span>
                        </div>
                        <div class="user-avatar">
                            <i class="fas fa-user-md"></i>
                        </div>
                        <button class="logout-btn" id="logout-btn">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    </div>
                </div>
            </header>

            <div class="dashboard-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-calendar-check"></i>
                        </div>
                        <div class="stat-info">
                            <h3>12</h3>
                            <p>Today's Appointments</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-file-medical"></i>
                        </div>
                        <div class="stat-info">
                            <h3>8</h3>
                            <p>Pending Reports</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="stat-info">
                            <h3>3</h3>
                            <p>Urgent Cases</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-prescription"></i>
                        </div>
                        <div class="stat-info">
                            <h3>15</h3>
                            <p>Prescriptions Today</p>
                        </div>
                    </div>
                </div>

                <div class="content-grid">
                    <div class="content-card">
                        <h3>Today's Schedule</h3>
                        <div class="schedule-list">
                            <div class="schedule-item">
                                <div class="time">09:00 AM</div>
                                <div class="patient">Sarah Johnson - Follow-up</div>
                                <div class="status confirmed">Confirmed</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">10:30 AM</div>
                                <div class="patient">Michael Brown - New Patient</div>
                                <div class="status confirmed">Confirmed</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">11:45 AM</div>
                                <div class="patient">Emma Wilson - Consultation</div>
                                <div class="status pending">Pending</div>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Quick Actions</h3>
                        <div class="action-buttons">
                            <button class="action-btn">
                                <i class="fas fa-file-medical"></i>
                                Write Prescription
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-notes-medical"></i>
                                Add Medical Note
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-calendar-plus"></i>
                                Schedule Appointment
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-vial"></i>
                                Order Tests
                            </button>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Medical Assistant AI</h3>
                        <div class="ai-chat">
                            <div class="chat-messages" id="ai-chat-messages">
                                <div class="message ai-message">
                                    <p>Hello Dr. Smith! I can help you with medical queries, drug information, or patient data analysis. What would you like to know?</p>
                                </div>
                            </div>
                            <div class="chat-input">
                                <input type="text" id="ai-chat-input" placeholder="Ask about medications, conditions, or patient data...">
                                <button id="ai-chat-send">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Recent Patients</h3>
                        <div class="patients-list">
                            <div class="patient-item">
                                <div class="patient-avatar">SJ</div>
                                <div class="patient-info">
                                    <h4>Sarah Johnson</h4>
                                    <p>Hypertension • Last visit: 2 days ago</p>
                                </div>
                            </div>
                            <div class="patient-item">
                                <div class="patient-avatar">MB</div>
                                <div class="patient-info">
                                    <h4>Michael Brown</h4>
                                    <p>Diabetes • Last visit: 1 week ago</p>
                                </div>
                            </div>
                            <div class="patient-item">
                                <div class="patient-avatar">EW</div>
                                <div class="patient-info">
                                    <h4>Emma Wilson</h4>
                                    <p>Asthma • Last visit: 3 days ago</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Patient Dashboard
function getPatientDashboard() {
    return `
        <div class="dashboard-container">
            <header class="dashboard-header">
                <div class="header-left">
                    <h1>Patient Dashboard</h1>
                    <p>Welcome back, ${currentUser.name.split(' ')[0]}</p>
                </div>
                <div class="header-right">
                    <div class="user-menu">
                        <div class="user-info">
                            <span class="user-name">${currentUser.name}</span>
                            <span class="user-role">Patient ID: ${currentUser.patientId}</span>
                        </div>
                        <div class="user-avatar">
                            <i class="fas fa-user-injured"></i>
                        </div>
                        <button class="logout-btn" id="logout-btn">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    </div>
                </div>
            </header>

            <div class="dashboard-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-calendar-check"></i>
                        </div>
                        <div class="stat-info">
                            <h3>2</h3>
                            <p>Upcoming Appointments</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-prescription-bottle-alt"></i>
                        </div>
                        <div class="stat-info">
                            <h3>5</h3>
                            <p>Active Medications</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-file-medical"></i>
                        </div>
                        <div class="stat-info">
                            <h3>12</h3>
                            <p>Medical Records</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-bell"></i>
                        </div>
                        <div class="stat-info">
                            <h3>3</h3>
                            <p>Pending Reminders</p>
                        </div>
                    </div>
                </div>

                <div class="content-grid">
                    <div class="content-card">
                        <h3>My Appointments</h3>
                        <div class="appointment-list">
                            <div class="appointment-item">
                                <div class="appointment-date">Tomorrow, 10:30 AM</div>
                                <div class="appointment-details">
                                    <h4>Dr. Jonathan Smith</h4>
                                    <p>Cardiology Follow-up</p>
                                </div>
                                <button class="action-btn small">Reschedule</button>
                            </div>
                            <div class="appointment-item">
                                <div class="appointment-date">June 15, 2:00 PM</div>
                                <div class="appointment-details">
                                    <h4>Dr. Emily Chen</h4>
                                    <p>Annual Check-up</p>
                                </div>
                                <button class="action-btn small">Cancel</button>
                            </div>
                        </div>
                        <button class="action-btn full-width">
                            <i class="fas fa-calendar-plus"></i>
                            Book New Appointment
                        </button>
                    </div>

                    <div class="content-card">
                        <h3>Current Medications</h3>
                        <div class="medication-list">
                            <div class="medication-item">
                                <div class="medication-name">Lisinopril 10mg</div>
                                <div class="medication-schedule">Once daily, Morning</div>
                                <div class="medication-status active">Active</div>
                            </div>
                            <div class="medication-item">
                                <div class="medication-name">Atorvastatin 20mg</div>
                                <div class="medication-schedule">Once daily, Evening</div>
                                <div class="medication-status active">Active</div>
                            </div>
                            <div class="medication-item">
                                <div class="medication-name">Metformin 500mg</div>
                                <div class="medication-schedule">Twice daily</div>
                                <div class="medication-status active">Active</div>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Health Assistant AI</h3>
                        <div class="ai-chat">
                            <div class="chat-messages" id="ai-chat-messages">
                                <div class="message ai-message">
                                    <p>Hello ${currentUser.name.split(' ')[0]}! I can help answer your health questions, explain medical terms, or provide information about your medications. How can I assist you today?</p>
                                </div>
                            </div>
                            <div class="chat-input">
                                <input type="text" id="ai-chat-input" placeholder="Ask about your health, medications, or appointments...">
                                <button id="ai-chat-send">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Quick Access</h3>
                        <div class="quick-actions">
                            <button class="quick-btn">
                                <i class="fas fa-file-medical"></i>
                                View Medical Records
                            </button>
                            <button class="quick-btn">
                                <i class="fas fa-prescription"></i>
                                Request Prescription Refill
                            </button>
                            <button class="quick-btn">
                                <i class="fas fa-download"></i>
                                Download Health Summary
                            </button>
                            <button class="quick-btn">
                                <i class="fas fa-phone-alt"></i>
                                Contact My Doctor
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Nurse Dashboard
function getNurseDashboard() {
    return `
        <div class="dashboard-container">
            <header class="dashboard-header">
                <div class="header-left">
                    <h1>Nurse Dashboard</h1>
                    <p>Welcome back, ${currentUser.name}</p>
                </div>
                <div class="header-right">
                    <div class="user-menu">
                        <div class="user-info">
                            <span class="user-name">${currentUser.name}</span>
                            <span class="user-role">${currentUser.department}</span>
                        </div>
                        <div class="user-avatar">
                            <i class="fas fa-user-nurse"></i>
                        </div>
                        <button class="logout-btn" id="logout-btn">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    </div>
                </div>
            </header>

            <div class="dashboard-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-bed"></i>
                        </div>
                        <div class="stat-info">
                            <h3>8</h3>
                            <p>Patients Assigned</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-heartbeat"></i>
                        </div>
                        <div class="stat-info">
                            <h3>24</h3>
                            <p>Vitals to Check</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-syringe"></i>
                        </div>
                        <div class="stat-info">
                            <h3>12</h3>
                            <p>Medications Due</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="stat-info">
                            <h3>2</h3>
                            <p>Critical Alerts</p>
                        </div>
                    </div>
                </div>

                <div class="content-grid">
                    <div class="content-card">
                        <h3>Patient Rounds</h3>
                        <div class="schedule-list">
                            <div class="schedule-item">
                                <div class="time">Room 201</div>
                                <div class="patient">John Davis - Post-op Monitoring</div>
                                <div class="status critical">Critical</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">Room 305</div>
                                <div class="patient">Maria Garcia - IV Medication</div>
                                <div class="status confirmed">Due Now</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">Room 412</div>
                                <div class="patient">Robert Wilson - Vital Signs</div>
                                <div class="status pending">Pending</div>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Quick Actions</h3>
                        <div class="action-buttons">
                            <button class="action-btn">
                                <i class="fas fa-heartbeat"></i>
                                Record Vitals
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-syringe"></i>
                                Administer Medication
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-file-medical"></i>
                                Update Chart
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-bell"></i>
                                Alert Doctor
                            </button>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Nursing Assistant AI</h3>
                        <div class="ai-chat">
                            <div class="chat-messages" id="ai-chat-messages">
                                <div class="message ai-message">
                                    <p>Hello Nurse ${currentUser.name.split(' ')[0]}! I can help with medication protocols, vital sign ranges, or patient care procedures. How can I assist you?</p>
                                </div>
                            </div>
                            <div class="chat-input">
                                <input type="text" id="ai-chat-input" placeholder="Ask about procedures, medications, or patient care...">
                                <button id="ai-chat-send">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Recent Patient Updates</h3>
                        <div class="patients-list">
                            <div class="patient-item">
                                <div class="patient-avatar">JD</div>
                                <div class="patient-info">
                                    <h4>John Davis</h4>
                                    <p>Room 201 • BP: 145/92 • Last update: 30 min ago</p>
                                </div>
                            </div>
                            <div class="patient-item">
                                <div class="patient-avatar">MG</div>
                                <div class="patient-info">
                                    <h4>Maria Garcia</h4>
                                    <p>Room 305 • Temp: 38.2°C • Needs attention</p>
                                </div>
                            </div>
                            <div class="patient-item">
                                <div class="patient-avatar">RW</div>
                                <div class="patient-info">
                                    <h4>Robert Wilson</h4>
                                    <p>Room 412 • Stable • Next vitals due: 2 hours</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Receptionist Dashboard
function getReceptionistDashboard() {
    return `
        <div class="dashboard-container">
            <header class="dashboard-header">
                <div class="header-left">
                    <h1>Receptionist Dashboard</h1>
                    <p>Welcome back, ${currentUser.name}</p>
                </div>
                <div class="header-right">
                    <div class="user-menu">
                        <div class="user-info">
                            <span class="user-name">${currentUser.name}</span>
                            <span class="user-role">${currentUser.location}</span>
                        </div>
                        <div class="user-avatar">
                            <i class="fas fa-concierge-bell"></i>
                        </div>
                        <button class="logout-btn" id="logout-btn">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    </div>
                </div>
            </header>

            <div class="dashboard-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-calendar-day"></i>
                        </div>
                        <div class="stat-info">
                            <h3>45</h3>
                            <p>Today's Appointments</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-user-clock"></i>
                        </div>
                        <div class="stat-info">
                            <h3>8</h3>
                            <p>Waiting Patients</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-phone"></i>
                        </div>
                        <div class="stat-info">
                            <h3>23</h3>
                            <p>Calls Today</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-envelope"></i>
                        </div>
                        <div class="stat-info">
                            <h3>15</h3>
                            <p>Pending Messages</p>
                        </div>
                    </div>
                </div>

                <div class="content-grid">
                    <div class="content-card">
                        <h3>Current Waiting Room</h3>
                        <div class="schedule-list">
                            <div class="schedule-item">
                                <div class="time">Token #15</div>
                                <div class="patient">Lisa Thompson - Dr. Smith</div>
                                <div class="status confirmed">Waiting: 5 min</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">Token #16</div>
                                <div class="patient">James Miller - Dr. Chen</div>
                                <div class="status confirmed">Waiting: 12 min</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">Token #17</div>
                                <div class="patient">Anna Davis - Dr. Rodriguez</div>
                                <div class="status pending">Checked In</div>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Quick Actions</h3>
                        <div class="action-buttons">
                            <button class="action-btn">
                                <i class="fas fa-user-plus"></i>
                                Check-in Patient
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-calendar-plus"></i>
                                New Appointment
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-file-invoice"></i>
                                Process Payment
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-phone"></i>
                                Call Patient
                            </button>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Reception Assistant AI</h3>
                        <div class="ai-chat">
                            <div class="chat-messages" id="ai-chat-messages">
                                <div class="message ai-message">
                                    <p>Hello ${currentUser.name.split(' ')[0]}! I can help with appointment scheduling, patient information, or administrative queries. What do you need assistance with?</p>
                                </div>
                            </div>
                            <div class="chat-input">
                                <input type="text" id="ai-chat-input" placeholder="Ask about appointments, patients, or procedures...">
                                <button id="ai-chat-send">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Upcoming Appointments</h3>
                        <div class="appointment-list">
                            <div class="appointment-item">
                                <div class="appointment-date">Next 30 min</div>
                                <div class="appointment-details">
                                    <h4>Dr. Jonathan Smith</h4>
                                    <p>Sarah Johnson - Follow-up</p>
                                </div>
                                <button class="action-btn small">Notify</button>
                            </div>
                            <div class="appointment-item">
                                <div class="appointment-date">Next 45 min</div>
                                <div class="appointment-details">
                                    <h4>Dr. Emily Chen</h4>
                                    <p>Michael Brown - Consultation</p>
                                </div>
                                <button class="action-btn small">Prepare</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Pharmacist Dashboard
function getPharmacistDashboard() {
    return `
        <div class="dashboard-container">
            <header class="dashboard-header">
                <div class="header-left">
                    <h1>Pharmacist Dashboard</h1>
                    <p>Welcome back, ${currentUser.name}</p>
                </div>
                <div class="header-right">
                    <div class="user-menu">
                        <div class="user-info">
                            <span class="user-name">${currentUser.name}</span>
                            <span class="user-role">${currentUser.pharmacy}</span>
                        </div>
                        <div class="user-avatar">
                            <i class="fas fa-prescription-bottle-alt"></i>
                        </div>
                        <button class="logout-btn" id="logout-btn">
                            <i class="fas fa-sign-out-alt"></i>
                        </button>
                    </div>
                </div>
            </header>

            <div class="dashboard-content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-prescription"></i>
                        </div>
                        <div class="stat-info">
                            <h3>28</h3>
                            <p>Pending Prescriptions</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-capsules"></i>
                        </div>
                        <div class="stat-info">
                            <h3>5</h3>
                            <p>Low Stock Items</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="stat-info">
                            <h3>3</h3>
                            <p>Interaction Alerts</p>
                        </div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-phone"></i>
                        </div>
                        <div class="stat-info">
                            <h3>7</h3>
                            <p>Doctor Calls Needed</p>
                        </div>
                    </div>
                </div>

                <div class="content-grid">
                    <div class="content-card">
                        <h3>Prescription Queue</h3>
                        <div class="schedule-list">
                            <div class="schedule-item">
                                <div class="time">#P-7842</div>
                                <div class="patient">Sarah Johnson - Dr. Smith</div>
                                <div class="status critical">Interaction Alert</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">#P-8192</div>
                                <div class="patient">Michael Brown - Dr. Chen</div>
                                <div class="status confirmed">Ready in 15 min</div>
                            </div>
                            <div class="schedule-item">
                                <div class="time">#P-8021</div>
                                <div class="patient">Emma Wilson - Dr. Rodriguez</div>
                                <div class="status pending">Processing</div>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Quick Actions</h3>
                        <div class="action-buttons">
                            <button class="action-btn">
                                <i class="fas fa-prescription"></i>
                                Fill Prescription
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-search"></i>
                                Check Interactions
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-box"></i>
                                Inventory Check
                            </button>
                            <button class="action-btn">
                                <i class="fas fa-phone"></i>
                                Contact Doctor
                            </button>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Pharmacy Assistant AI</h3>
                        <div class="ai-chat">
                            <div class="chat-messages" id="ai-chat-messages">
                                <div class="message ai-message">
                                    <p>Hello ${currentUser.name.split(' ')[0]}! I can help with drug information, interaction checks, dosage calculations, or inventory queries. What do you need to know?</p>
                                </div>
                            </div>
                            <div class="chat-input">
                                <input type="text" id="ai-chat-input" placeholder="Ask about medications, interactions, or inventory...">
                                <button id="ai-chat-send">
                                    <i class="fas fa-paper-plane"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="content-card">
                        <h3>Low Stock Alert</h3>
                        <div class="medication-list">
                            <div class="medication-item">
                                <div class="medication-name">Lisinopril 10mg</div>
                                <div class="medication-schedule">Stock: 12 units</div>
                                <div class="medication-status critical">Low</div>
                            </div>
                            <div class="medication-item">
                                <div class="medication-name">Atorvastatin 20mg</div>
                                <div class="medication-schedule">Stock: 8 units</div>
                                <div class="medication-status critical">Very Low</div>
                            </div>
                            <div class="medication-item">
                                <div class="medication-name">Metformin 500mg</div>
                                <div class="medication-schedule">Stock: 25 units</div>
                                <div class="medication-status warning">Monitor</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
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
    localStorage.removeItem('mednemesis_user');
    showPage('login-page');
    
    // Clear login form
    document.getElementById('email').value = '';
    document.getElementById('password').value = '';
}

// Setup AI chat functionality
function setupAIChat() {
    const chatInput = document.getElementById('ai-chat-input');
    const chatSend = document.getElementById('ai-chat-send');
    const chatMessages = document.getElementById('ai-chat-messages');

    if (chatInput && chatSend && chatMessages) {
        const sendMessage = () => {
            const message = chatInput.value.trim();
            if (!message) return;
            
            // Add user message
            addChatMessage(chatMessages, message, 'user');
            chatInput.value = '';
            
            // Simulate AI response
            setTimeout(() => {
                const response = generateAIResponse(message);
                addChatMessage(chatMessages, response, 'ai');
            }, 1000);
        };

        chatSend.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
}

// Add message to chat
function addChatMessage(container, text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    messageDiv.innerHTML = `<p>${text}</p>`;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// Generate AI response
function generateAIResponse(message) {
    const responses = [
        "I understand your concern. Let me provide some information about that.",
        "Based on medical guidelines, here's what I can share about your query:",
        "I recommend consulting with your healthcare provider for personalized medical advice.",
        "That's an important health question. Here's some general information that might help:",
        "I can help with general health information. For specific medical concerns, please contact your doctor."
    ];
    return responses[Math.floor(Math.random() * responses.length)];
}