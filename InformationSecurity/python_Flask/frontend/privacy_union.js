// ==================== 全局变量 ====================
let currentPSIUnionGroupId = null;
let psiUnionRefreshInterval = null;
let uploadedMyUnionFile = false;
let uploadedOtherUnionFile = false;

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

    await loadMyPSIUnionGroups();

    // 恢复之前选择的小组（刷新页面后仍能看到结果）
    const savedGroupId = sessionStorage.getItem("current_psu_group_id");
    if (savedGroupId) {
        currentPSIUnionGroupId = savedGroupId;
        await refreshCurrentPSIUnionGroup();
    }

    startPSIUnionAutoRefresh();
}

// ==================== 自动刷新 ====================
function startPSIUnionAutoRefresh() {
    if (psiUnionRefreshInterval) {
        clearInterval(psiUnionRefreshInterval);
    }

    psiUnionRefreshInterval = setInterval(async () => {
        await loadMyPSIUnionGroups();
        if (currentPSIUnionGroupId) {
            await refreshCurrentPSIUnionGroup();
        }
    }, 3000);
}

// ==================== 求并小组管理功能 ====================

async function createPSIUnionGroup() {
    const groupNameInput = document.getElementById("psiUnionGroupNameInput");
    const groupName = groupNameInput.value.trim();

    if (!groupName) {
        alert("请输入小组名称");
        return;
    }

    try {
        const result = await apiCreatePSIUnionGroup(groupName);

        if (result.success) {
            alert(`求并小组创建成功！\n小组ID: ${result.data.group.id}\n请分享ID给对方加入`);
            groupNameInput.value = "";
            await loadMyPSIUnionGroups();
            await selectPSIUnionGroup(result.data.group.id);
        } else {
            alert(result.message || "创建求并小组失败");
        }
    } catch (error) {
        console.error("创建求并小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function joinPSIUnionGroup() {
    const groupIdInput = document.getElementById("psiUnionGroupIdInput");
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
        const result = await apiJoinPSIUnionGroup(groupId);

        if (result.success) {
            alert("加入求并小组成功！");
            groupIdInput.value = "";
            await loadMyPSIUnionGroups();
            await selectPSIUnionGroup(groupId);
        } else {
            alert(result.message || "加入求并小组失败");
        }
    } catch (error) {
        console.error("加入求并小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function loadMyPSIUnionGroups() {
    const groupList = document.getElementById("myPSIUnionGroupList");

    try {
        const result = await apiGetMyPSIUnionGroups();

        if (result.success) {
            const groups = result.data.groups || [];

            if (groups.length === 0) {
                groupList.innerHTML = `<li class="empty-state">暂无求并小组<br><span style="font-size:12px">创建一个新小组或输入ID加入</span></li>`;
                return;
            }

            groupList.innerHTML = "";

            groups.forEach(group => {
                const li = document.createElement("li");
                li.className = "psi-group-item";
                li.dataset.groupId = group.id;
                if (currentPSIUnionGroupId === group.id) {
                    li.classList.add("active");
                }
                li.innerHTML = `
                    <div class="psi-group-name">${escapeHtml(group.name)}</div>
                    <div class="psi-group-id">ID: ${group.id}</div>
                    <div class="psi-group-meta">
                        <span>🔓 ${group.member_count}人</span>
                        ${group.creator === sessionStorage.getItem("username") ? '<span style="margin-left:10px;color:#92400e">👑 组长</span>' : ''}
                    </div>
                `;
                li.onclick = () => selectPSIUnionGroup(group.id);
                groupList.appendChild(li);
            });
        } else {
            groupList.innerHTML = `<li class="empty-state">${result.message || "加载失败"}</li>`;
        }
    } catch (error) {
        console.error("加载求并小组列表错误:", error);
        document.getElementById("myPSIUnionGroupList").innerHTML = `<li class="empty-state">网络错误</li>`;
    }
}

async function selectPSIUnionGroup(groupId) {
    currentPSIUnionGroupId = groupId;
    sessionStorage.setItem("current_psu_group_id", groupId);

    document.querySelectorAll(".psi-group-item").forEach(item => {
        item.classList.remove("active");
        if (item.dataset.groupId === groupId) {
            item.classList.add("active");
        }
    });

    document.getElementById("noPSIUnionGroupSelected").classList.add("hidden");
    document.getElementById("currentPSIUnionGroupSection").classList.remove("hidden");

    uploadedMyUnionFile = false;
    uploadedOtherUnionFile = false;

    await refreshCurrentPSIUnionGroup();
}

async function refreshCurrentPSIUnionGroup() {
    if (!currentPSIUnionGroupId) return;

    try {
        const result = await apiGetPSIUnionGroup(currentPSIUnionGroupId);

        if (result.success) {
            const group = result.data.group;
            const myUpload = result.data.my_upload;
            const otherUpload = result.data.other_upload;
            const unionResult = result.data.union_result;

            document.getElementById("currentPSIUnionGroupName").innerText = group.name;
            document.getElementById("currentPSIUnionGroupId").innerText = group.id;
            document.getElementById("psiUnionGroupCreator").innerText = group.creator + (group.creator === sessionStorage.getItem("username") ? "（你）" : "");
            document.getElementById("psiUnionGroupCreatedAt").innerText = group.created_at;

            // 更新成员状态
            updateUnionMemberStatus(myUpload, otherUpload);

            const uploadBtn = document.getElementById("psiUnionUploadBtn");
            if (myUpload) {
                uploadBtn.disabled = true;
                uploadBtn.textContent = "✓ 已上传";
                uploadedMyUnionFile = true;
            } else {
                uploadBtn.disabled = false;
                uploadBtn.textContent = "上传文件";
                uploadedMyUnionFile = false;
            }

            document.getElementById("myUnionElementsCount").innerText = myUpload ? myUpload.count : "0";
            document.getElementById("otherUnionElementsCount").innerText = otherUpload ? otherUpload.count : "0";

            // 检查是否有并集结果
            if (unionResult && unionResult.length > 0) {
                document.getElementById("unionElementsCount").innerText = unionResult.length;
                document.getElementById("unionCompletionRate").innerText = "100%";
                document.getElementById("psiUnionResultCard").style.display = 'block';

                // 并集前 20 个（一列一个带编号）
                document.getElementById("psuUnionPreview").innerText =
                    unionResult.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (unionResult.length > 20 ? `\n... 合计 ${unionResult.length} 个` : '');
                document.getElementById("psuUnionPreviewContainer").style.display = 'block';

                // 下载按钮
                document.getElementById("psuDownloadBtn").style.display = 'inline-block';

                // 密文前 20（异步拿）
                loadPSUCiphertextPreview();
            } else {
                document.getElementById("unionElementsCount").innerText = "0";
                document.getElementById("unionCompletionRate").innerText = "0%";
                document.getElementById("psuUnionPreviewContainer").style.display = 'none';
                document.getElementById("psuCiphertextPreviewContainer").style.display = 'none';
                document.getElementById("psuDownloadBtn").style.display = 'none';
            }

            // 明文前 20（只要 myUpload 有 items 就显示）
            if (myUpload && myUpload.items && myUpload.items.length > 0) {
                const items = myUpload.items;
                document.getElementById("psuPlaintextPreview").innerText =
                    items.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (items.length > 20 ? `\n... 合计 ${items.length} 个` : '');
                document.getElementById("psuPlaintextPreviewContainer").style.display = 'block';
            } else {
                document.getElementById("psuPlaintextPreviewContainer").style.display = 'none';
            }

            // 显示/隐藏操作按钮
            if (group.creator === sessionStorage.getItem("username")) {
                document.getElementById("leavePSIUnionGroupBtn").classList.add("hidden");
                document.getElementById("deletePSIUnionGroupBtn").classList.remove("hidden");
                if (myUpload) {
                    document.getElementById("deleteMyUnionUploadBtn").classList.remove("hidden");
                } else {
                    document.getElementById("deleteMyUnionUploadBtn").classList.add("hidden");
                }
            } else {
                document.getElementById("leavePSIUnionGroupBtn").classList.remove("hidden");
                document.getElementById("deletePSIUnionGroupBtn").classList.add("hidden");
                if (myUpload) {
                    document.getElementById("deleteMyUnionUploadBtn").classList.remove("hidden");
                } else {
                    document.getElementById("deleteMyUnionUploadBtn").classList.add("hidden");
                }
            }

        } else {
            if (result.message && (result.message.includes("不存在") || result.message.includes("404"))) {
                console.log("小组已解散，停止自动刷新");
                currentPSIUnionGroupId = null;
                sessionStorage.removeItem("current_psu_group_id");
                document.getElementById("noPSIUnionGroupSelected").classList.remove("hidden");
                document.getElementById("currentPSIUnionGroupSection").classList.add("hidden");
                await loadMyPSIUnionGroups();
                // 停止自动刷新
                if (psiUnionRefreshInterval) {
                    clearInterval(psiUnionRefreshInterval);
                    psiUnionRefreshInterval = null;
                }
            } else {
                alert(result.message || "获取求并小组信息失败");
            }
        }
    } catch (error) {
        console.error("刷新求并小组信息错误:", error);
    }
}

function updateUnionMemberStatus(myUpload, otherUpload) {
    const memberStatusList = document.getElementById("unionMemberStatusList");
    const progressFill = document.getElementById("unionProgressFill");
    const progressText = document.getElementById("unionProgressText");

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

    uploadedMyUnionFile = myUpload !== null;
    uploadedOtherUnionFile = otherUpload !== null;
}

async function leaveCurrentPSIUnionGroup() {
    if (!currentPSIUnionGroupId) return;

    if (!confirm("确定要退出当前求并小组吗？")) {
        return;
    }

    try {
        const result = await apiLeavePSIUnionGroup(currentPSIUnionGroupId);

        if (result.success) {
            alert("已退出求并小组");
            currentPSIUnionGroupId = null;
            sessionStorage.removeItem("current_psu_group_id");
            document.getElementById("noPSIUnionGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIUnionGroupSection").classList.add("hidden");
            await loadMyPSIUnionGroups();
        } else {
            alert(result.message || "退出求并小组失败");
        }
    } catch (error) {
        console.error("退出求并小组错误:", error);
        alert("网络错误");
    }
}

async function deleteCurrentPSIUnionGroup() {
    if (!currentPSIUnionGroupId) return;

    if (!confirm("确定要解散当前求并小组吗？此操作不可恢复，所有数据将被删除！")) {
        return;
    }

    try {
        const result = await apiDeletePSIUnionGroup(currentPSIUnionGroupId);

        if (result.success) {
            alert("求并小组已解散");
            currentPSIUnionGroupId = null;
            sessionStorage.removeItem("current_psu_group_id");
            document.getElementById("noPSIUnionGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIUnionGroupSection").classList.add("hidden");
            await loadMyPSIUnionGroups();
        } else {
            alert(result.message || "解散求并小组失败");
        }
    } catch (error) {
        console.error("解散求并小组错误:", error);
        alert("网络错误");
    }
}

async function deleteMyUnionUpload() {
    if (!currentPSIUnionGroupId) return;

    if (!confirm("确定要删除你的上传记录吗？删除后可重新上传文件。")) {
        return;
    }

    try {
        const result = await apiDeletePSIUnionUpload(currentPSIUnionGroupId);

        if (result.success) {
            alert("上传记录已删除");
            await refreshCurrentPSIUnionGroup();
        } else {
            alert(result.message || "删除失败");
        }
    } catch (error) {
        console.error("删除上传错误:", error);
        alert("网络错误");
    }
}

// ==================== 文件上传功能 ====================

let selectedPSIUnionFile = null;

function handlePSIUnionFileUpload(input) {
    const file = input.files[0];
    const uploadBtn = document.getElementById("psiUnionUploadBtn");

    if (file) {
        if (!file.name.endsWith('.txt')) {
            alert('只支持 .txt 文件');
            input.value = '';
            selectedPSIUnionFile = null;
            uploadBtn.disabled = true;
            return;
        }
        selectedPSIUnionFile = file;
        uploadBtn.disabled = false;
        uploadBtn.textContent = `上传 ${file.name}`;
    }
}

async function uploadPSIUnionFile() {
    if (!currentPSIUnionGroupId) {
        alert("请先选择一个求并小组");
        return;
    }

    if (!selectedPSIUnionFile) {
        alert("请先选择文件");
        return;
    }

    const uploadBtn = document.getElementById("psiUnionUploadBtn");
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span> 上传中...';

    try {
        const result = await apiPSIUnionUpload(currentPSIUnionGroupId, selectedPSIUnionFile);

        if (result.success) {
            document.getElementById("psiUnionFileInput").value = "";
            selectedPSIUnionFile = null;
            uploadBtn.disabled = true;
            uploadBtn.textContent = "✓ 已上传";

            await refreshCurrentPSIUnionGroup();

            if (result.data.union_completed) {
                alert(`并集计算完成！\n并集元素数量: ${result.data.union_count}`);
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
async function loadPSUCiphertextPreview() {
    if (!currentPSIUnionGroupId) return;
    try {
        const result = await apiPSUPreviewCiphertext(currentPSIUnionGroupId);
        if (result.success) {
            const ct = result.data.ciphertext;
            const role = result.data.role;
            const total = result.data.total_count;
            document.getElementById("psuCiphertextPreview").innerText =
                `[身份: ${role === 'receiver' ? '接收方 (组长)' : '发送方 (成员)'}]\n` +
                ct.map((line, i) => `${i + 1}. ${line}`).join('\n') +
                (total > 20 ? `\n... 合计 ${total} 个` : '');
            document.getElementById("psuCiphertextPreviewContainer").style.display = 'block';
        }
    } catch (error) {
        console.error("加载密文预览错误:", error);
    }
}

function downloadPSUResult() {
    if (!currentPSIUnionGroupId) return;
    const token = sessionStorage.getItem("token");
    const url = apiPSUDownloadResultUrl(currentPSIUnionGroupId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => { if (!r.ok) throw new Error('下载失败'); return r.blob(); })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `psu_union_${currentPSIUnionGroupId}.txt`;
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
    if (psiUnionRefreshInterval) {
        clearInterval(psiUnionRefreshInterval);
    }
});