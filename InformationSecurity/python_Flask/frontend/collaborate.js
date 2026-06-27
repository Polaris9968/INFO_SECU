// ==================== 全局变量 ====================
let currentGroupId = null;
let refreshInterval = null;

// ==================== 初始化检查 ====================
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

    return true;
}

// ==================== 页面初始化 ====================
async function initPage() {
    const isLoggedIn = await checkLogin();
    if (!isLoggedIn) return;

    // 显示用户名
    const username = sessionStorage.getItem("username") || result?.data?.username;
    document.getElementById("userInfo").innerText = username;

    // 加载我的小组列表
    await loadMyGroups();

    // 启动自动刷新（每5秒）
    startAutoRefresh();
}

// ==================== 自动刷新 ====================
function startAutoRefresh() {
    // 清除之前的定时器
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }

    // 每5秒刷新一次
    refreshInterval = setInterval(async () => {
        await loadMyGroups();
        if (currentGroupId) {
            await refreshCurrentGroup();
        }
    }, 5000);
}

// ==================== 小组管理功能 ====================

// 创建小组
async function createGroup() {
    const groupNameInput = document.getElementById("groupNameInput");
    const groupName = groupNameInput.value.trim();

    if (!groupName) {
        alert("请输入小组名称");
        return;
    }

    try {
        const result = await apiCreateGroup(groupName);

        if (result.success) {
            alert(`小组创建成功！\n小组ID: ${result.data.group.id}\n请分享ID给其他成员加入`);
            groupNameInput.value = "";

            // 刷新小组列表
            await loadMyGroups();

            // 自动切换到新创建的小组
            await selectGroup(result.data.group.id);
        } else {
            alert(result.message || "创建小组失败");
        }
    } catch (error) {
        console.error("创建小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

// 加入小组
async function joinGroup() {
    const groupIdInput = document.getElementById("groupIdInput");
    const groupId = groupIdInput.value.trim().toUpperCase();

    if (!groupId) {
        alert("请输入小组ID");
        return;
    }

    if (groupId.length !== 6) {
        alert("小组ID应为6位");
        return;
    }

    try {
        const result = await apiJoinGroup(groupId);

        if (result.success) {
            alert("加入小组成功！");
            groupIdInput.value = "";

            // 刷新小组列表
            await loadMyGroups();

            // 自动切换到加入的小组
            await selectGroup(groupId);
        } else {
            alert(result.message || "加入小组失败");
        }
    } catch (error) {
        console.error("加入小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

// 加载我的小组列表
async function loadMyGroups() {
    const groupList = document.getElementById("myGroupList");

    try {
        const result = await apiGetMyGroups();

        if (result.success) {
            const groups = result.data.groups || [];

            if (groups.length === 0) {
                groupList.innerHTML = `<li class="empty-state">暂无小组<br><span style="font-size:12px">创建一个新小组或输入ID加入</span></li>`;
                return;
            }

            groupList.innerHTML = "";

            groups.forEach(group => {
                const li = document.createElement("li");
                li.className = "group-item";
                li.dataset.groupId = group.id;
                if (currentGroupId === group.id) {
                    li.classList.add("active");
                }
                li.innerHTML = `
                    <div class="group-name">${escapeHtml(group.name)}</div>
                    <div class="group-id">ID: ${group.id}</div>
                    <div class="group-meta">
                        <span>👤 ${group.member_count}人</span>
                        ${group.creator === sessionStorage.getItem("username") ? '<span style="margin-left:10px;color:#92400e">👑 组长</span>' : ''}
                    </div>
                `;
                li.onclick = () => selectGroup(group.id);
                groupList.appendChild(li);
            });
        } else {
            groupList.innerHTML = `<li class="empty-state">${result.message || "加载失败"}</li>`;
        }
    } catch (error) {
        console.error("加载小组列表错误:", error);
        document.getElementById("myGroupList").innerHTML = `<li class="empty-state">网络错误</li>`;
    }
}

// 选择小组
async function selectGroup(groupId) {
    currentGroupId = groupId;

    // 更新列表选中状态
    document.querySelectorAll(".group-item").forEach(item => {
        item.classList.remove("active");
        if (item.dataset.groupId === groupId) {
            item.classList.add("active");
        }
    });

    // 显示小组信息区域
    document.getElementById("noGroupSelected").classList.add("hidden");
    document.getElementById("currentGroupSection").classList.remove("hidden");

    // 加载小组详情
    await refreshCurrentGroup();
}

// 刷新当前小组
async function refreshCurrentGroup() {
    if (!currentGroupId) return;

    try {
        const result = await apiGetGroup(currentGroupId);

        if (result.success) {
            const group = result.data.group;
            const uploads = result.data.uploads;
            const sortedNumbers = result.data.sorted_numbers || [];
            const stats = result.data.statistics || {};
            const isCreator = result.data.is_creator;

            // 更新小组信息
            document.getElementById("currentGroupName").innerText = group.name;
            document.getElementById("currentGroupId").innerText = group.id;
            document.getElementById("groupCreator").innerText = group.creator + (isCreator ? "（你）" : "");
            document.getElementById("memberCount").innerText = group.members.length + "人";
            document.getElementById("groupCreatedAt").innerText = group.created_at;

            // 更新成员列表
            const memberList = document.getElementById("memberList");
            memberList.innerHTML = "";
            group.members.forEach(member => {
                const tag = document.createElement("span");
                tag.className = "member-tag" + (member === group.creator ? " creator" : "");
                tag.innerText = member + (member === group.creator ? " 👑" : "");
                memberList.appendChild(tag);
            });

            // 更新统计信息
            if (sortedNumbers.length > 0) {
                document.getElementById("statCount").innerText = stats.count || sortedNumbers.length;
                document.getElementById("statMax").innerText = stats.max || "-";
                document.getElementById("statMin").innerText = stats.min || "-";
                document.getElementById("statAvg").innerText = (stats.average || 0).toFixed(2);
                document.getElementById("sortedResult").innerText = sortedNumbers.join(" ");
            } else {
                document.getElementById("statCount").innerText = "0";
                document.getElementById("statMax").innerText = "-";
                document.getElementById("statMin").innerText = "-";
                document.getElementById("statAvg").innerText = "-";
                document.getElementById("sortedResult").innerText = "暂无数据，请等待成员上传文件";
            }

            // 更新上传记录
            const recordsDiv = document.getElementById("uploadRecords");
            if (uploads && uploads.length > 0) {
                recordsDiv.innerHTML = "";
                const currentUsername = sessionStorage.getItem("username");
                uploads.forEach(record => {
                    const div = document.createElement("div");
                    div.className = "record-item";
                    const isOwnRecord = record.username === currentUsername;
                    div.innerHTML = `
                        <div>
                            <span class="record-user">${escapeHtml(record.username)}</span>
                            <span class="record-count">上传了 ${record.count} 个数字</span>
                        </div>
                        <div class="record-actions">
                            <span class="record-time">${record.timestamp}</span>
                            ${isOwnRecord ? `<button class="btn-delete-record" onclick="deleteMyUpload()">删除</button>` : ''}
                        </div>
                    `;
                    recordsDiv.appendChild(div);
                });
            } else {
                recordsDiv.innerHTML = '<div class="empty-state">暂无上传记录</div>';
            }

            // 显示/隐藏操作按钮
            if (isCreator) {
                document.getElementById("leaveGroupBtn").classList.add("hidden");
                document.getElementById("deleteGroupBtn").classList.remove("hidden");
            } else {
                document.getElementById("leaveGroupBtn").classList.remove("hidden");
                document.getElementById("deleteGroupBtn").classList.add("hidden");
            }

        } else {
            if (result.message.includes("不是该小组成员")) {
                // 已被移出小组
                alert("你已不再是该小组成员");
                currentGroupId = null;
                document.getElementById("noGroupSelected").classList.remove("hidden");
                document.getElementById("currentGroupSection").classList.add("hidden");
                await loadMyGroups();
            } else {
                alert(result.message || "获取小组信息失败");
            }
        }
    } catch (error) {
        console.error("刷新小组信息错误:", error);
    }
}

// 退出当前小组
async function leaveCurrentGroup() {
    if (!currentGroupId) return;

    if (!confirm("确定要退出当前小组吗？你上传的数据将被移除。")) {
        return;
    }

    try {
        const result = await apiLeaveGroup(currentGroupId);

        if (result.success) {
            alert("已退出小组");
            currentGroupId = null;
            document.getElementById("noGroupSelected").classList.remove("hidden");
            document.getElementById("currentGroupSection").classList.add("hidden");
            await loadMyGroups();
        } else {
            alert(result.message || "退出小组失败");
        }
    } catch (error) {
        console.error("退出小组错误:", error);
        alert("网络错误");
    }
}

// 解散当前小组
async function deleteCurrentGroup() {
    if (!currentGroupId) return;

    if (!confirm("确定要解散当前小组吗？此操作不可恢复，所有数据将被删除！")) {
        return;
    }

    try {
        const result = await apiDeleteGroup(currentGroupId);

        if (result.success) {
            alert("小组已解散");
            currentGroupId = null;
            document.getElementById("noGroupSelected").classList.remove("hidden");
            document.getElementById("currentGroupSection").classList.add("hidden");
            await loadMyGroups();
        } else {
            alert(result.message || "解散小组失败");
        }
    } catch (error) {
        console.error("解散小组错误:", error);
        alert("网络错误");
    }
}

// ==================== 文件上传功能 ====================

let selectedFile = null;

// 处理文件选择
function handleGroupFileUpload(input) {
    const file = input.files[0];
    const uploadBtn = document.getElementById("groupUploadBtn");

    if (file) {
        if (!file.name.endsWith('.txt')) {
            alert('只支持 .txt 文件');
            input.value = '';
            selectedFile = null;
            uploadBtn.disabled = true;
            return;
        }
        selectedFile = file;
        uploadBtn.disabled = false;
        uploadBtn.textContent = `上传 ${file.name}`;
    }
}

// 上传文件到小组
async function uploadGroupFile() {
    if (!currentGroupId) {
        alert("请先选择一个小组");
        return;
    }

    if (!selectedFile) {
        alert("请先选择文件");
        return;
    }

    const uploadBtn = document.getElementById("groupUploadBtn");
    uploadBtn.disabled = true;
    uploadBtn.textContent = "上传中...";

    try {
        const result = await apiGroupUpload(currentGroupId, selectedFile);

        if (result.success) {
            // 清空文件选择
            document.getElementById("groupFileInput").value = "";
            selectedFile = null;
            uploadBtn.disabled = true;
            uploadBtn.textContent = "上传并合并排序";

            // 刷新小组信息
            await refreshCurrentGroup();

            // 提示上传成功
            alert(`上传成功！共上传 ${result.data.upload_count} 个数字`);
        } else {
            alert(result.message || "文件上传失败");
            uploadBtn.disabled = false;
            uploadBtn.textContent = "上传并合并排序";
        }
    } catch (error) {
        console.error("文件上传错误:", error);
        alert("网络错误，请检查后端是否启动");
        uploadBtn.disabled = false;
        uploadBtn.textContent = "上传并合并排序";
    }
}

// ==================== 工具函数 ====================

// ==================== 删除上传记录 ====================

// 删除自己的上传记录
async function deleteMyUpload() {
    if (!currentGroupId) {
        alert("未选择小组");
        return;
    }

    if (!confirm("确定要删除你的上传记录吗？删除后可重新上传文件。")) {
        return;
    }

    try {
        const result = await apiDeleteGroupUpload(currentGroupId);

        if (result.success) {
            alert("上传记录已删除");
            // 刷新小组信息
            await refreshCurrentGroup();
        } else {
            alert(result.message || "删除失败");
        }
    } catch (error) {
        console.error("删除上传记录错误:", error);
        alert("网络错误");
    }
}

// HTML转义
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 页面加载 ====================
window.addEventListener("load", initPage);

// 页面卸载时清除定时器
window.addEventListener("beforeunload", () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
