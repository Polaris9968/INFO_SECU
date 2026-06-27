// ==================== 全局变量 ====================
let currentPSIMatchGroupId = null;
let psiMatchRefreshInterval = null;
let uploadedMyMatchFile = false;
let uploadedOtherMatchFile = false;

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

    await loadMyPSIMatchGroups();
    startPSIMatchAutoRefresh();
}

// ==================== 自动刷新 ====================
function startPSIMatchAutoRefresh() {
    if (psiMatchRefreshInterval) {
        clearInterval(psiMatchRefreshInterval);
    }

    psiMatchRefreshInterval = setInterval(async () => {
        await loadMyPSIMatchGroups();
        if (currentPSIMatchGroupId) {
            await refreshCurrentPSIMatchGroup();
        }
    }, 3000);
}

// ==================== 匹配小组管理功能 ====================

async function createPSIMatchGroup() {
    const groupNameInput = document.getElementById("psiMatchGroupNameInput");
    const groupName = groupNameInput.value.trim();

    if (!groupName) {
        alert("请输入小组名称");
        return;
    }

    try {
        const result = await apiCreatePSIMatchGroup(groupName);

        if (result.success) {
            alert(`匹配小组创建成功！\n小组ID: ${result.data.group.id}\n请分享ID给对方加入`);
            groupNameInput.value = "";
            await loadMyPSIMatchGroups();
            await selectPSIMatchGroup(result.data.group.id);
        } else {
            alert(result.message || "创建匹配小组失败");
        }
    } catch (error) {
        console.error("创建匹配小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function joinPSIMatchGroup() {
    const groupIdInput = document.getElementById("psiMatchGroupIdInput");
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
        const result = await apiJoinPSIMatchGroup(groupId);

        if (result.success) {
            alert("加入匹配小组成功！");
            groupIdInput.value = "";
            await loadMyPSIMatchGroups();
            await selectPSIMatchGroup(groupId);
        } else {
            alert(result.message || "加入匹配小组失败");
        }
    } catch (error) {
        console.error("加入匹配小组错误:", error);
        alert("网络错误，请检查后端是否启动");
    }
}

async function loadMyPSIMatchGroups() {
    const groupList = document.getElementById("myPSIMatchGroupList");

    try {
        const result = await apiGetMyPSIMatchGroups();

        if (result.success) {
            const groups = result.data.groups || [];

            if (groups.length === 0) {
                groupList.innerHTML = `<li class="empty-state">暂无匹配小组<br><span style="font-size:12px">创建一个新小组或输入ID加入</span></li>`;
                return;
            }

            groupList.innerHTML = "";

            groups.forEach(group => {
                const li = document.createElement("li");
                li.className = "group-item";
                li.dataset.groupId = group.id;
                if (currentPSIMatchGroupId === group.id) {
                    li.classList.add("active");
                }
                li.innerHTML = `
                    <div class="group-name">${escapeHtml(group.name)}</div>
                    <div class="group-id">ID: ${group.id}</div>
                    <div class="group-meta">
                        <span>🔒 ${group.member_count}人</span>
                        ${group.creator === sessionStorage.getItem("username") ? '<span style="margin-left:10px;color:#92400e">👑 组长</span>' : ''}
                    </div>
                `;
                li.onclick = () => selectPSIMatchGroup(group.id);
                groupList.appendChild(li);
            });
        } else {
            groupList.innerHTML = `<li class="empty-state">${result.message || "加载失败"}</li>`;
        }
    } catch (error) {
        console.error("加载匹配小组列表错误:", error);
        document.getElementById("myPSIMatchGroupList").innerHTML = `<li class="empty-state">网络错误</li>`;
    }
}

async function selectPSIMatchGroup(groupId) {
    currentPSIMatchGroupId = groupId;

    document.querySelectorAll(".group-item").forEach(item => {
        item.classList.remove("active");
        if (item.dataset.groupId === groupId) {
            item.classList.add("active");
        }
    });

    document.getElementById("noPSIMatchGroupSelected").classList.add("hidden");
    document.getElementById("currentPSIMatchGroupSection").classList.remove("hidden");

    uploadedMyMatchFile = false;
    uploadedOtherMatchFile = false;

    await refreshCurrentPSIMatchGroup();
}

async function refreshCurrentPSIMatchGroup() {
    if (!currentPSIMatchGroupId) return;

    try {
        const result = await apiGetPSIMatchGroup(currentPSIMatchGroupId);

        if (result.success) {
            const group = result.data.group;
            const myUpload = result.data.my_upload;
            const otherUpload = result.data.other_upload;
            const subsetResult = result.data.subset_result;

            document.getElementById("currentPSIMatchGroupName").innerText = group.name;
            document.getElementById("currentPSIMatchGroupId").innerText = group.id;
            document.getElementById("psiMatchGroupCreator").innerText = group.creator + (group.creator === sessionStorage.getItem("username") ? "（你）" : "");
            document.getElementById("psiMatchGroupCreatedAt").innerText = group.created_at;

            // 更新成员列表
            const memberList = document.getElementById("psiMatchMemberList");
            memberList.innerHTML = "";
            group.members.forEach(member => {
                const tag = document.createElement("span");
                tag.className = "member-tag" + (member === group.creator ? " creator" : "");
                tag.innerText = member + (member === group.creator ? " 👑" : "");
                memberList.appendChild(tag);
            });

            // 更新上传按钮
            const uploadBtn = document.getElementById("psiMatchUploadBtn");
            if (myUpload) {
                uploadBtn.disabled = true;
                uploadBtn.textContent = "✓ 已上传";
                uploadedMyMatchFile = true;
            } else {
                uploadBtn.disabled = false;
                uploadBtn.textContent = "上传并判断子集";
                uploadedMyMatchFile = false;
            }

            document.getElementById("myMatchElementsCount").innerText = myUpload ? myUpload.count : "0";
            document.getElementById("otherMatchElementsCount").innerText = otherUpload ? otherUpload.count : "0";

            // 己方明文前 20（上传后始终显示）
            if (myUpload && myUpload.items && myUpload.items.length > 0) {
                const items = myUpload.items;
                document.getElementById("matchMyPlaintext").innerText =
                    items.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (items.length > 20 ? `\n... 合计 ${items.length} 个` : '');
                document.getElementById("matchMyPlaintextContainer").style.display = 'block';
            } else {
                document.getElementById("matchMyPlaintextContainer").style.display = 'none';
            }

            // 显示子集判断结果
            if (subsetResult && subsetResult.isSubset !== undefined) {
                const resultText = subsetResult.isSubset
                    ? '✅ A 是 B 的子集'
                    : '❌ A 不是 B 的子集';
                document.getElementById("subsetMatchResult").innerText = resultText;
                document.getElementById("intersectionCardinalityCount").innerText = subsetResult.intersectionCardinality || 0;
                document.getElementById("missingMatchElementsCount").innerText = subsetResult.missingCount || 0;
                document.getElementById("psiMatchResultCard").style.display = 'block';
                document.getElementById("matchResultContainer").style.display = 'block';
                // PSI-Card OPRF 密文预览（异步拿）
                loadPSIMatchCiphertextPreview();
            } else {
                document.getElementById("subsetMatchResult").innerText = "等待双方上传文件...";
                document.getElementById("intersectionCardinalityCount").innerText = "0";
                document.getElementById("missingMatchElementsCount").innerText = "0";
                document.getElementById("psiMatchResultCard").style.display = 'block';
                document.getElementById("matchResultContainer").style.display = 'block';
                document.getElementById("matchCiphertextContainer").style.display = 'none';
            }

            // 更新上传记录
            const recordsDiv = document.getElementById("psiMatchUploadRecords");
            const allUploads = group.uploads || [];
            if (allUploads.length > 0) {
                recordsDiv.innerHTML = "";
                const currentUsername = sessionStorage.getItem("username");
                allUploads.forEach(record => {
                    const div = document.createElement("div");
                    div.className = "record-item";
                    const isOwnRecord = record.username === currentUsername;
                    div.innerHTML = `
                        <div>
                            <span class="record-user">${escapeHtml(record.username)}</span>
                            <span class="record-count">上传了 ${record.count} 个元素</span>
                        </div>
                        <div class="record-actions">
                            <span class="record-time">${record.timestamp}</span>
                            ${isOwnRecord ? `<button class="btn-delete-record" onclick="deleteMyMatchUpload()">删除</button>` : ''}
                        </div>
                    `;
                    recordsDiv.appendChild(div);
                });
            } else {
                recordsDiv.innerHTML = '<div class="empty-state">暂无上传记录</div>';
            }

            // 显示/隐藏操作按钮
            if (group.creator === sessionStorage.getItem("username")) {
                document.getElementById("leavePSIMatchGroupBtn").classList.add("hidden");
                document.getElementById("deletePSIMatchGroupBtn").classList.remove("hidden");
            } else {
                document.getElementById("leavePSIMatchGroupBtn").classList.remove("hidden");
                document.getElementById("deletePSIMatchGroupBtn").classList.add("hidden");
            }

        } else {
            if (result.message && result.message.includes("不是该小组成员")) {
                alert("你已不再是该小组成员");
                currentPSIMatchGroupId = null;
                document.getElementById("noPSIMatchGroupSelected").classList.remove("hidden");
                document.getElementById("currentPSIMatchGroupSection").classList.add("hidden");
                await loadMyPSIMatchGroups();
            } else {
                alert(result.message || "获取匹配小组信息失败");
            }
        }
    } catch (error) {
        console.error("刷新匹配小组信息错误:", error);
    }
}

async function leaveCurrentPSIMatchGroup() {
    if (!currentPSIMatchGroupId) return;

    if (!confirm("确定要退出当前匹配小组吗？")) {
        return;
    }

    try {
        const result = await apiLeavePSIMatchGroup(currentPSIMatchGroupId);

        if (result.success) {
            alert("已退出匹配小组");
            currentPSIMatchGroupId = null;
            document.getElementById("noPSIMatchGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIMatchGroupSection").classList.add("hidden");
            await loadMyPSIMatchGroups();
        } else {
            alert(result.message || "退出匹配小组失败");
        }
    } catch (error) {
        console.error("退出匹配小组错误:", error);
        alert("网络错误");
    }
}

async function deleteCurrentPSIMatchGroup() {
    if (!currentPSIMatchGroupId) return;

    if (!confirm("确定要解散当前匹配小组吗？此操作不可恢复，所有数据将被删除！")) {
        return;
    }

    try {
        const result = await apiDeletePSIMatchGroup(currentPSIMatchGroupId);

        if (result.success) {
            alert("匹配小组已解散");
            currentPSIMatchGroupId = null;
            document.getElementById("noPSIMatchGroupSelected").classList.remove("hidden");
            document.getElementById("currentPSIMatchGroupSection").classList.add("hidden");
            await loadMyPSIMatchGroups();
        } else {
            alert(result.message || "解散匹配小组失败");
        }
    } catch (error) {
        console.error("解散匹配小组错误:", error);
        alert("网络错误");
    }
}

// ==================== 文件上传功能 ====================

let selectedPSIMatchFile = null;

function handlePSIMatchFileUpload(input) {
    const file = input.files[0];
    const uploadBtn = document.getElementById("psiMatchUploadBtn");

    if (file) {
        if (!file.name.endsWith('.txt')) {
            alert('只支持 .txt 文件');
            input.value = '';
            selectedPSIMatchFile = null;
            uploadBtn.disabled = true;
            return;
        }
        selectedPSIMatchFile = file;
        uploadBtn.disabled = false;
        uploadBtn.textContent = `上传 ${file.name}`;
    }
}

async function uploadPSIMatchFile() {
    if (!currentPSIMatchGroupId) {
        alert("请先选择一个匹配小组");
        return;
    }

    if (!selectedPSIMatchFile) {
        alert("请先选择文件");
        return;
    }

    const uploadBtn = document.getElementById("psiMatchUploadBtn");
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="loading-spinner"></span> 上传中...';

    try {
        const result = await apiPSIMatchUpload(currentPSIMatchGroupId, selectedPSIMatchFile);

        if (result.success) {
            document.getElementById("psiMatchFileInput").value = "";
            selectedPSIMatchFile = null;
            uploadBtn.disabled = true;
            uploadBtn.textContent = "✓ 已上传";

            await refreshCurrentPSIMatchGroup();

            if (result.data.subset_completed) {
                alert(`子集判断完成！\n${result.data.is_subset ? '✅ A 是 B 的子集' : '❌ A 不是 B 的子集'}`);
            } else {
                alert(`上传成功！共上传 ${result.data.upload_count} 个元素，等待对方上传...`);
            }
        } else {
            alert(result.message || "文件上传失败");
            uploadBtn.disabled = false;
            uploadBtn.textContent = "上传并判断子集";
        }
    } catch (error) {
        console.error("文件上传错误:", error);
        alert("网络错误，请检查后端是否启动");
        uploadBtn.disabled = false;
        uploadBtn.textContent = "上传并判断子集";
    }
}

// ==================== 删除上传记录 ====================

async function deleteMyMatchUpload() {
    if (!currentPSIMatchGroupId) return;

    if (!confirm("确定要删除你的上传记录吗？删除后可重新上传文件。")) {
        return;
    }

    try {
        const result = await apiDeletePSIMatchUpload(currentPSIMatchGroupId);

        if (result.success) {
            alert("上传记录已删除");
            await refreshCurrentPSIMatchGroup();
        } else {
            alert(result.message || "删除失败");
        }
    } catch (error) {
        console.error("删除上传记录错误:", error);
        alert("网络错误");
    }
}

// ==================== 密文预览（PSI-Card OPRF）====================
async function loadPSIMatchCiphertextPreview() {
    if (!currentPSIMatchGroupId) return;
    try {
        const result = await apiPSIMatchPreviewCiphertext(currentPSIMatchGroupId);
        if (result.success) {
            const ct = result.data.ciphertext;
            const role = result.data.role;
            const total = result.data.total_count;
            document.getElementById("matchCiphertext").innerText =
                `[身份: ${role === 'receiver' ? '接收方 (组长)' : '发送方 (成员)'}]\n` +
                ct.map((line, i) => `${i + 1}. ${line}`).join('\n') +
                (total > 20 ? `\n... 合计 ${total} 个` : '');
            document.getElementById("matchCiphertextContainer").style.display = 'block';
        }
    } catch (e) {
        console.warn('加载密文预览失败:', e);
    }
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
    if (psiMatchRefreshInterval) {
        clearInterval(psiMatchRefreshInterval);
    }
});