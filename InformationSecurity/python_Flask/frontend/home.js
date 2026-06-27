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
    // 隐藏所有页面
    document.getElementById("homePage").style.display = "none";
    document.getElementById("profilePage").style.display = "none";
    document.getElementById("sortPage").style.display = "none";
    document.getElementById("settingsPage").style.display = "none";
    document.getElementById("adminPage").style.display = "none";

    // 隐藏 iframe（切换回内部页面时）
    const frame = document.getElementById("contentFrame");
    if (frame) frame.style.display = "none";

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
    } else if (page === "sort") {
        document.getElementById("sortPage").style.display = "block";
        navBtns.forEach(btn => {
            if (btn.textContent.trim() === '排序功能') btn.classList.add('active');
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
    }
}

// ==================== iframe 加载外部功能页 ====================
// 协作排序/隐私求交/集合匹配/隐私求并点击时调用，不再跳转而是内嵌展示
function loadInFrame(url, btnText) {
    // 隐藏所有内部 panel（与 showPage 行为一致）
    ["homePage", "profilePage", "sortPage", "settingsPage", "adminPage"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
    });

    // 显示 iframe 并加载目标页面
    const frame = document.getElementById("contentFrame");
    if (!frame) {
        console.error("contentFrame iframe 未找到");
        return;
    }
    // 先隐藏（避免新页面加载期间旧内容"闪一下"），等 onload 后再显示
    frame.style.display = "none";
    // 清空旧 src（防浏览器复用旧帧），同步生效
    frame.src = "about:blank";
    // 设置新 src（异步加载）
    frame.src = url;

    // iframe 加载完后做一系列"无缝集成"处理：
    //   1. 隐藏子页面的 top-bar（home 已经有侧边栏，子页面的顶栏多余）
    //   2. 去掉 body 的 min-height: 100vh（避免 iframe 撑出滚动条）
    //   3. 去掉 body 背景色（让 home 的渐变背景透过来，保持视觉统一）
    //   4. iframe 高度 = 内容真实高度（让滚动条只出现在外层页面，不嵌套）
    frame.onload = function () {
        const adjust = () => {
            try {
                const doc = frame.contentDocument;
                if (!doc || !doc.body) return;

                // 1. 隐藏子页面的 top-bar
                doc.querySelectorAll('.top-bar').forEach(el => el.style.display = 'none');

                // 2 & 3. 去掉 body 的 min-height 和 background（让 home 背景透出）
                doc.body.style.minHeight = '0';
                doc.body.style.background = 'transparent';

                // 4. iframe 高度跟随内容（让滚动条只在外层）
                const realH = Math.max(
                    doc.body.scrollHeight,
                    doc.documentElement.scrollHeight
                );
                frame.style.height = (realH + 20) + 'px';

                // 5. 加载完成，显示 iframe（避免旧内容闪一下）
                frame.style.display = 'block';
            } catch (e) {
                console.warn('iframe 内容调整失败:', e);
            }
        };
        adjust();
        // 二次调整：子页面里如果有 fetch 动态渲染内容，渲染完后再算一次
        setTimeout(adjust, 800);

        // 持续监听 body 高度变化（小组列表异步加载/窗口 resize/数据更新等都会改变高度）
        // 这样无论子页面内容什么时候变高，iframe 高度都跟得上，不会出现双滚动条
        try {
            const doc = frame.contentDocument;
            if (doc && doc.body && typeof ResizeObserver !== 'undefined') {
                if (frame._resizeObserver) frame._resizeObserver.disconnect();
                const ro = new ResizeObserver(() => adjust());
                ro.observe(doc.body);
                frame._resizeObserver = ro;
            }
        } catch (e) {
            // cross-origin 或其他原因导致 ResizeObserver 不可用时静默忽略
        }
    };

    // 高亮当前按钮
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.trim() === btnText) btn.classList.add('active');
    });
}

// ==================== 数据排序处理函数 ====================
async function sortTxtFile() {
    const fileInput = document.getElementById('txtFileInput');
    const file = fileInput.files[0];
    const sortBtn = document.getElementById('sortBtn');

    if (!file) {
        alert('请先选择一个 TXT 文件');
        return;
    }

    if (!file.name.endsWith('.txt')) {
        alert('只支持 .txt 文件');
        return;
    }

    sortBtn.disabled = true;
    sortBtn.textContent = '处理中...';

    try {
        const result = await apiSortFile(file);

        if (result.success) {
            const data = result.data;

            // 显示统计信息
            document.getElementById('statCount').textContent = data.statistics.count;
            document.getElementById('statMax').textContent = data.statistics.max;
            document.getElementById('statMin').textContent = data.statistics.min;
            document.getElementById('statAvg').textContent = data.statistics.average.toFixed(2);

            // 显示排序结果
            document.getElementById('sortedResult').textContent = data.sorted.join(' ');

            // 显示结果容器
            document.getElementById('resultContainer').classList.remove('hidden');
        } else {
            alert(result.message || '文件处理失败');
            document.getElementById('resultContainer').classList.add('hidden');
        }
    } catch (error) {
        console.error('排序错误:', error);
        alert('网络错误，请检查后端是否启动');
        document.getElementById('resultContainer').classList.add('hidden');
    } finally {
        sortBtn.disabled = false;
        sortBtn.textContent = '排序并显示';
    }
}

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
