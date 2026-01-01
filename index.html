<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Auth Test</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f0f2f5; display: flex; justify-content: center; padding: 50px; }
        .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); width: 400px; }
        h2 { text-align: center; color: #4361ee; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; }
        button { width: 100%; padding: 12px; background: #4361ee; color: white; border: none; border-radius: 6px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #3650d1; }
        .msg { padding: 10px; margin-top: 15px; border-radius: 6px; text-align: center; }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
        a { color: #4361ee; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Simple Auth Test</h2>

        <div id="registerForm">
            <h3>Register</h3>
            <input type="text" id="regUsername" placeholder="Username">
            <input type="password" id="regPassword" placeholder="Password">
            <input type="password" id="regConfirm" placeholder="Confirm Password">
            <button onclick="register()">Register</button>
            <p style="text-align:center; margin-top:15px;">
                Already have account? <a href="#" onclick="showLogin()">Login</a>
            </p>
        </div>

        <div id="loginForm" style="display:none;">
            <h3>Login</h3>
            <input type="text" id="loginUsername" placeholder="Username">
            <input type="password" id="loginPassword" placeholder="Password">
            <button onclick="login()">Login</button>
            <p style="text-align:center; margin-top:15px;">
                No account? <a href="#" onclick="showRegister()">Register</a>
            </p>
        </div>

        <div id="status" class="msg" style="display:none;"></div>
        <div id="user" style="margin-top:20px; text-align:center;"></div>
    </div>

    <script>
        const API = 'https://navalsheth.pythonanywhere.com';

        function show(msg, success = true) {
            const el = document.getElementById('status');
            el.textContent = msg;
            el.className = 'msg ' + (success ? 'success' : 'error');
            el.style.display = 'block';
        }

        async function register() {
            const u = document.getElementById('regUsername').value.trim();
            const p = document.getElementById('regPassword').value;
            const c = document.getElementById('regConfirm').value;

            if (!u || !p || !c) return show('Fill all fields', false);
            if (p !== c) return show('Passwords do not match', false);

            try {
                const res = await fetch(`${API}/api/register`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p, confirm: c})
                });
                const data = await res.json();
                show(data.message, data.success);
                if (data.success) checkAuth();
            } catch (e) {
                show('Network error', false);
            }
        }

        async function login() {
            const u = document.getElementById('loginUsername').value.trim();
            const p = document.getElementById('loginPassword').value;

            try {
                const res = await fetch(`${API}/api/login`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                show(data.message, data.success);
                if (data.success) checkAuth();
            } catch (e) {
                show('Network error', false);
            }
        }

        async function checkAuth() {
            try {
                const res = await fetch(`${API}/api/check_auth`, { credentials: 'include' });
                const data = await res.json();
                if (data.authenticated) {
                    document.getElementById('user').innerHTML = `<strong>Logged in as: ${data.username}</strong>`;
                } else {
                    document.getElementById('user').innerHTML = '';
                }
            } catch (e) {}
        }

        function showLogin() {
            document.getElementById('registerForm').style.display = 'none';
            document.getElementById('loginForm').style.display = 'block';
        }

        function showRegister() {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('registerForm').style.display = 'block';
        }

        checkAuth(); // on load
    </script>
</body>
</html>
