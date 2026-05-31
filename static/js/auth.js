/* ═══════════════════════════════════════════════
   AIHOTNESS — Auth JavaScript
   ═══════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function() {
    // ── Login Form ──
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('loginBtn');
            const errorEl = document.getElementById('loginError');
            btn.disabled = true;
            btn.textContent = '登录中...';
            errorEl.style.display = 'none';

            try {
                const resp = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('loginUsername').value.trim(),
                        password: document.getElementById('loginPassword').value,
                    }),
                });
                const data = await resp.json();
                if (resp.ok && data.token) {
                    localStorage.setItem('token', data.token);
                    showToast('登录成功！', 'success');
                    setTimeout(() => { window.location.href = '/'; }, 500);
                } else {
                    errorEl.textContent = data.detail || '登录失败';
                    errorEl.style.display = 'block';
                }
            } catch (err) {
                errorEl.textContent = '网络错误，请稍后重试';
                errorEl.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.textContent = '登录';
            }
        });
    }

    // ── Register Form ──
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('registerBtn');
            const errorEl = document.getElementById('registerError');
            const password = document.getElementById('regPassword').value;
            const confirm = document.getElementById('regConfirm').value;

            // Client-side validation
            if (password !== confirm) {
                errorEl.textContent = '两次输入的密码不一致';
                errorEl.style.display = 'block';
                return;
            }
            if (password.length < 6) {
                errorEl.textContent = '密码至少 6 位';
                errorEl.style.display = 'block';
                return;
            }

            btn.disabled = true;
            btn.textContent = '注册中...';
            errorEl.style.display = 'none';

            try {
                const resp = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('regUsername').value.trim(),
                        email: document.getElementById('regEmail').value.trim(),
                        password: password,
                    }),
                });
                const data = await resp.json();
                if (resp.ok && data.token) {
                    localStorage.setItem('token', data.token);
                    showToast('注册成功！', 'success');
                    setTimeout(() => { window.location.href = '/'; }, 500);
                } else {
                    errorEl.textContent = data.detail || '注册失败';
                    errorEl.style.display = 'block';
                }
            } catch (err) {
                errorEl.textContent = '网络错误，请稍后重试';
                errorEl.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.textContent = '注册';
            }
        });
    }
});
