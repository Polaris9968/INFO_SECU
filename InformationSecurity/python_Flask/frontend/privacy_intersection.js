// ==================== 全局变量 ====================
let currentPSIGroupId = null;
let psiRefreshInterval = null;
let uploadedMyFile = false;
let uploadedOtherFile = false;

// ==================== 初始化检查 ====================
async function checkLogin() {
    const token = sessionStorage.getItem("token");

    if (!token) {
        window.location.href = "login_register.html";
        return false;
    }

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

    const username = sessionStorage.getItem("username");
    document.getElementById("userInfo").innerText = username;

    await loadMyPSIGroups();

    // 恢复之前选择的小组（刷新页面后仍能看到结果）
    const savedGroupId = sessionStorage.getItem("current_psi_group_id");
    if (savedGroupId) {
        currentPSIGroupId = savedGroupId;
        await refreshCurrentPSIGroup();
    }

    startPSIAutoRefresh();
}

// ==================== 自动刷新 ====================
function startPSIAutoRefresh() {
    if (psiRefreshInterval) {
        clearInterval(psiRefreshInterval);
    }

    psiRefreshInterval = setInterval(async () => {
        await loadMyPSIGroups();
        if (currentPSIGroupId) {
            await refreshCurrentPSIGroup();
        }
    }, 3000);
}

// ==================== 求交小组管理功能 ====================

async function createPSIGroup() {
    const groupNameInput = document.getElementById("psiGroupNameInput");
    const groupName = groupNameInput.value.trim();

    if (!groupName) {
        alert("请输入小组名称");
        return;
    }

    try {
        const result = await apiCreatePSIGroup(groupName);

        if (result.success) {
            alert(`求交小组创建成功！\n小组ID: ${result.data.group.id}\n请分享ID给对方加入`);
            groupNameInput.value = "";
            await loadMyPSIGroups();
            await selectPSIGroup(result.data.group.id);
        } else {
            alert(result.message || "创建求交小组失败");
        }
    } catch (error) {
        console.error("创建求交小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function joinPSIGroup() {
    const groupIdInput = document.getElementById("psiGroupIdInput");
    const groupId = groupIdInput.value.trim().toUpperCase();

    if (!groupId) {
        alert("请输入小组ID");
        return;
    }

    if (groupId.length !== 4) {
        alert("小组ID应为4位");
        return;
    }

    try {
        const result = await apiJoinPSIGroup(groupId);

        if (result.success) {
            alert("加入求交小组成功！");
            groupIdInput.value = "";
            await loadMyPSIGroups();
            await selectPSIGroup(groupId);
        } else {
            alert(result.message || "加入求交小组失败");
        }
    } catch (error) {
        console.error("加入求交小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function loadMyPSIGroups() {
    const groupList = document.getElementById("myPSIGroupList");

    try {
        const result = await apiGetMyPSIGroups();

        if (result.success) {
            const groups = result.data.groups || [];

            if (groups.length === 0) {
                groupList.innerHTML = `<li class="empty-state">暂无求交小组<br><span style="font-size:12px">创建一个新小组或输入ID加入</span></li>`;
                return;
            }

            groupList.innerHTML = "";

            groups.forEach(group => {
                const li = document.createElement("li");
                li.className = "psi-group-item";
                li.dataset.groupId = group.id;
                if (currentPSIGroupId === group.id) {
                    li.classList.add("active");
                }
                li.innerHTML = `
                    <div class="psi-group-name">${escapeHtml(group.name)}</div>
                    <div class="psi-group-id">ID: ${group.id}</div>
                    <div class="psi-group-meta">
                        <span>🔒 ${group.member_count}人</span>
                        ${group.creator === sessionStorage.getItem("username") ? '<span style="margin-left:10px;color:#92400e">👑 组长</span>' : ''}
                    </div>
                `;
                li.onclick = () => selectPSIGroup(group.id);
                groupList.appendChild(li);
            });
        } else {
            groupList.innerHTML = `<li class="empty-state">${result.message || "加载失败"}</li>`;
        }
    } catch (error) {
        console.error("加载求交小组列表错误:", error);
        document.getElementById("myPSIGroupList").innerHTML = `<li class="empty-state">网络错误</li>`;
    }
}

async function selectPSIGroup(groupId) {
    currentPSIGroupId = groupId;
    sessionStorage.setItem("current_psi_group_id", groupId);

    document.querySelectorAll(".psi-group-item").forEach(item => {
        item.classList.remove("active");
        if (item.dataset.groupId === groupId) {
            item.classList.add("active");
        }
    });

    document.getElementById("noPSIGroupSelected").classList.add("hidden");
    document.getElementById("currentPSIGroupSection").classList.remove("hidden");

    uploadedMyFile = false;
    uploadedOtherFile = false;

    await refreshCurrentPSIGroup();
}

async function refreshCurrentPSIGroup() {
    if (!currentPSIGroupId) return;

    try {
        const result = await apiGetPSIGroup(currentPSIGroupId);

        if (result.success) {
            const group = result.data.group;
            const myUpload = result.data.my_upload;
            const otherUpload = result.data.other_upload;

            document.getElementById("currentPSIGroupName").innerText = group.name;
            document.getElementById("currentPSIGroupId").innerText = group.id;
            document.getElementById("psiGroupCreator").innerText = group.creator + (group.creator === sessionStorage.getItem("username") ? "（你）" : "");
            document.getElementById("psiGroupCreatedAt").innerText = group.created_at;

            updateMemberStatus(myUpload, otherUpload);

            const uploadBtn = document.getElementById("psiUploadBtn");
            if (myUpload) {
                uploadBtn.disabled = true;
                uploadBtn.textContent = "✓ 已上传";
                uploadedMyFile = true;
            } else {
                uploadBtn.disabled = false;
                uploadBtn.textContent = "上传文件";
                uploadedMyFile = false;
            }

            document.getElementById("myElementsCount").innerText = myUpload ? myUpload.count : "0";
            document.getElementById("otherElementsCount").innerText = otherUpload ? otherUpload.count : "0";

            // 检查是否有 PSI 结果
            if (result.data.psi_result && result.data.psi_result.length > 0) {
                const psiResult = result.data.psi_result;
                document.getElementById("commonElementsCount").innerText = psiResult.length;
                document.getElementById("completionRate").innerText = "100%";
                document.getElementById("psiResultCard").style.display = 'block';

                // 交集前 20 个
                document.getElementById("psiResultPreview").innerText =
                    psiResult.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (psiResult.length > 20 ? `\n... 合计 ${psiResult.length} 个` : '');
                document.getElementById("psiResultPreviewContainer").style.display = 'block';

                // 下载按钮
                document.getElementById("psiDownloadBtn").style.display = 'inline-block';

                // 密文前 20（异步拿）
                loadPSICiphertextPreview();
            } else {
                document.getElementById("commonElementsCount").innerText = "0";
                document.getElementById("completionRate").innerText = "0%";
                document.getElementById("psiResultPreviewContainer").style.display = 'none';
                document.getElementById("psiCiphertextPreviewContainer").style.display = 'none';
                document.getElementById("psiDownloadBtn").style.display = 'none';
            }

            // 明文前 20（只要 myUpload 有 numbers 就显示）
            if (myUpload && myUpload.numbers && myUpload.numbers.length > 0) {
                const nums = myUpload.numbers;
                document.getElementById("psiPlaintextPreview").innerText =
                    nums.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (nums.length > 20 ? `\n... 合计 ${nums.length} 个` : '');
                document.getElementById("psiPlaintextPreviewContainer").style.display = 'block';
            } else {
                document.getElementById("psiPlaintextPreviewContainer").style.display = 'none';
            }

            // 显示/隐藏操作按钮
            if (group.creator === sessionStorage.getItem("username")) {
                // 组长
                document.getElementById("leavePSIGroupBtn").classList.add("hidden");
                document.getElementById("deletePSIGroupBtn").classList.remove("hidden");
                // 组长也能删除自己的上传
                if (myUpload) {
                    document.getElementById("deleteMyUploadBtn").classList.remove("hidden");
                } else {
                    document.getElementById("deleteMyUploadBtn").classList.add("hidden");
                }
            } else {
                // 普通成员
                document.getElementById("leavePSIGroupBtn").classList.remove("hidden");
                document.getElementById("deletePSIGroupBtn").classList.add("hidden");
                if (myUpload) {
                    document.getElementById("deleteMyUploadBtn").classList.remove("hidden");
                } else {
                    document.getElementById("deleteMyUploadBtn").classList.add("hidden");
                }
            }

        } else {
            if (result.message && result.message.includes("不是该小组成员")) {
                alert("你已不再是该小组成员");
                currentPSIGroupId = null;
                sessionStorage.removeItem("current_psi_group_id");
                document.getElementById("noPSIGroupSelected").classList.remove("hidden");
                document.getElementById("currentPSIGroupSection").classList.add("hidden");
                await loadMyPSIGroups();
            } else {
                alert(result.message || "获取求交小组信息失败");
            }
        }
    } catch (error) {
        console.error("刷新求交小组信息错误:", error);
    }
}

function updateMemberStatus(myUpload, otherUpload) {
    const memberStatusList = document.getElementById("memberStatusList");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");

    memberStatusList.innerHTML = "";

    const myStatus = document.createElement("div");
    myStatus.className = "member-status";
    const username = sessionStorage.getItem("username") || "我";
    myStatus.innerHTML = `
        <div class="member-info">
            <div class="member-avatar">${username.charAt(0).toUpperCase()}</div>
            <div>
                <div class="member-name">${username}</div>
                <div class="member-status-text ${myUpload ? 'uploaded' : 'not-uploaded'}">
                    ${myUpload ? '✓ 已上传' : '等待上传'}
                </div>
            </div>
        </div>
        <div class="status-indicator">
            <div class="status-dot ${myUpload ? 'ready' : 'waiting'}"></div>
            <span class="status-text">${myUpload ? '准备就绪' : '等待上传'}</span>
        </div>
    `;
    memberStatusList.appendChild(myStatus);

    const otherStatus = document.createElement("div");
    otherStatus.className = "member-status";
    otherStatus.innerHTML = `
        <div class="member-info">
            <div class="member-avatar">?</div>
            <div>
                <div class="member-name">对方</div>
                <div class="member-status-text ${otherUpload ? 'uploaded' : 'not-uploaded'}">
                    ${otherUpload ? '✓ 已上传' : '等待上传'}
                </div>
            </div>
        </div>
        <div class="status-indicator">
            <div class="status-dot ${otherUpload ? 'ready' : 'waiting'}"></div>
            <span class="status-text">${otherUpload ? '准备就绪' : '等待上传'}</span>
        </div>
    `;
    memberStatusList.appendChild(otherStatus);

    const uploadedCount = (myUpload ? 1 : 0) + (otherUpload ? 1 : 0);
    const progressPercent = (uploadedCount / 2) * 100;
    progressFill.style.width = progressPercent + "%";
    progressText.innerText = `${uploadedCount}/2 成员已上传`;

    uploadedMyFile = myUpload !== null;
    uploadedOtherFile = otherUpload !== null;
}

async function leaveCurrentPSIGroup() {
    if (!currentPSIGroupId) return;

    if (!confirm("确定要退出当前求交小组吗？")) {
        return;
    }

    try {
        const result = await apiLeavePSIGroup(currentPSIGroupId);

        if (result.success) {
            alert("已退出求交小组");
            currentPSIGroupId = null;
            sessionStorage.removeItem("current_psi_group_id");
            document.getElementById("noPSIGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIGroupSection").classList.add("hidden");
            await loadMyPSIGroups();
        } else {
            alert(result.message || "退出求交小组失败");
        }
    } catch (error) {
        console.error("退出求交小组错误:", error);
        alert("网络错误");
    }
}

async function deleteCurrentPSIGroup() {
    if (!currentPSIGroupId) return;

    if (!confirm("确定要解散当前求交小组吗？此操作不可恢复，所有数据将被删除！")) {
        return;
    }

    try {
        const result = await apiDeletePSIGroup(currentPSIGroupId);

        if (result.success) {
            alert("求交小组已解散");
            currentPSIGroupId = null;
            sessionStorage.removeItem("current_psi_group_id");
            document.getElementById("noPSIGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIGroupSection").classList.add("hidden");
            await loadMyPSIGroups();
        } else {
            alert(result.message || "解散求交小组失败");
        }
    } catch (error) {
        console.error("解散求交小组错误:", error);
        alert("网络错误");
    }
}

async function deleteMyUpload() {
    if (!currentPSIGroupId) return;

    if (!confirm("确定要删除你的上传记录吗？删除后可重新上传文件。")) {
        return;
    }

    try {
        const result = await apiDeleteUpload(currentPSIGroupId);

        if (result.success) {
            alert("上传记录已删除");
            await refreshCurrentPSIGroup();
        } else {
            alert(result.message || "删除失败");
        }
    } catch (error) {
        console.error("删除上传错误:", error);
        alert("网络错误");
    }
}

// ==================== 文件上传功能 ====================

let selectedPSIFile = null;

function handlePSIFileUpload(input) {
    const file = input.files[0];
    const uploadBtn = document.getElementById("psiUploadBtn");

    if (file) {
        if (!file.name.endsWith('.txt')) {
            alert('只支持 .txt 文件');
            input.value = '';
            selectedPSIFile = null;
            uploadBtn.disabled = true;
            return;
        }
        selectedPSIFile = file;
        uploadBtn.disabled = false;
        uploadBtn.textContent = `上传 ${file.name}`;
    }
}

async function uploadPSIFile() {
    if (!currentPSIGroupId) {
        alert("请先选择一个求交小组");
        return;
    }

    if (!selectedPSIFile) {
        alert("请先选择文件");
        return;
    }

    const uploadBtn = document.getElementById("psiUploadBtn");
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span> 上传中...';

    try {
        const result = await apiPSIUpload(currentPSIGroupId, selectedPSIFile);

        if (result.success) {
            document.getElementById("psiFileInput").value = "";
            selectedPSIFile = null;
            uploadBtn.disabled = true;
            uploadBtn.textContent = "✓ 已上传";

            await refreshCurrentPSIGroup();

            // 检查是否计算完成
            if (result.data.psi_completed) {
                alert(`PSI 计算完成！\n交集元素数量: ${result.data.intersection_count}`);
            } else {
                alert(`上传成功！共上传 ${result.data.upload_count} 个元素，等待对方上传...`);
            }
        } else {
            alert(result.message || "文件上传失败");
            uploadBtn.disabled = false;
            uploadBtn.textContent = "上传文件";
        }
    } catch (error) {
        console.error("文件上传错误:", error);
        alert("网络错误，请检查后端是否启动");
        uploadBtn.disabled = false;
        uploadBtn.textContent = "上传文件";
    }
}

// ==================== 密文预览 / 下载 ====================
async function loadPSICiphertextPreview() {
    if (!currentPSIGroupId) return;
    try {
        const result = await apiPSIPreviewCiphertext(currentPSIGroupId);
        if (result.success) {
            const ct = result.data.ciphertext;
            const role = result.data.role;
            const total = result.data.total_count;
            document.getElementById("psiCiphertextPreview").innerText =
                `[身份: ${role === 'receiver' ? '接收方 (组长)' : '发送方 (成员)'}]\n` +
                ct.map((line, i) => `${i + 1}. ${line}`).join('\n') +
                (total > 20 ? `\n... 合计 ${total} 个密文` : '');
            document.getElementById("psiCiphertextPreviewContainer").style.display = 'block';
        }
    } catch (e) {
        console.warn('加载密文预览失败:', e);
    }
}

function downloadPSIResult() {
    if (!currentPSIGroupId) return;
    const token = sessionStorage.getItem("token");
    // 带 token 的下载链接
    const url = apiPSIDownloadResultUrl(currentPSIGroupId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => { if (!r.ok) throw new Error('下载失败'); return r.blob(); })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `psi_intersection_${currentPSIGroupId}.txt`;
            a.click();
            URL.revokeObjectURL(a.href);
        })
        .catch(e => alert('下载失败：' + e.message));
}

// ==================== 工具函数 ====================

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function logout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("username");
    window.location.href = "login_register.html";
}

// ==================== 页面加载 ====================
window.addEventListener("load", initPage);

window.addEventListener("beforeunload", () => {
    if (psiRefreshInterval) {
        clearInterval(psiRefreshInterval);
    }
});