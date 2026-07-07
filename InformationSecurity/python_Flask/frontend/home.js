// ==================== 全局变量 ====================
let user = null;
let isAdmin = false;

// ==================== 初始化检查 ====================
// 未登录跳回
async function checkLogin() {
    const token = sessionStorage.getItem("token");

    if (!token) {
        window.location.href = "login_register.html";
        return false;
    }

    // 验证 token 是否有效
    const result = await apiGetCurrentUser();
    if (!result.success) {
        logout();
        return false;
    }

    user = result.data;
    isAdmin = user.is_admin;

    // 更新本地存储
    sessionStorage.setItem("isAdmin", isAdmin ? "true" : "false");

    return true;
}

// ==================== 页面初始化 ====================
async function initPage() {
    const isLoggedIn = await checkLogin();
    if (!isLoggedIn) return;

    // 从 localStorage 获取用户名（兼容性）
    const username = sessionStorage.getItem("username") || user.username;
    const adminFlag = sessionStorage.getItem("isAdmin") === "true";

    // 显示用户名
    document.getElementById("userInfo").innerText = username;
    document.getElementById("profileUser").innerText = username;

    // 显示用户邮箱
    if (!adminFlag) {
        document.getElementById("profileEmailText").innerText = user.email || "未设置";
    } else {
        // 管理员隐藏邮箱
        document.getElementById("profileEmail").style.display = "none";
        // 显示管理员标识
        document.getElementById("adminBadge").classList.remove("hidden");
        // 显示管理员导航
        document.getElementById("adminNavBtn").classList.remove("hidden");
    }

    // 恢复保存的背景颜色
    const savedBg = localStorage.getItem("bgColor");
    if (savedBg && bgColors[savedBg]) {
        document.body.style.background = bgColors[savedBg];
    }
}

// ==================== 页面切换函数 ====================
function showPage(page) {
    // 隐藏所有页面(包括 3 个嵌入的子页面,SPA 化后)
    ["homePage", "profilePage", "settingsPage", "adminPage",
     "psiIntPage", "psiMatchPage", "psiUnionPage",
     "psiSumPage", "ssPsiPage"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });

    // 移除所有导航按钮的active状态
    let navBtns = document.querySelectorAll('.nav-btn');
    navBtns.forEach(btn => btn.classList.remove('active'));

    // 显示选中的页面
    if (page === "home") {
        document.getElementById("homePage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '首页') btn.classList.add('active');
        });
    } else if (page === "profile") {
        document.getElementById("profilePage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '个人中心') btn.classList.add('active');
        });
    } else if (page === "settings") {
        document.getElementById("settingsPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '设置') btn.classList.add('active');
        });
    } else if (page === "admin") {
        if (!isAdmin) {
            alert("权限不足");
            showPage('home');
            return;
        }
        document.getElementById("adminPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '用户管理') btn.classList.add('active');
        });
        loadUserList();
    } else if (page === "psiInt") {
        document.getElementById("psiIntPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '隐私求交') btn.classList.add('active');
        });
        if (typeof PSI_INT !== 'undefined' && PSI_INT.init) PSI_INT.init();
    } else if (page === "psiMatch") {
        document.getElementById("psiMatchPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '集合匹配') btn.classList.add('active');
        });
        if (typeof PSI_MATCH !== 'undefined' && PSI_MATCH.init) PSI_MATCH.init();
    } else if (page === "psiUnion") {
        document.getElementById("psiUnionPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '隐私求并') btn.classList.add('active');
        });
        if (typeof PSI_UNION !== 'undefined' && PSI_UNION.init) PSI_UNION.init();
    } else if (page === "psiSum") {
        // 2026-07-05: PSI-Sum 演示 (mock)
        document.getElementById("psiSumPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '隐私求和') btn.classList.add('active');
        });
        if (typeof PSI_SUM !== 'undefined' && PSI_SUM.init) PSI_SUM.init();
    } else if (page === "ssPsi") {
        // 2026-07-05: SS-PSI 演示 (mock)
        document.getElementById("ssPsiPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '多方隐私求交') btn.classList.add('active');
        });
        if (typeof SS_PSI !== 'undefined' && SS_PSI.init) SS_PSI.init();
    }
}

// loadInFrame 函数已删除(2026-07-01 重构为 SPA,子页面合并到主页)
// 切换子页面请用 showPage('psiInt' | 'psiMatch' | 'psiUnion')



// ==================== 管理员功能 ====================

// 加载用户列表
async function loadUserList() {
    const tbody = document.getElementById("userTableBody");
    const noUsersDiv = document.getElementById("noUsers");

    tbody.innerHTML = "";

    try {
        const result = await apiGetAllUsers();

        if (result.success) {
            const users = result.data.users || [];

            if (users.length === 0) {
                noUsersDiv.classList.remove("hidden");
                return;
            }

            noUsersDiv.classList.add("hidden");

            users.forEach(userInfo => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${userInfo.username}</td>
                    <td>${userInfo.email || '-'}</td>
                    <td>${userInfo.created_at || '-'}</td>
                    <td>
                        <button class="btn btn-delete btn-small" onclick="adminDeleteUser('${userInfo.username}')">删除</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            alert(result.message || '获取用户列表失败');
        }
    } catch (error) {
        console.error('加载用户列表错误:', error);
        alert('网络错误，请检查后端是否启动');
    }
}

// 管理员删除用户
async function adminDeleteUser(username) {
    if (!confirm(`确定要删除用户 "${username}" 吗？此操作不可恢复！`)) {
        return;
    }

    try {
        const result = await apiDeleteUser(username);

        if (result.success) {
            alert(`用户 "${username}" 已删除`);
            loadUserList(); // 重新加载用户列表
        } else {
            alert(result.message || '删除用户失败');
        }
    } catch (error) {
        console.error('删除用户错误:', error);
        alert('网络错误，请检查后端是否启动');
    }
}

// ==================== 背景颜色设置 ====================
const bgColors = {
    blue: '#f9fafb',     // 极简浅灰白
    red: '#fee2e2',      // 柔和浅红
    green: '#d1fae5'     // 柔和浅绿
};

function changeBg(color) {
    document.body.style.background = bgColors[color];
    localStorage.setItem("bgColor", color);
}

// ==================== 页面加载 ====================
window.addEventListener("load", initPage);
