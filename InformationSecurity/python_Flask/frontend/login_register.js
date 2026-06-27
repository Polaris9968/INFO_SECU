// ==================== 全局变量 ====================
let countdownTimer = null;

// ==================== 页面切换函数 ====================
function showRegister() {
    document.getElementById("loginBox").classList.add("hidden");
    document.getElementById("registerBox").classList.remove("hidden");
    hideMessage("loginMessage");
}

function showLogin() {
    document.getElementById("registerBox").classList.add("hidden");
    document.getElementById("loginBox").classList.remove("hidden");
    // 清空输入框
    document.getElementById("regEmail").value = "";
    document.getElementById("regUser").value = "";
    document.getElementById("regPass").value = "";
    document.getElementById("regPassConfirm").value = "";
    hideMessage("regMessage");
}

// ==================== 工具函数 ====================

// 验证邮箱格式
function isValidEmail(email) {
    const emailRegex = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return emailRegex.test(email);
}

// 显示消息
function showMessage(elementId, text, type = "error") {
    const msgEl = document.getElementById(elementId);
    msgEl.textContent = text;
    msgEl.className = "message " + type;
    msgEl.classList.remove("hidden");
}

function hideMessage(elementId) {
    const msgEl = document.getElementById(elementId);
    msgEl.classList.add("hidden");
}

// 设置按钮加载状态
function setButtonLoading(btnId, loading, originalText) {
    const btn = document.getElementById(btnId);
    if (loading) {
        btn.dataset.originalText = btn.textContent;
        btn.textContent = "处理中...";
        btn.disabled = true;
    } else {
        btn.textContent = originalText || btn.dataset.originalText;
        btn.disabled = false;
    }
}

// ==================== 注册函数 ====================
async function register() {
    const email = document.getElementById("regEmail").value.trim();
    const username = document.getElementById("regUser").value.trim();
    const password = document.getElementById("regPass").value.trim();
    const passwordConfirm = document.getElementById("regPassConfirm").value.trim();

    // 验证用户名
    if (!username) {
        showMessage("regMessage", "请输入用户名");
        return;
    }

    if (username.length < 3 || username.length > 20) {
        showMessage("regMessage", "用户名长度应在3-20个字符之间");
        return;
    }

    // 验证邮箱（如果填写了）
    if (email && !isValidEmail(email)) {
        showMessage("regMessage", "请输入正确的邮箱格式");
        return;
    }

    // 验证密码
    if (!password) {
        showMessage("regMessage", "请输入密码");
        return;
    }

    if (password.length < 6) {
        showMessage("regMessage", "密码长度至少6位");
        return;
    }

    // 验证确认密码
    if (password !== passwordConfirm) {
        showMessage("regMessage", "两次输入的密码不一致");
        return;
    }

    setButtonLoading("regBtn", true);

    try {
        const result = await apiRegister(username, password, email);

        if (result.success) {
            showMessage("regMessage", result.message, "success");
            // 延迟切换到登录
            setTimeout(() => {
                showLogin();
            }, 1500);
        } else {
            showMessage("regMessage", result.message || "注册失败");
        }
    } catch (error) {
        console.error("注册错误:", error);
        showMessage("regMessage", "网络错误，请检查后端是否启动");
    } finally {
        setButtonLoading("regBtn", false);
    }
}

// ==================== 登录函数 ====================
async function login() {
    const username = document.getElementById("loginUser").value.trim();
    const password = document.getElementById("loginPass").value.trim();

    if (!username || !password) {
        showMessage("loginMessage", "请输入用户名和密码");
        return;
    }

    setButtonLoading("loginBtn", true);

    try {
        const result = await apiLogin(username, password);

        if (result.success) {
            showMessage("loginMessage", "登录成功！", "success");
            // 保存用户信息到 localStorage
            sessionStorage.setItem("token", result.data.token);
            sessionStorage.setItem("username", result.data.username);
            sessionStorage.setItem("isAdmin", result.data.is_admin ? "true" : "false");

            // 跳转到主页
            setTimeout(() => {
                window.location.href = "home.html";
            }, 500);
        } else {
            showMessage("loginMessage", result.message || "登录失败");
        }
    } catch (error) {
        console.error("登录错误:", error);
        showMessage("loginMessage", "网络错误，请检查后端是否启动");
    } finally {
        setButtonLoading("loginBtn", false);
    }
}

// ==================== 页面加载时检查登录状态 ====================
window.addEventListener("load", async () => {
    const token = sessionStorage.getItem("token");

    if (token) {
        // 验证 token 是否有效
        try {
            const result = await apiGetCurrentUser();
            if (result.success) {
                // 已登录，跳转到主页
                window.location.href = "home.html";
            }
        } catch (error) {
            // token 无效，清除
            sessionStorage.removeItem("token");
            sessionStorage.removeItem("username");
            sessionStorage.removeItem("isAdmin");
        }
    }
});
