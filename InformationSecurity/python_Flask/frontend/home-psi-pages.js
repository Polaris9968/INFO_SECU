// ============================================================
// 子页面 JS 集合 (2026-07-01 从 3 个独立子页面合并)
// ============================================================
// 包含 3 个 IIFE:
//   - PSI_INT   (隐私求交)
//   - PSI_MATCH (集合匹配)
//   - PSI_UNION (隐私求并)
// 切到对应页面时,主页 showPage 会调用对应 .init()
//
// 设计要点:
//   - 所有变量/函数都被 IIFE 隔离,不会污染全局
//   - HTML onclick 调用的函数名都带子页面前缀(createPSIGroup/createPSIMatchGroup/...),
//     互相不冲突
//   - 同名函数(checkLogin/initPage/logout/escapeHtml)只在 IIFE 内可见,
//     不会覆盖主页 home.js 的同名函数

// ============================================================
// 子页面 JS: PSI_INT (IIFE 隔离,2026-07-01 重构)
// 通过 window.PSI_INT 命名空间对外暴露 init 函数
// 切到对应页面时,主页 showPage 会调用 PSI_INT.init()
// ============================================================
window.PSI_INT = (function() {
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
        // 切到详情视图(2026-07-01:两板块布局:隐藏列表,显示详情)
        document.querySelector('.psi-int-page .sidebar').style.display = 'none';
        document.querySelector('.psi-int-page .main-content').classList.add('active');
        document.getElementById('psiIntBackBtn').style.display = 'inline-block';
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

    const mode = document.getElementById("psiStandardizeMode").value;

    try {
        const result = await apiCreatePSIGroup(groupName, mode);

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

            // 2026-07-01:如果当前选中的 group 已不在列表里(被解散/被踢),静默清理
            // 避免 setInterval 持续刷已不存在的 group → 反复弹"小组不存在"alert
            if (currentPSIGroupId && !groups.some(g => g.id === currentPSIGroupId)) {
                currentPSIGroupId = null;
                sessionStorage.removeItem("current_psi_group_id");
                if (psiRefreshInterval) {
                    clearInterval(psiRefreshInterval);
                    psiRefreshInterval = null;
                }
                backToPsiIntList();
                document.getElementById("currentPSIGroupSection").classList.add("hidden");
            }

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

    // 切到详情视图(2026-07-01:两板块布局:隐藏列表,显示详情)
    document.querySelector('.psi-int-page .sidebar').style.display = 'none';
    document.querySelector('.psi-int-page .main-content').classList.add('active');
    document.getElementById('psiIntBackBtn').style.display = 'inline-block';

    uploadedMyFile = false;
    uploadedOtherFile = false;

    await refreshCurrentPSIGroup();
}

// 返回小组列表(隐私求交)
function backToPsiIntList() {
    document.querySelector('.psi-int-page .sidebar').style.display = 'block';
    document.querySelector('.psi-int-page .main-content').classList.remove('active');
    document.getElementById('psiIntBackBtn').style.display = 'none';
    // 2026-07-01:多轮历史 - 切回列表时重置 tab 到"当前操作"
    switchTab('current');
    document.getElementById('psiIntTabHistory').style.display = 'none';
    document.getElementById('psiIntHistoryCount').innerText = '0';
    // 清除轮询,避免回到列表后还在刷新已不存在的 group
    if (psiRefreshInterval) {
        clearInterval(psiRefreshInterval);
        psiRefreshInterval = null;
    }
}

// 2026-07-01:多轮历史 - tab 切换
function switchTab(tab) {
    if (tab === 'current') {
        document.getElementById('psiIntCurrentTab').style.display = 'block';
        document.getElementById('psiIntHistoryTab').style.display = 'none';
        document.getElementById('psiIntTabCurrent').classList.add('active');
        document.getElementById('psiIntTabHistory').classList.remove('active');
    } else {
        document.getElementById('psiIntCurrentTab').style.display = 'none';
        document.getElementById('psiIntHistoryTab').style.display = 'block';
        document.getElementById('psiIntTabCurrent').classList.remove('active');
        document.getElementById('psiIntTabHistory').classList.add('active');
    }
}

// 2026-07-01:多轮历史 - 加载历史
async function loadPsiIntHistory() {
    if (!currentPSIGroupId) return;
    try {
        const result = await apiGetPSIGroupHistory(currentPSIGroupId);
        if (result.success) {
            const rounds = result.data.rounds || [];
            const countEl = document.getElementById('psiIntHistoryCount');
            countEl.innerText = rounds.length;
            // tabs: 0 条时隐藏历史 tab
            if (rounds.length > 0) {
                document.getElementById('psiIntTabHistory').style.display = 'inline-block';
            } else {
                document.getElementById('psiIntTabHistory').style.display = 'none';
            }
            // 渲染列表
            const list = document.getElementById('psiIntHistoryList');
            if (rounds.length === 0) {
                list.innerHTML = '<div class="empty-state">暂无历史记录<br><span class="hint-text">点击 "💾 保存当前结果,开始下一轮" 后会出现历史</span></div>';
                return;
            }
            // 倒序(最新在最上面)
            const reversed = [...rounds].reverse();
            list.innerHTML = reversed.map(r => {
                const myCount = r.my_upload_count;
                const resultInfo = r.result;
                // 2026-07-02:展示轮次耗时
                const dur = r.computation_human ? `⏱ ${r.computation_human}` : '';
                return `
                    <div class="round-item">
                        <div class="round-header">
                            <span class="round-title">第 ${r.round} 轮</span>
                            <span class="round-meta">${r.completed_at} · 由 ${r.completed_by} 保存${dur ? ' · ' + dur : ''}</span>
                        </div>
                        <div class="round-body">
                            <span>我的明文: <strong>${myCount}</strong> 个</span>
                            <span style="margin-left: 20px;">交集元素: <strong>${resultInfo.count}</strong> 个</span>
                        </div>
                        <div class="round-actions">
                            <button class="btn btn-primary" onclick="PSI_INT.downloadRoundFile(${r.round}, 'my_plaintext')">📥 我的明文</button>
                            <button class="btn btn-primary" onclick="PSI_INT.downloadRoundFile(${r.round}, 'my_oprf')">📥 我的密文</button>
                            <button class="btn btn-success" onclick="PSI_INT.downloadRoundFile(${r.round}, 'result_with_original')">📥 交集结果(原始)</button>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('加载历史失败:', error);
    }
}

// 2026-07-01:多轮历史 - 保存当前结果,开始下一轮
async function saveAndStartNewRound() {
    if (!currentPSIGroupId) return;
    if (!confirm('确定要保存当前结果到历史,双方需要重新上传文件,开始下一轮吗?')) return;
    try {
        const result = await apiFinalizePSIRound(currentPSIGroupId);
        if (result.success) {
            alert(`✓ 第 ${result.data.round} 轮已保存到历史\n双方可重新上传文件开始第 ${result.data.round + 1} 轮`);
            // 立即清空当前结果显示(避免旧数据残留)
            document.getElementById("psiResultCard").style.display = 'none';
            document.getElementById("psiResultPreviewContainer").style.display = 'none';
            document.getElementById("psiCiphertextPreviewContainer").style.display = 'none';
            document.getElementById("psiPlaintextPreviewContainer").style.display = 'none';
            document.getElementById("psiDownloadBtn").style.display = 'none';
            document.getElementById("psiResultPreview").innerText = '';
            document.getElementById("psiPlaintextPreview").innerText = '';
            document.getElementById("psiCiphertextPreview").innerText = '';
            document.getElementById("commonElementsCount").innerText = '0';
            document.getElementById("completionRate").innerText = '0%';
            document.getElementById("myElementsCount").innerText = '0';
            document.getElementById("otherElementsCount").innerText = '0';
            // 重置上传按钮
            const uploadBtn = document.getElementById("psiUploadBtn");
            uploadBtn.disabled = false;
            uploadBtn.textContent = "上传文件";
            document.getElementById("psiFileInput").value = "";
            selectedPSIFile = null;
            uploadedMyFile = false;
            // 隐藏保存按钮
            document.getElementById("psiIntSaveRoundBtn").classList.add("hidden");
            document.getElementById("psiIntSaveRoundHint").classList.add("hidden");
            // 刷新当前 group(此时 result 已被清空,回到上传状态)
            await refreshCurrentPSIGroup();
            // 重新加载历史(tab 计数更新)
            await loadPsiIntHistory();
        } else {
            alert('保存失败: ' + (result.message || '未知错误'));
        }
    } catch (error) {
        console.error('保存轮次失败:', error);
        alert('保存失败: 网络错误');
    }
}

// 2026-07-01:多轮历史 - 下载某 round 文件
function downloadRoundFile(roundNum, type) {
    if (!currentPSIGroupId) return;
    apiDownloadPSIRoundFile(currentPSIGroupId, roundNum, type);
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
            // 2026-07-01:显示标准化方式
            const modeLabels = { 'auto': '自动（数字+文字哈希）', 'number_only': '只保留数字', 'text_all': '全部文字哈希' };
            document.getElementById("psiGroupStandardizeMode").innerText = modeLabels[group.standardize_mode || 'auto'] || group.standardize_mode || 'auto';

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

            // 检查是否有 PSI 结果 (2026-07-02:双方对称显示,破 PSO 严格化)
            if (result.data.psi_completed && (result.data.intersection_count || 0) > 0) {
                document.getElementById("commonElementsCount").innerText = result.data.intersection_count;
                document.getElementById("completionRate").innerText = "100%";
                document.getElementById("psiResultCard").style.display = 'block';

                // 交集前 20 个 — 双方都看,用 result_preview(非 receiver 独有)
                const resultPreview = result.data.result_preview || [];
                const resultFull = result.data.result_full_count || 0;
                const resultLines = resultPreview.map((it, i) => {
                    const orig = it.original;
                    return orig ? `${i + 1}. ${orig}` : `${i + 1}. ${it.value}`;
                });
                if (resultFull > resultPreview.length) {
                    resultLines.push(`... 合计 ${resultFull} 个`);
                }
                document.getElementById("psiResultPreview").innerText = resultLines.join('\n');
                document.getElementById("psiResultPreviewContainer").style.display = 'block';

                // 1 个下载按钮(sender 也看到自己那一半结果)
                document.getElementById("psiDownloadBtn").style.display = 'inline-block';

                // 密文前 20(从后端返的 my_ciphertext_preview,可能是 ciphertext run 中间文件)
                const ctPreview = result.data.my_ciphertext_preview || [];
                const ctFull = result.data.my_ciphertext_full_count || 0;
                const ctLines = ctPreview.map((v, i) => `${i + 1}. ${v}`);
                if (ctFull > ctPreview.length) ctLines.push(`... 合计 ${ctFull} 个`);
                document.getElementById("psiCiphertextPreview").innerText = ctLines.join('\n');
                document.getElementById("psiCiphertextPreviewContainer").style.display = 'block';
            } else {
                document.getElementById("commonElementsCount").innerText = "0";
                document.getElementById("completionRate").innerText = "0%";
                document.getElementById("psiResultPreviewContainer").style.display = 'none';
                document.getElementById("psiResultPreview").innerText = '';
                document.getElementById("psiCiphertextPreviewContainer").style.display = 'none';
                document.getElementById("psiCiphertextPreview").innerText = '';
                document.getElementById("psiDownloadBtn").style.display = 'none';
            }

            // 明文前 20 — 用后端 my_original_preview(file 内容,不等运算)
            const opPreview = result.data.my_original_preview || [];
            const opFull = result.data.my_original_full_count || 0;
            if (opPreview.length > 0) {
                const opLines = opPreview.map((v, i) => `${i + 1}. ${v}`);
                if (opFull > opPreview.length) opLines.push(`... 合计 ${opFull} 个`);
                document.getElementById("psiPlaintextPreview").innerText = opLines.join('\n');
                document.getElementById("psiPlaintextPreviewContainer").style.display = 'block';
            } else {
                document.getElementById("psiPlaintextPreviewContainer").style.display = 'none';
                document.getElementById("psiPlaintextPreview").innerText = '';
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

            // 2026-07-01:多轮历史 - 只有 receiver (= creator=组长) 看到"保存"按钮
            // 触发条件:双方都已上传 + psi_completed(Kunlun 跑完,与交集个数无关)
            // 修复:0 交集时也能归档
            const hasResult = result.data.psi_completed === true;
            const isReceiver = group.creator === sessionStorage.getItem("username");
            const bothUploaded = myUpload && otherUpload;
            if (isReceiver && hasResult && bothUploaded) {
                document.getElementById("psiIntSaveRoundBtn").classList.remove("hidden");
                document.getElementById("psiIntSaveRoundHint").classList.add("hidden");
            } else if (!isReceiver) {
                document.getElementById("psiIntSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiIntSaveRoundHint").classList.remove("hidden");
            } else {
                document.getElementById("psiIntSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiIntSaveRoundHint").classList.add("hidden");
            }

            // 2026-07-02:receiver + 双方都上传 + 还没结果 → 显示"开始运算"按钮
            // (在独立的 psiStartComputeCard 里，不依赖 psiResultCard 的显示逻辑)
            const startBtn = document.getElementById("psiStartComputeBtn");
            const startCard = document.getElementById("psiStartComputeCard");
            if (startBtn && startCard) {
                if (isReceiver && bothUploaded && !hasResult) {
                    startCard.style.display = 'block';
                    startBtn.classList.remove("hidden");
                } else {
                    startCard.style.display = 'none';
                    startBtn.classList.add("hidden");
                }
            }

            // 2026-07-02:有结果时显示耗时(computation_human)到旧独立区 + stats 卡
            const durInfo = document.getElementById("psiDurationInfo");
            const durText = document.getElementById("psiDurationText");
            const durStatItem = document.getElementById("psiDurationStatItem");
            const durStat = document.getElementById("psiDurationStat");
            const dh = result.data.computation_human || result.data.duration_human;
            if (durInfo && durText) {
                if (hasResult && dh) {
                    durText.innerText = dh;
                    durInfo.style.display = 'block';
                } else {
                    durInfo.style.display = 'none';
                }
            }
            if (durStatItem && durStat) {
                if (hasResult && dh) {
                    durStat.innerText = dh;
                    durStatItem.style.display = '';
                } else {
                    durStatItem.style.display = 'none';
                }
            }

            // 加载历史(让 tab 按钮显示 round 数)
            await loadPsiIntHistory();

        } else {
            if (result.message && (result.message.includes("不是该小组成员") || result.message.includes("不存在"))) {
                alert("该小组已不存在或你已不是成员");
                currentPSIGroupId = null;
                sessionStorage.removeItem("current_psi_group_id");
                if (psiRefreshInterval) {
                    clearInterval(psiRefreshInterval);
                    psiRefreshInterval = null;
                }
                backToPsiIntList();
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
            backToPsiIntList();
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
            // 先清轮询再切回列表,避免轮询继续刷已删除的 group
            if (psiRefreshInterval) {
                clearInterval(psiRefreshInterval);
                psiRefreshInterval = null;
            }
            backToPsiIntList();
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
    const pathSelectorArea = document.getElementById("psiPathSelectorArea");
    const pathSelect = document.getElementById("psiJSONPathSelect");
    const pathHidden = document.getElementById("psiJSONPathInput");
    const pathSample = document.getElementById("psiPathSample");

    if (!file) {
        selectedPSIFile = null;
        uploadBtn.disabled = true;
        return;
    }
    if (!file.name.endsWith('.txt') && !file.name.endsWith('.csv') && !file.name.endsWith('.json')) {
        alert('只支持 .txt / .csv / .json 文件');
        input.value = '';
        selectedPSIFile = null;
        uploadBtn.disabled = true;
        pathSelectorArea.style.display = 'none';
        return;
    }
    selectedPSIFile = file;
    uploadBtn.disabled = false;
    uploadBtn.textContent = `上传 ${file.name}`;
    pathHidden.value = '';
    pathSample.textContent = '';

    // 2026-07-02: JSON 文件自动探测结构,不立即上传
    if (file.name.toLowerCase().endsWith('.json')) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = `🔍 探测 ${file.name} 的结构...`;
        (async () => {
            if (!currentPSIGroupId) {
                alert('请先选择小组');
                input.value = '';
                selectedPSIFile = null;
                uploadBtn.disabled = true;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const probeResult = await apiPSIProbe(currentPSIGroupId, file);
            if (!probeResult.success) {
                alert('探测失败: ' + (probeResult.message || '未知错误'));
                uploadBtn.disabled = false;
                uploadBtn.textContent = `上传 ${file.name}`;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const paths = probeResult.data.paths || [];
            if (paths.length === 0) {
                // TXT 提示 / 纯数组 / 损坏 JSON -> 提示后隐藏 select
                const msg = probeResult.data.message || '未探测到可用字段路径';
                alert(msg + '\n将由后端默认提取');
                pathSelectorArea.style.display = 'none';
                pathHidden.value = '';
            } else {
                pathSelectorArea.style.display = 'block';
                pathSelect.innerHTML = '';
                paths.forEach((p, idx) => {
                    const option = document.createElement('option');
                    option.value = p.path;
                    option.textContent = `[${p.type}] ${p.display} (示例: "${p.sample}")`;
                    option.dataset.sample = p.sample;
                    option.dataset.display = p.display;
                    pathSelect.appendChild(option);
                });
                pathHidden.value = paths[0].path;
                pathSample.textContent = `✓ ${paths.length} 个可选路径 - 默认选了第 1 个`;
                pathSelect.onchange = () => {
                    const sel = pathSelect.options[pathSelect.selectedIndex];
                    pathHidden.value = sel.value;
                    pathSample.textContent = `使用: ${sel.dataset.display} - 示例: "${sel.dataset.sample}"`;
                };
            }
            uploadBtn.disabled = false;
            uploadBtn.textContent = `上传 ${file.name}`;
        })();
    } else {
        // TXT/CSV 不需探测
        pathSelectorArea.style.display = 'none';
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
        const psiPathInput = document.getElementById('psiJSONPathInput');
        const psiPath = psiPathInput ? psiPathInput.value : '';
        const result = await apiPSIUpload(currentPSIGroupId, selectedPSIFile, psiPath);

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
    // 带 token 的下载链接 (2026-07-02:改用 download-result-with-original 译文版)
    const url = `/api/psi-group/${currentPSIGroupId}/download-result-with-original`;
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => { if (!r.ok) throw new Error('下载失败'); return r.blob(); })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `psi_intersection_${currentPSIGroupId}.txt`;
            a.click();
            URL.revokeObjectURL(a.href);
        })
        .catch(e => alert('下载失败:' + e.message));
}

// 2026-07-02:下载己方密文/明文按钮已删除(用户要求 sender 只需 1 个结果按钮)

// 2026-07-02:receiver 手动触发 PSI 运算(双方都上传后才能调,后端会检查)
async function startPSIComputation() {
    if (!currentPSIGroupId) return;
    const btn = document.getElementById("psiStartComputeBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> 计算中...';
    }
    try {
        const result = await apiStartPSIComputation(currentPSIGroupId);
        if (result.success) {
            const dur = result.data.duration_human || '';
            alert(`PSI 计算完成！\n交集元素数: ${result.data.intersection_count}${dur ? '\n耗时: ' + dur : ''}`);
            await refreshCurrentPSIGroup();
        } else {
            alert(result.message || '运算失败');
        }
    } catch (e) {
        alert('网络错误: ' + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "▶ 开始运算";
        }
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
window.addEventListener("beforeunload", () => {
    if (psiRefreshInterval) {
        clearInterval(psiRefreshInterval);
    }
});

    // 暴露给 HTML onclick 的全局函数(2026-07-01:IIFE 隔离后需要显式暴露)
    window.createPSIGroup = createPSIGroup;
    window.joinPSIGroup = joinPSIGroup;
    window.uploadPSIFile = uploadPSIFile;
    window.deleteMyUpload = deleteMyUpload;
    window.leaveCurrentPSIGroup = leaveCurrentPSIGroup;
    window.deleteCurrentPSIGroup = deleteCurrentPSIGroup;
    window.downloadPSIResult = downloadPSIResult;
    window.logout = logout;
    window.handlePSIFileUpload = handlePSIFileUpload;
    window.startPSIComputation = startPSIComputation;

    return { init: initPage, backToList: backToPsiIntList, switchTab, loadPsiIntHistory, saveAndStartNewRound, downloadRoundFile };
})();

// ============================================================
// 子页面 JS: PSI_MATCH (IIFE 隔离,2026-07-01 重构)
// 通过 window.PSI_MATCH 命名空间对外暴露 init 函数
// 切到对应页面时,主页 showPage 会调用 PSI_MATCH.init()
// ============================================================
window.PSI_MATCH = (function() {
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

    const mode = document.getElementById("psiMatchStandardizeMode").value;

    try {
        const result = await apiCreatePSIMatchGroup(groupName, mode);

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

            // 2026-07-01:同 PSI 端 — 当前 group 不在 list 里就静默清理
            if (currentPSIMatchGroupId && !groups.some(g => g.id === currentPSIMatchGroupId)) {
                currentPSIMatchGroupId = null;
                if (psiMatchRefreshInterval) {
                    clearInterval(psiMatchRefreshInterval);
                    psiMatchRefreshInterval = null;
                }
                backToPsiMatchList();
                document.getElementById("currentPSIMatchGroupSection").classList.add("hidden");
            }

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

    // 切到详情视图(2026-07-01:两板块布局:隐藏列表,显示详情)
    document.querySelector('.psi-match-page .sidebar').style.display = 'none';
    document.querySelector('.psi-match-page .main-content').classList.add('active');
    document.getElementById('psiMatchBackBtn').style.display = 'inline-block';

    uploadedMyMatchFile = false;
    uploadedOtherMatchFile = false;

    await refreshCurrentPSIMatchGroup();
}

// 返回小组列表(集合匹配)
function backToPsiMatchList() {
    document.querySelector('.psi-match-page .sidebar').style.display = 'block';
    document.querySelector('.psi-match-page .main-content').classList.remove('active');
    document.getElementById('psiMatchBackBtn').style.display = 'none';
    if (psiMatchRefreshInterval) {
        clearInterval(psiMatchRefreshInterval);
        psiMatchRefreshInterval = null;
    }
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
            // 2026-07-01:显示标准化方式
            const modeLabels2 = { 'auto': '自动（数字+文字哈希）', 'number_only': '只保留数字', 'text_all': '全部文字哈希' };
            document.getElementById("psiMatchGroupStandardizeMode").innerText = modeLabels2[group.standardize_mode || 'auto'] || group.standardize_mode || 'auto';

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

            // 己方明文前 20（上传后始终显示）— 2026-07-01:优先用 original_items
            if (myUpload && (myUpload.original_items || myUpload.items)) {
                const items = myUpload.original_items || myUpload.items;
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
                // 2026-07-02:PSIMatch 1 个下载按钮(sender 也看到自己那一半结果)
                document.getElementById("psiMatchDownloadBtn").style.display = 'inline-block';
                // PSI-Card OPRF 密文预览（异步拿）
                loadPSIMatchCiphertextPreview();
            } else {
                document.getElementById("subsetMatchResult").innerText = "等待双方上传文件...";
                document.getElementById("intersectionCardinalityCount").innerText = "0";
                document.getElementById("missingMatchElementsCount").innerText = "0";
                document.getElementById("psiMatchResultCard").style.display = 'block';
                document.getElementById("matchResultContainer").style.display = 'block';
                document.getElementById("matchCiphertextContainer").style.display = 'none';
                document.getElementById("psiMatchDownloadBtn").style.display = 'none';
            }

            // 更新上传记录（依据后端顶层字段 my_upload / other_upload）
            const recordsDiv = document.getElementById("psiMatchUploadRecords");
            const allUploads = (myUpload && otherUpload) ? [myUpload, otherUpload] : [];
            // 保持详情页面里面上传记录的刷新
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

            const hasResult = subsetResult !== null && subsetResult !== undefined && subsetResult.intersectionCardinality !== undefined;
            const isReceiver = group.creator === sessionStorage.getItem("username");
            const bothUploaded = allUploads.length >= 2;
            if (isReceiver && hasResult && bothUploaded) {
                document.getElementById("psiMatchSaveRoundBtn").classList.remove("hidden");
                document.getElementById("psiMatchSaveRoundHint").classList.add("hidden");
            } else if (!isReceiver) {
                document.getElementById("psiMatchSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiMatchSaveRoundHint").classList.remove("hidden");
            } else {
                document.getElementById("psiMatchSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiMatchSaveRoundHint").classList.add("hidden");
            }

            // 2026-07-02:PSIMatch receiver + 双方都上传 + 还没结果 → 显示"开始运算"按钮
            // (在独立卡 psiMatchStartComputeCard，不依赖 psiMatchResultCard 的显示逻辑)
            const pmStartBtn = document.getElementById("psiMatchStartComputeBtn");
            const pmStartCard = document.getElementById("psiMatchStartComputeCard");
            if (pmStartBtn && pmStartCard) {
                if (isReceiver && bothUploaded && !hasResult) {
                    pmStartCard.style.display = 'block';
                    pmStartBtn.classList.remove("hidden");
                } else {
                    pmStartCard.style.display = 'none';
                    pmStartBtn.classList.add("hidden");
                }
            }

            // 2026-07-02:有结果时显示耗时到独立区 + stats
            const pmDurInfo = document.getElementById("psiMatchDurationInfo");
            const pmDurText = document.getElementById("psiMatchDurationText");
            const pmDurStatItem = document.getElementById("psiMatchDurationStatItem");
            const pmDurStat = document.getElementById("psiMatchDurationStat");
            const pmDh = result.data.computation_human || result.data.duration_human;
            if (pmDurInfo && pmDurText) {
                if (hasResult && pmDh) {
                    pmDurText.innerText = pmDh;
                    pmDurInfo.style.display = 'block';
                } else {
                    pmDurInfo.style.display = 'none';
                }
            }
            if (pmDurStatItem && pmDurStat) {
                if (hasResult && pmDh) {
                    pmDurStat.innerText = pmDh;
                    pmDurStatItem.style.display = '';
                } else {
                    pmDurStatItem.style.display = 'none';
                }
            }

        } else {
            if (result.message && result.message.includes("不是该小组成员")) {
                alert("你已不再是该小组成员");
                currentPSIMatchGroupId = null;
                backToPsiMatchList();
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
            backToPsiMatchList();
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
            backToPsiMatchList();
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
    const pathSelectorArea = document.getElementById("psiMatchPathSelectorArea");
    const pathSelect = document.getElementById("psiMatchJSONPathSelect");
    const pathHidden = document.getElementById("psiMatchJSONPathInput");
    const pathSample = document.getElementById("psiMatchPathSample");

    if (!file) {
        selectedPSIMatchFile = null;
        uploadBtn.disabled = true;
        return;
    }
    if (!file.name.endsWith('.txt') && !file.name.endsWith('.csv') && !file.name.endsWith('.json')) {
        alert('只支持 .txt / .csv / .json 文件');
        input.value = '';
        selectedPSIMatchFile = null;
        uploadBtn.disabled = true;
        pathSelectorArea.style.display = 'none';
        return;
    }
    selectedPSIMatchFile = file;
    uploadBtn.disabled = false;
    uploadBtn.textContent = `上传 ${file.name}`;
    pathHidden.value = '';
    pathSample.textContent = '';

    // 2026-07-02: JSON 文件自动探测结构
    if (file.name.toLowerCase().endsWith('.json')) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = `🔍 探测 ${file.name} 的结构...`;
        (async () => {
            if (!currentPSIMatchGroupId) {
                alert('请先选择小组');
                input.value = '';
                selectedPSIMatchFile = null;
                uploadBtn.disabled = true;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const probeResult = await apiPSIMatchProbe(currentPSIMatchGroupId, file);
            if (!probeResult.success) {
                alert('探测失败: ' + (probeResult.message || '未知错误'));
                uploadBtn.disabled = false;
                uploadBtn.textContent = `上传 ${file.name}`;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const paths = probeResult.data.paths || [];
            if (paths.length === 0) {
                const msg = probeResult.data.message || '未探测到可用字段路径';
                alert(msg + '\n将由后端默认提取');
                pathSelectorArea.style.display = 'none';
                pathHidden.value = '';
            } else {
                pathSelectorArea.style.display = 'block';
                pathSelect.innerHTML = '';
                paths.forEach((p, idx) => {
                    const option = document.createElement('option');
                    option.value = p.path;
                    option.textContent = `[${p.type}] ${p.display} (示例: "${p.sample}")`;
                    option.dataset.sample = p.sample;
                    option.dataset.display = p.display;
                    pathSelect.appendChild(option);
                });
                pathHidden.value = paths[0].path;
                pathSample.textContent = `✓ ${paths.length} 个可选路径 - 默认选了第 1 个`;
                pathSelect.onchange = () => {
                    const sel = pathSelect.options[pathSelect.selectedIndex];
                    pathHidden.value = sel.value;
                    pathSample.textContent = `使用: ${sel.dataset.display} - 示例: "${sel.dataset.sample}"`;
                };
            }
            uploadBtn.disabled = false;
            uploadBtn.textContent = `上传 ${file.name}`;
        })();
    } else {
        pathSelectorArea.style.display = 'none';
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
        const psiMatchPathInput = document.getElementById('psiMatchJSONPathInput');
        const psiMatchPath = psiMatchPathInput ? psiMatchPathInput.value : '';
        const result = await apiPSIMatchUpload(currentPSIMatchGroupId, selectedPSIMatchFile, psiMatchPath);

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

// 2026-07-02:PSIMatch receiver 手动触发运算
async function startPSIMatchComputation() {
    if (!currentPSIMatchGroupId) return;
    const btn = document.getElementById("psiMatchStartComputeBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> 计算中...';
    }
    try {
        const result = await apiStartPSIMatchComputation(currentPSIMatchGroupId);
        if (result.success) {
            const dur = result.data.duration_human || '';
            alert(`PSIMatch 计算完成！\n交集基数: ${result.data.intersection_cardinality}${dur ? '\n耗时: ' + dur : ''}`);
            await refreshCurrentPSIMatchGroup();
        } else {
            alert(result.message || '运算失败');
        }
    } catch (e) {
        alert('网络错误: ' + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "▶ 开始运算";
        }
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

// 2026-07-02:PSIMatch 下载运算结果(按上传格式输出 .json/.csv/.txt)
function downloadPSIMatchResult() {
    if (!currentPSIMatchGroupId) return;
    const token = sessionStorage.getItem("token");
    const url = apiPSIMatchDownloadResultWithOriginalUrl(currentPSIMatchGroupId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => { if (!r.ok) throw new Error('下载失败'); return r.blob(); })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `psi_match_${currentPSIMatchGroupId}`;
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
window.addEventListener("beforeunload", () => {
    if (psiMatchRefreshInterval) {
        clearInterval(psiMatchRefreshInterval);
    }
});

    // 暴露给 HTML onclick 的全局函数
    window.createPSIMatchGroup = createPSIMatchGroup;
    window.joinPSIMatchGroup = joinPSIMatchGroup;
    window.uploadPSIMatchFile = uploadPSIMatchFile;
    window.deleteMyMatchUpload = deleteMyMatchUpload;
    window.leaveCurrentPSIMatchGroup = leaveCurrentPSIMatchGroup;
    window.deleteCurrentPSIMatchGroup = deleteCurrentPSIMatchGroup;
    window.refreshCurrentPSIMatchGroup = refreshCurrentPSIMatchGroup;
    window.logout = logout;
    window.handlePSIMatchFileUpload = handlePSIMatchFileUpload;
    window.startPSIMatchComputation = startPSIMatchComputation;
    window.downloadPSIMatchResult = downloadPSIMatchResult;

    // 多轮历史函数
    function switchTab(tab) {
        if (tab === 'current') {
            document.getElementById('psiMatchCurrentTab').style.display = 'block';
            document.getElementById('psiMatchHistoryTab').style.display = 'none';
            document.getElementById('psiMatchTabCurrent').classList.add('active');
            document.getElementById('psiMatchTabHistory').classList.remove('active');
        } else {
            document.getElementById('psiMatchCurrentTab').style.display = 'none';
            document.getElementById('psiMatchHistoryTab').style.display = 'block';
            document.getElementById('psiMatchTabCurrent').classList.remove('active');
            document.getElementById('psiMatchTabHistory').classList.add('active');
        }
    }

    async function loadPsiMatchHistory() {
        if (!currentPSIMatchGroupId) return;
        try {
            const result = await apiGetPSIMatchGroupHistory(currentPSIMatchGroupId);
            if (result.success) {
                const rounds = result.data.rounds || [];
                document.getElementById('psiMatchHistoryCount').innerText = rounds.length;
                if (rounds.length > 0) {
                    document.getElementById('psiMatchTabHistory').style.display = 'inline-block';
                } else {
                    document.getElementById('psiMatchTabHistory').style.display = 'none';
                }
                const list = document.getElementById('psiMatchHistoryList');
                if (rounds.length === 0) {
                    list.innerHTML = '<div class="empty-state">暂无历史记录<br><span class="hint-text">点击 "💾 保存当前结果,开始下一轮" 后会出现历史</span></div>';
                    return;
                }
                const reversed = [...rounds].reverse();
                list.innerHTML = reversed.map(r => {
                    const myCount = r.my_upload_count;
                    const resultInfo = r.result;
                    return `
                        <div class="round-item">
                            <div class="round-header">
                                <span class="round-title">第 ${r.round} 轮</span>
                                <span class="round-meta">${r.completed_at} · 由 ${r.completed_by} 保存</span>
                            </div>
                            <div class="round-body">
                                <span>我的明文: <strong>${myCount}</strong> 个</span>
                                <span style="margin-left: 20px;">匹配元素: <strong>${resultInfo.count}</strong> 个</span>
                            </div>
                            <div class="round-actions">
                                <button class="btn btn-primary" onclick="PSI_MATCH.downloadRoundFile(${r.round}, 'my_plaintext')">📥 我的明文</button>
                                <button class="btn btn-primary" onclick="PSI_MATCH.downloadRoundFile(${r.round}, 'my_oprf')">📥 我的密文</button>
                                <button class="btn btn-success" onclick="PSI_MATCH.downloadRoundFile(${r.round}, 'result')">📥 匹配结果</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        } catch (error) {
            console.error('加载历史失败:', error);
        }
    }

    async function saveAndStartNewRound() {
        if (!currentPSIMatchGroupId) return;
        if (!confirm('确定要保存当前结果到历史,双方需要重新上传文件,开始下一轮吗?')) return;
        try {
            const result = await apiFinalizePSIMatchRound(currentPSIMatchGroupId);
            if (result.success) {
                alert(`✓ 第 ${result.data.round} 轮已保存到历史\n双方可重新上传文件开始第 ${result.data.round + 1} 轮`);
                document.getElementById("psiMatchResultCard").style.display = 'none';
                document.getElementById("matchResultContainer").style.display = 'none';
                document.getElementById("matchCiphertextContainer").style.display = 'none';
                document.getElementById("matchCiphertext").innerText = '';
                document.getElementById("intersectionCardinalityCount").innerText = '0';
                document.getElementById("missingMatchElementsCount").innerText = '0';
                document.getElementById("psiMatchSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiMatchSaveRoundHint").classList.add("hidden");
                await refreshCurrentPSIMatchGroup();
                await loadPsiMatchHistory();
            } else {
                alert('保存失败: ' + (result.message || '未知错误'));
            }
        } catch (error) {
            console.error('保存轮次失败:', error);
            alert('保存失败: 网络错误');
        }
    }

    function downloadRoundFile(roundNum, type) {
        if (!currentPSIMatchGroupId) return;
        apiDownloadPSIMatchRoundFile(currentPSIMatchGroupId, roundNum, type);
    }

    return { init: initPage, backToList: backToPsiMatchList, switchTab, loadPsiMatchHistory, saveAndStartNewRound, downloadRoundFile };
})();

// ============================================================
// 子页面 JS: PSI_UNION (IIFE 隔离,2026-07-01 重构)
// 通过 window.PSI_UNION 命名空间对外暴露 init 函数
// 切到对应页面时,主页 showPage 会调用 PSI_UNION.init()
// ============================================================
window.PSI_UNION = (function() {
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

    // 恢复之前选择的小组(刷新页面后仍能看到结果,2026-07-01:两板块布局)
    const savedGroupId = sessionStorage.getItem("current_psu_group_id");
    if (savedGroupId) {
        currentPSIUnionGroupId = savedGroupId;
        await refreshCurrentPSIUnionGroup();
        // 切到详情视图(2026-07-01:两板块布局:隐藏列表,显示详情)
        document.querySelector('.psi-union-page .sidebar').style.display = 'none';
        document.querySelector('.psi-union-page .main-content').classList.add('active');
        document.getElementById('psiUnionBackBtn').style.display = 'inline-block';
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

    const mode = document.getElementById("psiUnionStandardizeMode").value;

    try {
        const result = await apiCreatePSIUnionGroup(groupName, mode);

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

            // 2026-07-01:同 PSI 端 — 当前 group 不在 list 里就静默清理
            if (currentPSIUnionGroupId && !groups.some(g => g.id === currentPSIUnionGroupId)) {
                currentPSIUnionGroupId = null;
                sessionStorage.removeItem("current_psu_group_id");
                if (psiUnionRefreshInterval) {
                    clearInterval(psiUnionRefreshInterval);
                    psiUnionRefreshInterval = null;
                }
                backToPsiUnionList();
                document.getElementById("currentPSIUnionGroupSection").classList.add("hidden");
            }

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

    // 切到详情视图(2026-07-01:两板块布局:隐藏列表,显示详情)
    document.querySelector('.psi-union-page .sidebar').style.display = 'none';
    document.querySelector('.psi-union-page .main-content').classList.add('active');
    document.getElementById('psiUnionBackBtn').style.display = 'inline-block';

    uploadedMyUnionFile = false;
    uploadedOtherUnionFile = false;

    await refreshCurrentPSIUnionGroup();
}

// 返回小组列表(隐私求并)
function backToPsiUnionList() {
    document.querySelector('.psi-union-page .sidebar').style.display = 'block';
    document.querySelector('.psi-union-page .main-content').classList.remove('active');
    document.getElementById('psiUnionBackBtn').style.display = 'none';
    switchTab('current');
    document.getElementById('psiUnionTabHistory').style.display = 'none';
    document.getElementById('psiUnionHistoryCount').innerText = '0';
    if (psiUnionRefreshInterval) {
        clearInterval(psiUnionRefreshInterval);
        psiUnionRefreshInterval = null;
    }
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
            // 2026-07-01:显示标准化方式
            const modeLabels3 = { 'auto': '自动（数字+文字哈希）', 'number_only': '只保留数字', 'text_all': '全部文字哈希' };
            document.getElementById("psiUnionGroupStandardizeMode").innerText = modeLabels3[group.standardize_mode || 'auto'] || group.standardize_mode || 'auto';

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

            const hasResult = result.data.union_completed === true;
            const unionCount = result.data.union_count || 0;
            if (hasResult) {
                // 并集前 20 个 — 优先 result_preview(带 original 字段)
                const resultPreview = result.data.result_preview || [];
                document.getElementById("unionElementsCount").innerText = unionCount;
                document.getElementById("unionCompletionRate").innerText = "100%";
                document.getElementById("psiUnionResultCard").style.display = 'block';

                // 并集预览:用 receiver 的 reverse_map 译码(双方对称,2026-07-02 打破 PSO 严格化)
                const unionLines = resultPreview.map((it, i) => {
                    const orig = it.original;
                    return orig ? `${i + 1}. ${orig}` : `${i + 1}. ${it.value}`;
                });
                document.getElementById("psuUnionPreview").innerText =
                    unionLines.slice(0, 20).join('\n') +
                    (unionCount > 20 ? `\n... 合计 ${unionCount} 个` : '');
                document.getElementById("psuUnionPreviewContainer").style.display = 'block';

                // 下载按钮
                document.getElementById("psuDownloadBtn").style.display = 'inline-block';

                // 密文前 20 (用后端 my_ciphertext_preview)
                const ctPreview = result.data.my_ciphertext_preview || [];
                const role = result.data.role;
                document.getElementById("psuCiphertextPreview").innerText =
                    `[身份: ${role === 'receiver' ? '接收方 (组长)' : '发送方 (成员)'}]\n` +
                    ctPreview.map((line, i) => `${i + 1}. ${line}`).join('\n') +
                    (result.data.my_ciphertext_full_count > 20 ? `\n... 合计 ${result.data.my_ciphertext_full_count} 个` : '');
                document.getElementById("psuCiphertextPreviewContainer").style.display = 'block';
            } else {
                // 2026-07-02:display:none 同时清空 innerText,防止老数据残留
                document.getElementById("unionElementsCount").innerText = "0";
                document.getElementById("unionCompletionRate").innerText = "0%";
                document.getElementById("psuUnionPreviewContainer").style.display = 'none';
                document.getElementById("psuUnionPreview").innerText = '';
                document.getElementById("psuCiphertextPreviewContainer").style.display = 'none';
                document.getElementById("psuCiphertextPreview").innerText = '';
                document.getElementById("psuDownloadBtn").style.display = 'none';
            }

            // 明文前 20 — 用后端 my_original_preview(file 内容,不等运算)
            const opPreview = result.data.my_original_preview || [];
            if (opPreview.length > 0) {
                document.getElementById("psuPlaintextPreview").innerText =
                    opPreview.slice(0, 20).map((v, i) => `${i + 1}. ${v}`).join('\n') +
                    (result.data.my_original_full_count > 20 ? `\n... 合计 ${result.data.my_original_full_count} 个` : '');
                document.getElementById("psuPlaintextPreviewContainer").style.display = 'block';
            } else {
                document.getElementById("psuPlaintextPreviewContainer").style.display = 'none';
                document.getElementById("psuPlaintextPreview").innerText = '';
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

            const isReceiver = group.creator === sessionStorage.getItem("username");
            const bothUploaded = myUpload && otherUpload;
            if (isReceiver && hasResult && bothUploaded) {
                document.getElementById("psiUnionSaveRoundBtn").classList.remove("hidden");
                document.getElementById("psiUnionSaveRoundHint").classList.add("hidden");
            } else if (!isReceiver) {
                document.getElementById("psiUnionSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiUnionSaveRoundHint").classList.remove("hidden");
            } else {
                document.getElementById("psiUnionSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiUnionSaveRoundHint").classList.add("hidden");
            }

            // 2026-07-02:PSU receiver + 双方都上传 + 还没结果 → 显示"开始运算"按钮
            // (在独立卡 psuStartComputeCard，不依赖 psiUnionResultCard 的显示逻辑)
            const psuStartBtn = document.getElementById("psuStartComputeBtn");
            const psuStartCard = document.getElementById("psuStartComputeCard");
            if (psuStartBtn && psuStartCard) {
                if (isReceiver && bothUploaded && !hasResult) {
                    psuStartCard.style.display = 'block';
                    psuStartBtn.classList.remove("hidden");
                } else {
                    psuStartCard.style.display = 'none';
                    psuStartBtn.classList.add("hidden");
                }
            }

            // 2026-07-02:有结果时显示耗时到独立区 + stats
            const psuDurInfo = document.getElementById("psuDurationInfo");
            const psuDurText = document.getElementById("psuDurationText");
            const psuDurStatItem = document.getElementById("psuDurationStatItem");
            const psuDurStat = document.getElementById("psuDurationStat");
            const psuDh = result.data.computation_human || result.data.duration_human;
            if (psuDurInfo && psuDurText) {
                if (hasResult && psuDh) {
                    psuDurText.innerText = psuDh;
                    psuDurInfo.style.display = 'block';
                } else {
                    psuDurInfo.style.display = 'none';
                }
            }
            if (psuDurStatItem && psuDurStat) {
                if (hasResult && psuDh) {
                    psuDurStat.innerText = psuDh;
                    psuDurStatItem.style.display = '';
                } else {
                    psuDurStatItem.style.display = 'none';
                }
            }

            await loadPsiUnionHistory();

        } else {
            if (result.message && (result.message.includes("不存在") || result.message.includes("404"))) {
                console.log("小组已解散，停止自动刷新");
                currentPSIUnionGroupId = null;
                sessionStorage.removeItem("current_psu_group_id");
                backToPsiUnionList();
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
            backToPsiUnionList();
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
            backToPsiUnionList();
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
    const pathSelectorArea = document.getElementById("psiUnionPathSelectorArea");
    const pathSelect = document.getElementById("psiUnionJSONPathSelect");
    const pathHidden = document.getElementById("psiUnionJSONPathInput");
    const pathSample = document.getElementById("psiUnionPathSample");

    if (!file) {
        selectedPSIUnionFile = null;
        uploadBtn.disabled = true;
        return;
    }
    if (!file.name.endsWith('.txt') && !file.name.endsWith('.csv') && !file.name.endsWith('.json')) {
        alert('只支持 .txt / .csv / .json 文件');
        input.value = '';
        selectedPSIUnionFile = null;
        uploadBtn.disabled = true;
        pathSelectorArea.style.display = 'none';
        return;
    }
    selectedPSIUnionFile = file;
    uploadBtn.disabled = false;
    uploadBtn.textContent = `上传 ${file.name}`;
    pathHidden.value = '';
    pathSample.textContent = '';

    // 2026-07-02: JSON 文件自动探测结构
    if (file.name.toLowerCase().endsWith('.json')) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = `🔍 探测 ${file.name} 的结构...`;
        (async () => {
            if (!currentPSIUnionGroupId) {
                alert('请先选择小组');
                input.value = '';
                selectedPSIUnionFile = null;
                uploadBtn.disabled = true;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const probeResult = await apiPSUUnionProbe(currentPSIUnionGroupId, file);
            if (!probeResult.success) {
                alert('探测失败: ' + (probeResult.message || '未知错误'));
                uploadBtn.disabled = false;
                uploadBtn.textContent = `上传 ${file.name}`;
                pathSelectorArea.style.display = 'none';
                return;
            }
            const paths = probeResult.data.paths || [];
            if (paths.length === 0) {
                const msg = probeResult.data.message || '未探测到可用字段路径';
                alert(msg + '\n将由后端默认提取');
                pathSelectorArea.style.display = 'none';
                pathHidden.value = '';
            } else {
                pathSelectorArea.style.display = 'block';
                pathSelect.innerHTML = '';
                paths.forEach((p, idx) => {
                    const option = document.createElement('option');
                    option.value = p.path;
                    option.textContent = `[${p.type}] ${p.display} (示例: "${p.sample}")`;
                    option.dataset.sample = p.sample;
                    option.dataset.display = p.display;
                    pathSelect.appendChild(option);
                });
                pathHidden.value = paths[0].path;
                pathSample.textContent = `✓ ${paths.length} 个可选路径 - 默认选了第 1 个`;
                pathSelect.onchange = () => {
                    const sel = pathSelect.options[pathSelect.selectedIndex];
                    pathHidden.value = sel.value;
                    pathSample.textContent = `使用: ${sel.dataset.display} - 示例: "${sel.dataset.sample}"`;
                };
            }
            uploadBtn.disabled = false;
            uploadBtn.textContent = `上传 ${file.name}`;
        })();
    } else {
        pathSelectorArea.style.display = 'none';
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
        const psiUnionPathInput = document.getElementById('psiUnionJSONPathInput');
        const psiUnionPath = psiUnionPathInput ? psiUnionPathInput.value : '';
        const result = await apiPSIUnionUpload(currentPSIUnionGroupId, selectedPSIUnionFile, psiUnionPath);

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
    // 2026-07-02:改用 download-result-with-original，按上传格式输出 .json/.csv/.txt
    const url = apiPSUDownloadResultWithOriginalUrl(currentPSIUnionGroupId);
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
        .then(r => { if (!r.ok) throw new Error('下载失败'); return r.blob(); })
        .then(blob => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            // 后端会送 Content-Disposition，浏览器会自取文件名
            a.download = `psu_union_${currentPSIUnionGroupId}`;
            a.click();
            URL.revokeObjectURL(a.href);
        })
        .catch(e => alert('下载失败：' + e.message));
}

// 2026-07-02:PSU receiver 手动触发运算
async function startPSUUnionComputation() {
    if (!currentPSIUnionGroupId) return;
    const btn = document.getElementById("psuStartComputeBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> 计算中...';
    }
    try {
        const result = await apiStartPSUUnionComputation(currentPSIUnionGroupId);
        if (result.success) {
            const dur = result.data.duration_human || '';
            alert(`PSU 计算完成！\n并集元素数: ${result.data.union_count}${dur ? '\n耗时: ' + dur : ''}`);
            await refreshCurrentPSIUnionGroup();
        } else {
            alert(result.message || '运算失败');
        }
    } catch (e) {
        alert('网络错误: ' + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "▶ 开始运算";
        }
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
window.addEventListener("beforeunload", () => {
    if (psiUnionRefreshInterval) {
        clearInterval(psiUnionRefreshInterval);
    }
});

    // 暴露给 HTML onclick 的全局函数
    window.createPSIUnionGroup = createPSIUnionGroup;
    window.joinPSIUnionGroup = joinPSIUnionGroup;
    window.uploadPSIUnionFile = uploadPSIUnionFile;
    window.deleteMyUnionUpload = deleteMyUnionUpload;
    window.leaveCurrentPSIUnionGroup = leaveCurrentPSIUnionGroup;
    window.deleteCurrentPSIUnionGroup = deleteCurrentPSIUnionGroup;
    window.downloadPSUResult = downloadPSUResult;
    window.logout = logout;
    window.handlePSIUnionFileUpload = handlePSIUnionFileUpload;
    window.startPSUUnionComputation = startPSUUnionComputation;

    // 多轮历史函数
    function switchTab(tab) {
        if (tab === 'current') {
            document.getElementById('psiUnionCurrentTab').style.display = 'block';
            document.getElementById('psiUnionHistoryTab').style.display = 'none';
            document.getElementById('psiUnionTabCurrent').classList.add('active');
            document.getElementById('psiUnionTabHistory').classList.remove('active');
        } else {
            document.getElementById('psiUnionCurrentTab').style.display = 'none';
            document.getElementById('psiUnionHistoryTab').style.display = 'block';
            document.getElementById('psiUnionTabCurrent').classList.remove('active');
            document.getElementById('psiUnionTabHistory').classList.add('active');
        }
    }

    async function loadPsiUnionHistory() {
        if (!currentPSIUnionGroupId) return;
        try {
            const result = await apiGetPSUUnionGroupHistory(currentPSIUnionGroupId);
            if (result.success) {
                const rounds = result.data.rounds || [];
                document.getElementById('psiUnionHistoryCount').innerText = rounds.length;
                if (rounds.length > 0) {
                    document.getElementById('psiUnionTabHistory').style.display = 'inline-block';
                } else {
                    document.getElementById('psiUnionTabHistory').style.display = 'none';
                }
                const list = document.getElementById('psiUnionHistoryList');
                if (rounds.length === 0) {
                    list.innerHTML = '<div class="empty-state">暂无历史记录<br><span class="hint-text">点击 "💾 保存当前结果,开始下一轮" 后会出现历史</span></div>';
                    return;
                }
                const reversed = [...rounds].reverse();
                list.innerHTML = reversed.map(r => {
                    const myCount = r.my_upload_count;
                    const resultInfo = r.result;
                    return `
                        <div class="round-item">
                            <div class="round-header">
                                <span class="round-title">第 ${r.round} 轮</span>
                                <span class="round-meta">${r.completed_at} · 由 ${r.completed_by} 保存</span>
                            </div>
                            <div class="round-body">
                                <span>我的明文: <strong>${myCount}</strong> 个</span>
                                <span style="margin-left: 20px;">并集元素: <strong>${resultInfo.count}</strong> 个</span>
                            </div>
                            <div class="round-actions">
                                <button class="btn btn-primary" onclick="PSI_UNION.downloadRoundFile(${r.round}, 'my_plaintext')">📥 我的明文</button>
                                <button class="btn btn-primary" onclick="PSI_UNION.downloadRoundFile(${r.round}, 'my_oprf')">📥 我的密文</button>
                                <button class="btn btn-success" onclick="PSI_UNION.downloadRoundFile(${r.round}, 'result_with_original')">📥 并集结果(原始)</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        } catch (error) {
            console.error('加载历史失败:', error);
        }
    }

    async function saveAndStartNewRound() {
        if (!currentPSIUnionGroupId) return;
        if (!confirm('确定要保存当前结果到历史,双方需要重新上传文件,开始下一轮吗?')) return;
        try {
            const result = await apiFinalizePSUUnionRound(currentPSIUnionGroupId);
            if (result.success) {
                alert(`✓ 第 ${result.data.round} 轮已保存到历史\n双方可重新上传文件开始第 ${result.data.round + 1} 轮`);
                document.getElementById("psiUnionResultCard").style.display = 'none';
                document.getElementById("psuUnionPreviewContainer").style.display = 'none';
                document.getElementById("psuCiphertextPreviewContainer").style.display = 'none';
                document.getElementById("psuPlaintextPreviewContainer").style.display = 'none';
                document.getElementById("psuDownloadBtn").style.display = 'none';
                document.getElementById("psuUnionPreview").innerText = '';
                document.getElementById("psuCiphertextPreview").innerText = '';
                document.getElementById("unionElementsCount").innerText = '0';
                document.getElementById("unionCompletionRate").innerText = '0%';
                document.getElementById("myUnionElementsCount").innerText = '0';
                document.getElementById("otherUnionElementsCount").innerText = '0';
                const uploadBtn = document.getElementById("psiUnionUploadBtn");
                uploadBtn.disabled = false;
                uploadBtn.textContent = "上传文件";
                document.getElementById("psiUnionFileInput").value = "";
                selectedPSIUnionFile = null;
                uploadedMyUnionFile = false;
                document.getElementById("psiUnionSaveRoundBtn").classList.add("hidden");
                document.getElementById("psiUnionSaveRoundHint").classList.add("hidden");
                await refreshCurrentPSIUnionGroup();
                await loadPsiUnionHistory();
            } else {
                alert('保存失败: ' + (result.message || '未知错误'));
            }
        } catch (error) {
            console.error('保存轮次失败:', error);
            alert('保存失败: 网络错误');
        }
    }

    function downloadRoundFile(roundNum, type) {
        if (!currentPSIUnionGroupId) return;
        apiDownloadPSUUnionRoundFile(currentPSIUnionGroupId, roundNum, type);
    }

    return { init: initPage, backToList: backToPsiUnionList, switchTab, loadPsiUnionHistory, saveAndStartNewRound, downloadRoundFile };
})();


// PSI_SUM IIFE (2026-07-07 从 mock 升级为真实接口)
// 与 PSI_INT/PSU/PSIMatch 共享同一套 UX 模板:
//   - view1: 创建 / 加入 / 我的小组列表
//   - view2: 进组后, 5 个区块: 小组信息 / 成员状态 / 上传 / 开始运算 / 预览 + 结果
// 差异: 比 PSI-Card 多一个 valueFile 输入 + 结果展示同时显示 cardinality + sum
window.PSI_SUM = (function() {
    let myGroups = [];
    let currentGroupId = null;
    let pollTimer = null;
    let pollBusy = false;
    let currentGroupDetail = null;

    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
    }

    async function loadMyGroups() {
        try {
            const result = await apiGetMyPSISumGroups();
            if (result.success) {
                myGroups = result.data.groups || [];
            } else {
                myGroups = [];
            }
        } catch (err) {
            console.error('loadMyGroups 失败:', err);
            myGroups = [];
        }
        // 如果当前选中 group 已被解散, 静默清除
        if (currentGroupId && !myGroups.some(g => g.id === currentGroupId)) {
            backToList();
        }
        renderMyGroupsList();
    }

    async function loadGroupDetail(groupId) {
        try {
            const result = await apiGetPSISumGroup(groupId);
            if (result.success) {
                return result.data;
            }
            return null;
        } catch (err) {
            console.error('loadGroupDetail 失败:', err);
            return null;
        }
    }

    function renderMyGroupsList() {
        const ul = document.getElementById('psiSumMyGroupList');
        if (!ul) return;
        if (myGroups.length === 0) {
            ul.innerHTML = '<li class="empty-state">暂无求和小组<br><span style="font-size:12px">创建一个新小组或输入ID加入</span></li>';
            return;
        }
        const username = sessionStorage.getItem('username');
        ul.innerHTML = myGroups.map(g => `
            <li class="psi-group-item${currentGroupId === g.id ? ' active' : ''}" data-group-id="${g.id}" onclick="PSI_SUM.selectGroup('${g.id}')">
                <div class="psi-group-name">${escapeHtml(g.name)}</div>
                <div class="psi-group-id">ID: ${g.id}</div>
                <div class="psi-group-meta">
                    <span>🔒 ${g.member_count}人</span>
                    ${g.creator === username ? '<span style="margin-left:10px;color:#92400e">👑 组长</span>' : ''}
                </div>
            </li>
        `).join('');
    }

    function showView1() {
        document.getElementById('psiSumView1').style.display = 'block';
        document.getElementById('psiSumView2').style.display = 'none';
    }
    function showView2() {
        document.getElementById('psiSumView1').style.display = 'none';
        document.getElementById('psiSumView2').style.display = 'block';
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(async () => {
            if (!currentGroupId || pollBusy) return;
            pollBusy = true;
            const detail = await loadGroupDetail(currentGroupId);
            pollBusy = false;
            if (detail && detail.group.id === currentGroupId) {
                currentGroupDetail = detail;
                renderFromDetail();
            }
        }, 2000);
    }
    function stopPolling() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    async function init() {
        currentGroupId = null;
        currentGroupDetail = null;
        stopPolling();
        showView1();
        await loadMyGroups();
    }

    async function createGroup() {
        const nameInput = document.getElementById('psiSumGroupNameInput');
        const name = (nameInput.value || '').trim();
        if (!name) { alert('请输入小组名称'); return; }
        const modeEl = document.getElementById('psiSumStandardizeMode');
        const mode = modeEl ? modeEl.value : 'auto';
        try {
            const result = await apiCreatePSISumGroup(name, mode);
            if (result.success) {
                alert(`✓ 小组创建成功\nID: ${result.data.group.id}\n请告诉对方加入`);
                nameInput.value = '';
                await loadMyGroups();
                await selectGroup(result.data.group.id);
            } else {
                alert('创建失败: ' + (result.message || '未知错误'));
            }
        } catch (err) {
            alert('创建失败: ' + err.message);
        }
    }

    async function joinGroup() {
        const idInput = document.getElementById('psiSumGroupIdInput');
        const id = (idInput.value || '').trim().toUpperCase().slice(0, 4);
        if (!id || id.length !== 4) { alert('请输入4位小组ID'); return; }
        try {
            const result = await apiJoinPSISumGroup(id);
            if (result.success) {
                alert('加入成功');
                idInput.value = '';
                await loadMyGroups();
                await selectGroup(id);
            } else {
                alert('加入失败: ' + (result.message || '未知错误'));
            }
        } catch (err) {
            alert('加入失败: ' + err.message);
        }
    }

    async function selectGroup(groupId) {
        currentGroupId = groupId;
        const detail = await loadGroupDetail(groupId);
        if (!detail) { alert('加载小组失败'); backToList(); return; }
        currentGroupDetail = detail;
        showView2();
        // 高亮当前选中的组
        document.querySelectorAll('#psiSumMyGroupList .psi-group-item').forEach(li => {
            li.classList.toggle('active', li.dataset.groupId === groupId);
        });
        // 清空 upload 区块
        const setFile = document.getElementById('psiSumFile');
        const valFile = document.getElementById('psiSumValueFile');
        if (setFile) setFile.value = '';
        if (valFile) valFile.value = '';
        const status = document.getElementById('psiSumUploadStatus');
        if (status) status.textContent = '';
        renderFromDetail();
        startPolling();
    }

    function renderFromDetail() {
        if (!currentGroupDetail) return;
        const detail = currentGroupDetail;
        const group = detail.group;
        const username = sessionStorage.getItem('username');
        const myUpload = detail.my_upload;
        const otherUpload = detail.other_upload;

        // 小组信息
        document.getElementById('psiSumCurrentGroupName').textContent = group.name;
        document.getElementById('psiSumCurrentGroupId').textContent = group.id;
        document.getElementById('psiSumCreator').textContent = group.creator + (group.creator === username ? ' (你)' : '');
        document.getElementById('psiSumCreatedAt').textContent = group.created_at;
        const modeLabels = { 'auto': '自动', 'number_only': '只取数字', 'text_all': '全部哈希' };
        const modeEl = document.getElementById('psiSumStandardizeModeShown');
        if (modeEl) modeEl.textContent = modeLabels[group.standardize_mode || 'auto'] || (group.standardize_mode || 'auto');
        document.getElementById('psiSumMemberCount').textContent = `${group.members.length} / 2 人`;

        // 成员状态
        const uploadedNames = new Set((group.uploads || []).map(u => u.username));
        const memberStatusHtml = group.members.map((name, idx) => {
            const up = uploadedNames.has(name);
            const role = idx === 0 ? 'receiver' : 'sender';
            return `<div class="member-status">
                <span><strong>${escapeHtml(name)}${name === username ? ' (你)' : ''}</strong> · <em>${role}</em></span>
                <span class="status-badge ${up ? 'uploaded' : 'pending'}">${up ? '✓ 已上传' : '⏳ 未上传'}</span>
            </div>`;
        }).join('');
        document.getElementById('psiSumMemberStatus').innerHTML = memberStatusHtml;

        // 进度条
        const uploadedCount = (group.uploads || []).length;
        const pct = group.members.length ? Math.round((uploadedCount / group.members.length) * 100) : 0;
        document.getElementById('psiSumProgressFill').style.width = pct + '%';
        const allUploaded = group.members.length === 2 && uploadedCount === 2;
        const remainText = group.members.length < 2
            ? `⏳ 等待对方加入 (${group.members.length}/2)...`
            : (myUpload ? '⏳ 等待对方上传...' : '📤 请上传你的文件 + 关联数值');
        document.getElementById('psiSumProgressText').textContent = allUploaded ? '✓ 双方已上传, 可以开始运算' : remainText;

        // 上传按钮状态
        const uploadBtn = document.getElementById('psiSumUploadBtn');
        if (uploadBtn) {
            if (myUpload) {
                uploadBtn.disabled = true;
                uploadBtn.textContent = '✓ 已上传';
            } else {
                uploadBtn.disabled = group.members.length < 2;
                uploadBtn.textContent = '📤 上传';
            }
        }
        // 撤回按钮只在已上传后显示
        const deleteBtn = document.getElementById('psiSumDeleteUploadBtn');
        if (deleteBtn) {
            deleteBtn.style.display = myUpload ? 'inline-block' : 'none';
        }

        // 启动运算按钮
        const startCard = document.getElementById('psiSumStartCard');
        const startBtn = document.getElementById('psiSumStartBtn');
        // 只有 creator (receiver) 能看到并触发
        const isCreator = group.creator === username;
        if (startCard) {
            startCard.style.display = allUploaded && isCreator ? 'block' : 'none';
        }
        if (startBtn && detail.cardinality_result !== null && detail.cardinality_result !== undefined) {
            startBtn.disabled = true;
            startBtn.textContent = '✓ 已完成';
        } else if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = '▶ 开始隐私求和';
        }

        // 预览：己方明文 + 己方 value (上传后立即显示)
        renderPreview(detail, username);

        // 结果展示
        if (detail.cardinality_result !== null && detail.cardinality_result !== undefined) {
            renderResult(detail);
        }
    }

    function renderPreview(detail, username) {
        const previewCard = document.getElementById('psiSumPreviewCard');
        const origEl = document.getElementById('psiSumPlaintext');
        const valEl = document.getElementById('psiSumValues');
        const ctEl = document.getElementById('psiSumCiphertext');
        if (!previewCard || !origEl) return;

        const myOrig = detail.my_original_preview || [];
        const myVal = detail.my_values_preview || [];
        const myCt = detail.my_ciphertext_preview || [];
        const myOrigFull = detail.my_original_full_count || 0;
        const myValFull = detail.my_values_full_count || 0;
        const myCtFull = detail.my_ciphertext_full_count || 0;

        if (myOrig.length === 0 && myVal.length === 0 && myCt.length === 0) {
            previewCard.style.display = 'none';
            return;
        }
        previewCard.style.display = 'block';
        origEl.textContent = myOrig.length ? myOrig.join('\n') + (myOrigFull > 20 ? `\n... (共 ${myOrigFull} 项, 仅显示前 20)` : '') : '(未上传集合)';
        if (valEl) {
            valEl.textContent = myVal.length ? myVal.join('\n') + (myValFull > 20 ? `\n... (共 ${myValFull} 项, 仅显示前 20)` : '') : '(未传 value)';
        }
        if (ctEl) {
            ctEl.textContent = myCt.length ? myCt.join('\n') + (myCtFull > 20 ? `\n... (共 ${myCtFull} 项, 仅显示前 20)` : '') : '(尚未运算, 没有密文)';
        }
    }

    function renderResult(detail) {
        const resultCard = document.getElementById('psiSumResultCard');
        if (!resultCard) return;
        resultCard.style.display = 'block';
        document.getElementById('psiSumCardinality').textContent = detail.cardinality_result ?? '-';
        // sum 是 BigInt, 必须用字符串(避免 JS Number 精度丢失)
        document.getElementById('psiSumSum').textContent = detail.sum_result || '-';
        // duration
        const durEl = document.getElementById('psiSumDuration');
        if (durEl && detail.sum_persisted) {
            durEl.textContent = detail.sum_persisted.duration_human || `${detail.sum_persisted.duration_seconds || '?'} 秒`;
        } else if (durEl) {
            durEl.textContent = '-';
        }
        const startBtn = document.getElementById('psiSumStartBtn');
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.textContent = '✓ 已完成';
        }
    }

    async function uploadFile() {
        const setInput = document.getElementById('psiSumFile');
        const valInput = document.getElementById('psiSumValueFile');
        const setFile = setInput && setInput.files[0];
        const valFile = valInput && valInput.files[0];
        if (!setFile) { alert('请选择集合文件'); return; }
        if (!currentGroupId) { alert('小组未加载'); return; }
        const statusEl = document.getElementById('psiSumUploadStatus');
        statusEl.textContent = '⏳ 上传中...';
        statusEl.style.color = '#666';
        try {
            const result = await apiPSISumUpload(currentGroupId, setFile, valFile);
            if (result.success) {
                const d = result.data;
                statusEl.style.color = '#5a8a3a';
                statusEl.textContent = `✓ ${setFile.name} (${d.upload_count} 个元素)`
                    + (d.value_count > 0 ? ` + ${d.value_count} 个 value` : ' (未传 value)');
                const detail = await loadGroupDetail(currentGroupId);
                if (detail) {
                    currentGroupDetail = detail;
                    renderFromDetail();
                }
            } else {
                statusEl.style.color = '#c33';
                statusEl.textContent = '';
                alert('上传失败: ' + (result.message || '未知错误'));
            }
        } catch (err) {
            statusEl.style.color = '#c33';
            statusEl.textContent = '';
            alert('上传失败: ' + err.message);
        }
    }

    async function deleteUpload() {
        if (!currentGroupId) return;
        if (!confirm('确认撤回本轮上传吗? (双方需重新上传才能再次运算)')) return;
        try {
            const result = await apiDeletePSISumUpload(currentGroupId);
            if (result.success) {
                alert('已撤回');
                const detail = await loadGroupDetail(currentGroupId);
                if (detail) {
                    currentGroupDetail = detail;
                    renderFromDetail();
                }
            } else {
                alert('撤回失败: ' + (result.message || '未知错误'));
            }
        } catch (err) {
            alert('撤回失败: ' + err.message);
        }
    }

    async function start() {
        if (!currentGroupId) { alert('请先选择小组'); return; }
        const btn = document.getElementById('psiSumStartBtn');
        btn.disabled = true;
        btn.textContent = '⏳ 运算中...';
        try {
            const result = await apiStartPSISumComputation(currentGroupId);
            if (result.success) {
                const detail = await loadGroupDetail(currentGroupId);
                if (detail) {
                    currentGroupDetail = detail;
                    renderFromDetail();
                }
            } else {
                alert('运算失败: ' + (result.message || '未知错误'));
                btn.disabled = false;
                btn.textContent = '▶ 开始隐私求和';
            }
        } catch (err) {
            alert('运算失败: ' + err.message);
            btn.disabled = false;
            btn.textContent = '▶ 开始隐私求和';
        }
    }

    async function deleteGroup() {
        if (!currentGroupId) return;
        if (!confirm('确认解散该 PSI-Sum 小组吗? 此操作不可撤销')) return;
        try {
            const result = await apiDeletePSISumGroup(currentGroupId);
            if (result.success) {
                alert('小组已解散');
                backToList();
            } else {
                alert('解散失败: ' + (result.message || '未知错误'));
            }
        } catch (err) {
            alert('解散失败: ' + err.message);
        }
    }

    function backToList() {
        currentGroupId = null;
        currentGroupDetail = null;
        stopPolling();
        showView1();
        loadMyGroups();
    }

    return {
        init,
        createGroup,
        joinGroup,
        selectGroup,
        uploadFile,
        deleteUpload,
        start,
        deleteGroup,
        backToList,
        _loadMyGroups: loadMyGroups
    };
})();

// SS_PSI IIFE (真实后端 4 方小组管理, 仅运算 mock)
// 2026-07-05
window.SS_PSI = (function() {
    let myGroups = [];
    let currentGroupId = null;
    let currentGroupDetail = null;
    let pollTimer = null;
    let pollBusy = false;

    function getToken() {
        return sessionStorage.getItem('token') || localStorage.getItem('jwt_token') || '';
    }
    function getUsername() {
        const t = getToken();
        if (!t) return '';
        try {
            const payload = JSON.parse(atob(t.split('.')[1] || ''));
            return payload.username || payload.sub || '';
        } catch { return ''; }
    }
    async function api(path, opts = {}) {
        const headers = { 'Authorization': 'Bearer ' + getToken() };
        if (!(opts.body instanceof FormData) && opts.body && typeof opts.body === 'object') {
            headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(opts.body);
        }
        const r = await fetch(path, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
        return j;
    }
    async function loadMyGroups() {
        try {
            const j = await api('/api/my-ss-psi-groups');
            myGroups = j.groups || [];
        } catch (err) { console.error(err); myGroups = []; }
        renderMyGroupsList();
    }
    async function loadGroupDetail(groupId) {
        try {
            const j = await api(`/api/ss-psi-groups/${groupId}`);
            return j.group;
        } catch (err) { console.error(err); return null; }
    }
    function startPolling() {
        stopPolling();
        pollTimer = setInterval(async () => {
            if (!currentGroupId || pollBusy) return;
            pollBusy = true;
            const detail = await loadGroupDetail(currentGroupId);
            pollBusy = false;
            if (detail && detail.id === currentGroupId) {
                currentGroupDetail = detail;
                renderFromDetail();
            }
        }, 2000);
    }
    function stopPolling() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    async function init() {
        currentGroupId = null;
        currentGroupDetail = null;
        stopPolling();
        showView1();
        await loadMyGroups();
    }
    function showView1() {
        document.getElementById('ssPsiView1').style.display = 'block';
        document.getElementById('ssPsiView2').style.display = 'none';
    }
    function showView2() {
        document.getElementById('ssPsiView1').style.display = 'none';
        document.getElementById('ssPsiView2').style.display = 'block';
    }

    async function createGroup() {
        const name = document.getElementById('ssPsiGroupNameInput').value.trim();
        if (!name) { alert('请输入小组名称'); return; }
        try {
            const j = await api('/api/ss-psi-groups', { method: 'POST', body: { name } });
            document.getElementById('ssPsiGroupNameInput').value = '';
            await loadMyGroups();
            alert(`✓ 多方小组已创建\n名称: ${j.group.name}\nID: ${j.group.id}\n需 4 方全部加入, 将 ID 告诉其他参与方`);
            enterGroup(j.group.id);
        } catch (err) {
            alert('创建失败: ' + err.message);
        }
    }
    async function joinGroup() {
        const id = document.getElementById('ssPsiGroupIdInput').value.trim().toUpperCase().slice(0, 4);
        if (!id) { alert('请输入小组 ID'); return; }
        try {
            const j = await api('/api/ss-psi-groups/join', { method: 'POST', body: { group_id: id } });
            if (!j.success) { alert('加入失败: ' + (j.message || '未知错误')); return; }
            document.getElementById('ssPsiGroupIdInput').value = '';
            await loadMyGroups();
            enterGroup(j.group_id || id);
        } catch (err) {
            alert('加入失败: ' + err.message);
        }
    }
    function renderMyGroupsList() {
        const ul = document.getElementById('ssPsiMyGroupList');
        if (myGroups.length === 0) {
            ul.innerHTML = '<li class="empty-state">暂无小组, 创建或加入一个</li>';
            return;
        }
        ul.innerHTML = myGroups.map(g => `
            <li class="psi-group-item" onclick="SS_PSI.enterGroup('${g.id}')">
                <div class="psi-group-name">${g.name}</div>
                <div class="psi-group-id">ID: ${g.id}</div>
                <div class="psi-group-meta">${g.member_count} / ${g.expected_parties} 方 · ${g.created_at}</div>
            </li>
        `).join('');
    }

    async function enterGroup(groupId) {
        currentGroupId = groupId;
        showView2();
        const detail = await loadGroupDetail(groupId);
        if (!detail) { alert('加载小组失败'); backToList(); return; }
        currentGroupDetail = detail;
        document.getElementById('ssPsiCurrentGroupName').textContent = detail.name;
        document.getElementById('ssPsiCurrentGroupId').textContent = detail.id;
        document.getElementById('ssPsiCreatedAt').textContent = detail.created_at;
        document.getElementById('ssPsiCreator').textContent = detail.creator;
        document.getElementById('ssPsiFile').value = '';
        document.getElementById('ssPsiUploadStatus').textContent = '';
        document.getElementById('ssPsiUploadBtn').disabled = true;
        renderFromDetail();
        startPolling();
    }
    function renderFromDetail() {
        if (!currentGroupDetail) return;
        const g = currentGroupDetail;
        const me = getUsername();
        const uploadedNames = new Set(g.uploads.map(u => u.username));
        const roleNames = ['party_A', 'party_B', 'party_C', 'party_D'];
        const members = g.members.map((name, idx) => ({
            name,
            uploaded: uploadedNames.has(name),
            isMe: name === me,
            role: roleNames[idx] || `party_${idx + 1}`
        }));
        const totalParties = g.expected_parties || 4;
        document.getElementById('ssPsiMemberCount').textContent = `${g.members.length} / ${totalParties} 方`;
        document.getElementById('ssPsiMemberStatus').innerHTML = members.map(m => `
            <div class="member-status">
                <span><strong>${m.name}${m.isMe ? ' (我)' : ''}</strong> · <em>${m.role}</em></span>
                <span class="status-badge ${m.uploaded ? 'uploaded' : 'pending'}">
                    ${m.uploaded ? '✓ 已上传' : '⏳ 未上传'}
                </span>
            </div>
        `).join('');
        const uploadedCount = members.filter(m => m.uploaded).length;
        const pct = g.members.length ? Math.round((uploadedCount / g.members.length) * 100) : 0;
        document.getElementById('ssPsiProgressFill').style.width = pct + '%';
        const allUploaded = g.members.length === totalParties && uploadedCount === totalParties;
        const myUploaded = uploadedNames.has(me);
        document.getElementById('ssPsiUploadBtn').disabled = g.members.length < totalParties || myUploaded;
        document.getElementById('ssPsiStartCard').style.display = allUploaded ? 'block' : 'none';
        const remainText = g.members.length < totalParties
            ? `⏳ 等待其他参与方加入 (${g.members.length}/${totalParties})...`
            : (myUploaded ? '⏳ 等待其他参与方上传...' : '📤 请上传你的文件');
        document.getElementById('ssPsiProgressText').textContent = allUploaded ? '✓ 所有参与方已上传, 可以开始运算' : remainText;
        // 参与方表
        if (g.uploads.length > 0) {
            document.getElementById('ssPsiParticipants').innerHTML = members.map(m => {
                const up = g.uploads.find(u => u.username === m.name);
                const cnt = up ? up.count : '-';
                return `<tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${m.name}${m.isMe ? ' (我)' : ''}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${cnt}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${m.role}</td>
                </tr>`;
            }).join('');
            document.getElementById('ssPsiParticipantsCard').style.display = 'block';
        }
        if (g.result) renderResult(g.result);
    }
    function renderResult(result) {
        document.getElementById('ssPsiIntersection').textContent = (result.intersection || []).join('\n');
        document.getElementById('ssPsiCardinality').textContent = result.cardinality ?? '-';
        document.getElementById('ssPsiParticipantsCard').style.display = 'block';
        document.getElementById('ssPsiResultCard').style.display = 'block';
        const btn = document.getElementById('ssPsiStartBtn');
        if (btn) { btn.disabled = true; btn.textContent = '✓ 已完成'; }
    }

    async function uploadFile() {
        const fileInput = document.getElementById('ssPsiFile');
        const file = fileInput.files[0];
        if (!file) { alert('请先选择文件'); return; }
        if (!currentGroupId) { alert('小组未加载'); return; }
        try {
            const fd = new FormData();
            fd.append('file', file);
            const j = await api(`/api/ss-psi-groups/${currentGroupId}/upload`, { method: 'POST', body: fd });
            document.getElementById('ssPsiUploadStatus').textContent = `✓ ${file.name} (${j.count} 条)`;
            document.getElementById('ssPsiUploadStatus').style.color = '#5a8a3a';
            const detail = await loadGroupDetail(currentGroupId);
            if (detail) { currentGroupDetail = detail; renderFromDetail(); }
        } catch (err) {
            alert('上传失败: ' + err.message);
        }
    }
    async function start() {
        if (!currentGroupId) { alert('请先选择小组'); return; }
        const btn = document.getElementById('ssPsiStartBtn');
        btn.disabled = true;
        btn.textContent = '⏳ 运算中...';
        try {
            const j = await api(`/api/ss-psi-groups/${currentGroupId}/start`, { method: 'POST' });
            renderResult(j.result);
            const detail = await loadGroupDetail(currentGroupId);
            if (detail) { currentGroupDetail = detail; renderFromDetail(); }
        } catch (err) {
            alert('运算失败: ' + err.message);
            btn.disabled = false;
            btn.textContent = '🚀 开始运算';
        }
    }
    function backToList() {
        currentGroupId = null;
        currentGroupDetail = null;
        stopPolling();
        showView1();
        loadMyGroups();
    }

    return { init, createGroup, joinGroup, enterGroup, uploadFile, start, backToList, _loadMyGroups: loadMyGroups };
})();