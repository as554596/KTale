// API 配置
const API_BASE_URL = window.location.protocol === 'file:'
    ? 'http://localhost:5000'
    : window.location.origin;

// 全局狀態
const state = {
    files: [],
    glossary: [],
    currentFileType: 'epub',
    currentPage: 'files',
    taskId: null,
    translatedFilePath: null,
    progressTimers: {}
};

// ==================== 辅助函数 ====================

// 格式化时间（秒转为可读格式）
function formatTime(seconds) {
    if (seconds < 60) return `${Math.round(seconds)} 秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
    return `${Math.floor(seconds / 3600)} 小时 ${Math.floor((seconds % 3600) / 60)} 分`;
}

// 更新进度显示
function updateProgressDisplay(type, data) {
    const percent = data.percent || 0;
    const processed = data.processed || 0;
    const total = data.total || 0;
    const message = data.message || '';

    // 更新百分比
    document.getElementById(`${type}Percent`).textContent = `${Math.round(percent)}%`;

    // 更新进度条
    document.getElementById(`${type}Bar`).style.width = `${percent}%`;

    // 更新状态文字
    document.getElementById(`${type}Status`).textContent = message;

    // 更新详细信息
    if (document.getElementById(`${type}Processed`)) {
        document.getElementById(`${type}Processed`).textContent = processed;
    }
    if (document.getElementById(`${type}Total`)) {
        document.getElementById(`${type}Total`).textContent = total;
    }

    // 计算并更新 ETA
    if (data.eta !== undefined && document.getElementById(`${type}ETA`)) {
        document.getElementById(`${type}ETA`).textContent = formatTime(data.eta);
    } else if (percent > 0 && percent < 100 && data.elapsed) {
        const remaining = (data.elapsed / percent) * (100 - percent);
        if (document.getElementById(`${type}ETA`)) {
            document.getElementById(`${type}ETA`).textContent = formatTime(remaining / 1000);
        }
    }

    // 更新特定类型的额外信息
    if (type === 'extract' && data.found !== undefined && document.getElementById('extractFound')) {
        document.getElementById('extractFound').textContent = data.found;
    }
    if (type === 'review' && data.fixed !== undefined && document.getElementById('reviewFixed')) {
        document.getElementById('reviewFixed').textContent = data.fixed;
    }
    if (type === 'translate' && data.speed !== undefined && document.getElementById('translateSpeed')) {
        document.getElementById('translateSpeed').textContent = `${data.speed.toFixed(1)} 段/秒`;
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    updateUI();
});

// ==================== 側邊欄 ====================

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
}

function navigateTo(page) {
    // 更新導航狀態
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // 找到被点击的导航项并激活
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.getAttribute('onclick')?.includes(page)) {
            item.classList.add('active');
        }
    });

    // 切換頁面
    document.querySelectorAll('.page').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(`page-${page}`).classList.add('active');

    // 更新標題
    const titles = {
        'files': '文件管理',
        'glossary-extract': '術語提取',
        'glossary-review': '術語校對',
        'translate': '翻譯',
        'quality-check': '漏翻校對',
        'settings': '設置'
    };
    document.getElementById('pageTitle').textContent = titles[page];

    // 特殊處理：跳轉到漏翻校對頁面
    if (page === 'quality-check') {
        const taskId = localStorage.getItem('last_translate_task_id');
        if (taskId) {
            window.open(`quality_checker.html?task_id=${taskId}`, '_blank');
        } else {
            showToast('請先完成一次翻譯任務');
        }
    }

    state.currentPage = page;

    // 更新術語校對頁面計數
    if (page === 'glossary-review') {
        updateTermCount();
    }

    // 更新翻譯頁面的已校對術語計數
    if (page === 'translate') {
        const countEl = document.getElementById('reviewedGlossaryCount');
        if (countEl) countEl.textContent = state.glossary.length;
    }

    // 關閉側邊欄（手機）
    if (window.innerWidth < 768) {
        closeSidebar();
    }
}

// ==================== 文件管理 ====================

function setFileType(type) {
    state.currentFileType = type;

    // 更新标签样式
    document.querySelectorAll('.file-type-tab').forEach(tab => {
        tab.classList.remove('active');
        // 检查这个标签是否对应当前类型
        if ((type === 'epub' && tab.textContent.includes('EPUB')) ||
            (type === 'txt' && tab.textContent.includes('TXT'))) {
            tab.classList.add('active');
        }
    });

    // 更新文件输入的 accept 属性
    const input = document.getElementById('fileInput');
    if (input) {
        input.accept = type === 'epub' ? '.epub,application/epub+zip' : '.txt,text/plain';
    }
}

async function handleFileSelect(event) {
    const files = Array.from(event.target.files);

    console.log('=== File Select ===');
    console.log(`Selected ${files.length} files`);

    if (files.length === 0) {
        console.warn('No files selected');
        return;
    }

    for (const file of files) {
        console.log(`Processing: ${file.name}, size: ${file.size}, type: ${file.type}`);

        // 检查文件大小
        if (file.size > 50 * 1024 * 1024) {
            showToast(`${file.name} 超過 50MB 限制`);
            continue;
        }

        // 检查文件类型（手机兼容性）
        const isEpub = file.name.toLowerCase().endsWith('.epub') || file.type === 'application/epub+zip';
        const isTxt = file.name.toLowerCase().endsWith('.txt') || file.type === 'text/plain';

        if (!isEpub && !isTxt) {
            showToast(`${file.name} 不支持的文件格式`);
            console.error(`Unsupported file type: ${file.type}`);
            continue;
        }

        const formData = new FormData();
        formData.append('file', file);

        console.log('Uploading file to:', `${API_BASE_URL}/api/upload`);

        try {
            const response = await fetch(`${API_BASE_URL}/api/upload`, {
                method: 'POST',
                body: formData
            });

            console.log('Upload response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Upload failed:', errorText);
                throw new Error(`上傳失敗 (${response.status})`);
            }

            const data = await response.json();
            console.log('Upload response data:', data);

            if (data.status === 'success') {
                state.files.push({
                    name: file.name,
                    path: data.filepath,
                    size: file.size,
                    type: data.file_type
                });
                showToast(`${file.name} 上傳成功`);
                console.log(`✓ File uploaded: ${data.filepath}`);
            } else {
                showToast(`${file.name} 上傳失敗: ${data.error || '未知錯誤'}`);
                console.error('Upload failed:', data);
            }
        } catch (error) {
            console.error('Upload error:', error);
            showToast(`上傳失敗: ${error.message}`);
        }
    }

    renderFileList();
    updateUI();
    event.target.value = '';
}

function renderFileList() {
    const card = document.getElementById('fileListCard');
    const list = document.getElementById('fileList');

    if (state.files.length === 0) {
        card.classList.add('hidden');
        return;
    }

    card.classList.remove('hidden');
    list.innerHTML = state.files.map((file, index) => `
        <div class="file-item">
            <div class="file-item-info">
                <div class="file-item-name">${file.name}</div>
                <div class="file-item-size">${formatFileSize(file.size)}</div>
            </div>
            <button class="file-item-remove" onclick="removeFile(${index})">刪除</button>
        </div>
    `).join('');
}

function removeFile(index) {
    state.files.splice(index, 1);
    renderFileList();
    updateUI();
}

function clearFiles() {
    if (confirm('確定要清空所有文件嗎？')) {
        state.files = [];
        renderFileList();
        updateUI();
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ==================== 術語提取 ====================

async function extractGlossary() {
    const settings = loadSettings();

    if (!settings.extract_api_key) {
        showToast('請先配置術語提取 API');
        navigateTo('settings');
        return;
    }

    if (state.files.length === 0) {
        showToast('請先上傳文件');
        navigateTo('files');
        return;
    }

    const btn = document.getElementById('btnExtract');
    const progress = document.getElementById('extractProgress');
    const result = document.getElementById('glossaryResult');

    btn.disabled = true;
    progress.classList.remove('hidden');
    result.classList.add('hidden');

    updateProgressDisplay('extract', {
        percent: 0,
        processed: 0,
        total: 0,
        found: 0,
        message: '正在提取術語...'
    });

    try {
        const customPrompt = document.getElementById('extractPrompt').value;

        const response = await fetch(`${API_BASE_URL}/api/extract_glossary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: state.files.map(f => f.path),
                api_key: settings.extract_api_key,
                base_url: settings.extract_api_url,
                model: settings.extract_api_model,
                custom_prompt: customPrompt
            })
        });

        const data = await response.json();

        if (data.status !== 'success') {
            throw new Error(data.error || '啟動提取任務失敗');
        }

        await pollExtractProgress(data.task_id);

    } catch (error) {
        console.error('Extract error:', error);

        let errorMsg = error.message || '未知錯誤';
        if (errorMsg.includes('Failed to fetch')) {
            errorMsg = '網絡連接失敗，請檢查後端是否運行';
        } else if (errorMsg.includes('pattern')) {
            errorMsg = 'API Key 或 URL 格式錯誤';
        }

        showToast('提取失敗: ' + errorMsg);
        updateProgressDisplay('extract', {
            percent: 0,
            message: '❌ ' + errorMsg
        });
        btn.disabled = false;
        setTimeout(() => {
            progress.classList.add('hidden');
        }, 2000);
    }
}

async function pollExtractProgress(taskId) {
    const btn = document.getElementById('btnExtract');
    const progress = document.getElementById('extractProgress');
    const result = document.getElementById('glossaryResult');
    const startTime = Date.now();

    return new Promise((resolve) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/progress/${taskId}`);
                const data = await response.json();

                if (data.status === 'processing') {
                    const p = data.progress || {};
                    const elapsed = Date.now() - startTime;
                    updateProgressDisplay('extract', {
                        percent: p.percent || 0,
                        processed: p.current || 0,
                        total: p.total || 0,
                        elapsed: elapsed,
                        message: p.message || '提取中...'
                    });

                } else if (data.status === 'completed') {
                    clearInterval(interval);

                    state.glossary = data.result || [];

                    updateProgressDisplay('extract', {
                        percent: 100,
                        processed: state.glossary.length,
                        total: state.glossary.length,
                        found: state.glossary.length,
                        message: '提取完成！'
                    });

                    if (state.glossary.length === 0) {
                        showToast('⚠️  未提取到术語，請檢查文件內容');
                        setTimeout(() => {
                            result.classList.remove('hidden');
                            document.getElementById('glossaryList').innerHTML = `
                                <div class="alert alert-warning">
                                    未提取到任何術語。可能的原因：
                                    <ul style="margin: 8px 0 0 20px; font-size: 13px;">
                                        <li>文件內容過短</li>
                                        <li>文件編碼問題</li>
                                        <li>EPUB 結構不標準</li>
                                    </ul>
                                    建議：嘗試上傳 TXT 格式，或在電腦上提取後上傳 JSON
                                </div>
                            `;
                        }, 500);
                    } else {
                        setTimeout(() => {
                            renderGlossaryList();
                            result.classList.remove('hidden');
                            updateUI();
                            showToast(`提取到 ${state.glossary.length} 個術語`);
                        }, 500);
                    }

                    btn.disabled = false;
                    setTimeout(() => progress.classList.add('hidden'), 2000);
                    resolve();

                } else if (data.status === 'error') {
                    clearInterval(interval);

                    let errorMsg = data.error || '未知錯誤';
                    if (errorMsg.includes('pattern')) {
                        errorMsg = 'API 格式錯誤，請檢查 API Key 和 URL 是否正確';
                    }

                    showToast('提取失敗: ' + errorMsg);
                    updateProgressDisplay('extract', {
                        percent: 0,
                        message: '❌ ' + errorMsg
                    });

                    btn.disabled = false;
                    setTimeout(() => progress.classList.add('hidden'), 2000);
                    resolve();
                }
            } catch (error) {
                clearInterval(interval);
                showToast('獲取進度失敗');
                btn.disabled = false;
                resolve();
            }
        }, 1500);
    });
}

function renderGlossaryList() {
    const list = document.getElementById('glossaryList');
    list.innerHTML = state.glossary.map(term => {
        // 只显示前3个上下文（用于预览）
        const displayContexts = (term.contexts || []).slice(0, 3);
        const hasMore = (term.contexts || []).length > 3;

        return `
        <div class="term-item">
            <div class="term-item-left">
                <div class="term-label">原文</div>
                <div class="term-text">${term.src}</div>
                <div class="term-freq">出現 ${term.frequency} 次${term.info ? ' · ' + term.info : ''}</div>
                ${displayContexts.length > 0 ? `
                    <details class="term-contexts" style="margin-top: 8px;">
                        <summary style="cursor: pointer; color: #007aff; font-size: 13px;">
                            查看原文參考 (顯示前 ${displayContexts.length} 條${hasMore ? '，共 ' + term.contexts.length + ' 條' : ''})
                        </summary>
                        <div style="margin-top: 8px;">
                            ${displayContexts.map((ctx, i) => `
                                <div class="context-item" style="margin-bottom: 6px; padding: 8px; background: #f5f5f5; border-radius: 6px;">
                                    <strong style="color: #666;">[${i+1}]</strong> ${truncateContext(ctx, 100)}
                                </div>
                            `).join('')}
                            ${hasMore ? `
                                <div style="margin-top: 8px; padding: 8px; background: #fff3cd; border-radius: 6px; font-size: 12px; color: #856404;">
                                    💡 提示：完整上下文已保存，下載和校對時會包含全部 ${term.contexts.length} 條參考
                                </div>
                            ` : ''}
                        </div>
                    </details>
                ` : ''}
            </div>
            <div class="term-item-right">
                <div class="term-label">翻譯</div>
                <div class="term-text ${!term.dst ? 'text-gray' : ''}">${term.dst || '（未翻譯）'}</div>
            </div>
        </div>
    `;
    }).join('');
}

// 截断上下文用于显示
function truncateContext(context, maxLength = 100) {
    if (!context || context.length <= maxLength) {
        return context;
    }
    return context.substring(0, maxLength) + '...';
}

function exportGlossary() {
    // 导出完整术语表（包含所有上下文）
    const dataStr = JSON.stringify(state.glossary, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'glossary_full.json';
    link.click();
    URL.revokeObjectURL(url);
    showToast('完整術語表已導出（包含所有上下文）');
}

// ==================== 術語校對 ====================

function useExtractedGlossary() {
    if (state.glossary.length === 0) {
        showToast('沒有已提取的術語，請先進行術語提取');
        navigateTo('glossary-extract');
        return;
    }
    showToast(`已載入 ${state.glossary.length} 個術語`);
    updateUI();
}

function updateTermCount() {
    const countEl = document.getElementById('extractedCount');
    if (countEl) countEl.textContent = state.glossary.length;
}

function handleGlossaryJsonUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const json = JSON.parse(e.target.result);

            // 验证 JSON 格式
            if (!Array.isArray(json)) {
                showToast('JSON 格式錯誤：必須是陣列');
                return;
            }

            // 验证每个术语的格式
            const validGlossary = json.filter(term => {
                return term.src && typeof term.src === 'string';
            }).map(term => ({
                src: term.src,
                dst: term.dst || '',
                info: term.info || term.type || '未分類',
                frequency: term.frequency || 1
            }));

            if (validGlossary.length === 0) {
                showToast('JSON 中沒有有效的術語');
                return;
            }

            state.glossary = validGlossary;
            showToast(`成功載入 ${validGlossary.length} 個術語`);
            updateUI();

            // 清空 input
            event.target.value = '';
        } catch (error) {
            showToast('JSON 解析失敗: ' + error.message);
        }
    };
    reader.readAsText(file);
}

async function reviewGlossary() {
    const settings = loadSettings();

    if (!settings.review_api_key) {
        showToast('請先配置術語校對 API');
        navigateTo('settings');
        return;
    }

    if (state.glossary.length === 0) {
        showToast('請先提取術語');
        navigateTo('glossary-extract');
        return;
    }

    const btn = document.getElementById('btnReview');
    const progress = document.getElementById('reviewProgress');
    const result = document.getElementById('reviewResult');

    btn.disabled = true;
    progress.classList.remove('hidden');
    result.classList.add('hidden');

    const totalTerms = state.glossary.length;
    updateProgressDisplay('review', {
        percent: 0,
        processed: 0,
        total: totalTerms,
        fixed: 0,
        message: '正在校對術語...'
    });

    try {
        const customPrompt = document.getElementById('reviewPrompt').value;

        const response = await fetch(`${API_BASE_URL}/api/review_glossary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                glossary: state.glossary,
                api_key: settings.review_api_key,
                base_url: settings.review_api_url,
                model: settings.review_api_model,
                custom_prompt: customPrompt,
                novel_background: settings.novel_background || '',
                output_language: settings.output_language || 'traditional'
            })
        });

        const data = await response.json();

        if (data.status !== 'success') {
            throw new Error(data.error || '啟動校對任務失敗');
        }

        await pollReviewProgress(data.task_id, totalTerms);

    } catch (error) {
        showToast('校對失敗: ' + error.message);
        updateProgressDisplay('review', {
            percent: 0,
            message: '❌ ' + error.message
        });
        btn.disabled = false;
        setTimeout(() => {
            progress.classList.add('hidden');
        }, 2000);
    }
}

async function pollReviewProgress(taskId, totalTerms) {
    const btn = document.getElementById('btnReview');
    const progress = document.getElementById('reviewProgress');
    const result = document.getElementById('reviewResult');
    const startTime = Date.now();

    return new Promise((resolve) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/progress/${taskId}`);
                const data = await response.json();

                if (data.status === 'processing') {
                    const p = data.progress || {};
                    const elapsed = Date.now() - startTime;
                    updateProgressDisplay('review', {
                        percent: p.percent || 0,
                        processed: p.current || 0,
                        total: p.total || totalTerms,
                        elapsed: elapsed,
                        message: p.message || '校對中...'
                    });

                } else if (data.status === 'completed') {
                    clearInterval(interval);

                    const reviewResult = data.result || {};
                    state.glossary = reviewResult.glossary || [];
                    const fixedCount = reviewResult.reviewed_count || 0;

                    updateProgressDisplay('review', {
                        percent: 100,
                        processed: totalTerms,
                        total: totalTerms,
                        fixed: fixedCount,
                        message: '校對完成！'
                    });

                    setTimeout(() => {
                        renderReviewList();
                        result.classList.remove('hidden');
                        updateUI();
                        showToast(`校對完成，保留 ${state.glossary.length} 個術語`);
                    }, 500);

                    btn.disabled = false;
                    setTimeout(() => progress.classList.add('hidden'), 2000);
                    resolve();

                } else if (data.status === 'error') {
                    clearInterval(interval);

                    showToast('校對失敗: ' + (data.error || '未知錯誤'));
                    updateProgressDisplay('review', {
                        percent: 0,
                        message: '❌ ' + (data.error || '未知錯誤')
                    });

                    btn.disabled = false;
                    setTimeout(() => progress.classList.add('hidden'), 2000);
                    resolve();
                }
            } catch (error) {
                clearInterval(interval);
                showToast('獲取進度失敗');
                btn.disabled = false;
                resolve();
            }
        }, 1500);
    });
}

function renderReviewList() {
    const list = document.getElementById('reviewList');
    list.innerHTML = state.glossary.map((term, index) => `
        <div class="term-item">
            <div class="term-item-left">
                <div class="term-label">原文</div>
                <div class="term-text">${term.src}</div>
                <div class="term-freq">出現 ${term.frequency} 次</div>
            </div>
            <div class="term-item-right">
                <div class="term-label">翻譯</div>
                <input type="text" class="form-input" value="${term.dst || ''}"
                       onchange="updateGlossaryTranslation(${index}, this.value)">
            </div>
        </div>
    `).join('');
}

function updateGlossaryTranslation(index, value) {
    state.glossary[index].dst = value;
}

function saveGlossary() {
    localStorage.setItem('glossary', JSON.stringify(state.glossary));
    showToast('術語表已保存');
}

function exportReviewedGlossary() {
    // 导出校对后的完整术语表
    const dataStr = JSON.stringify(state.glossary, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'glossary_reviewed.json';
    link.click();
    URL.revokeObjectURL(url);
    showToast('已校對術語表已導出');
}

function goToTranslateWithGlossary() {
    if (state.glossary.length === 0) {
        showToast('沒有可用的術語表');
        return;
    }
    navigateTo('translate');
    showToast(`已載入 ${state.glossary.length} 個已校對術語`);
}

function useReviewedGlossary() {
    if (state.glossary.length === 0) {
        showToast('沒有已校對的術語，請先進行術語校對');
        navigateTo('glossary-review');
        return;
    }
    const countEl = document.getElementById('reviewedGlossaryCount');
    if (countEl) countEl.textContent = state.glossary.length;
    const statusEl = document.getElementById('translateGlossaryStatus');
    if (statusEl) statusEl.textContent = `已使用 ${state.glossary.length} 個已校對術語`;
    showToast(`已載入 ${state.glossary.length} 個術語`);
    updateUI();
}

function handleTranslateGlossaryUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const json = JSON.parse(e.target.result);

            if (!Array.isArray(json)) {
                showToast('JSON 格式錯誤：必須是陣列');
                return;
            }

            const validGlossary = json.filter(term => {
                return term.src && typeof term.src === 'string';
            }).map(term => ({
                src: term.src,
                dst: term.dst || '',
                info: term.info || term.type || '未分類',
                frequency: term.frequency || 1,
                contexts: term.contexts || []
            }));

            if (validGlossary.length === 0) {
                showToast('JSON 中沒有有效的術語');
                return;
            }

            state.glossary = validGlossary;
            const statusEl = document.getElementById('translateGlossaryStatus');
            if (statusEl) statusEl.textContent = `已上傳 ${validGlossary.length} 個術語`;
            showToast(`成功載入 ${validGlossary.length} 個術語`);
            updateUI();

            event.target.value = '';
        } catch (error) {
            showToast('JSON 解析失敗: ' + error.message);
        }
    };
    reader.readAsText(file);
}

// ==================== 翻譯 ====================

async function startTranslation() {
    const settings = loadSettings();

    if (!settings.translate_api_key) {
        showToast('請先配置翻譯 API');
        navigateTo('settings');
        return;
    }

    if (state.files.length === 0) {
        showToast('請先上傳文件');
        navigateTo('files');
        return;
    }

    const btn = document.getElementById('btnTranslate');
    const progress = document.getElementById('translateProgress');
    const result = document.getElementById('translateResult');

    btn.disabled = true;
    progress.classList.remove('hidden');
    result.classList.add('hidden');

    const useGlossary = document.getElementById('useGlossary').checked;
    const customPrompt = document.getElementById('translatePrompt').value;
    const maxWorkers = parseInt(document.getElementById('maxWorkers').value);
    const batchSize = parseInt(document.getElementById('batchSize').value);

    state.taskId = 'task_' + Date.now();

    try {
        const response = await fetch(`${API_BASE_URL}/api/translate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: state.taskId,
                file: state.files[0].path,
                file_type: state.files[0].type,
                glossary: useGlossary ? state.glossary : [],
                api_key: settings.translate_api_key,
                base_url: settings.translate_api_url,
                model: settings.translate_api_model,
                custom_prompt: customPrompt,
                max_workers: maxWorkers,
                batch_size: batchSize,
                delay: 0.5,
                use_glossary: useGlossary
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            pollTranslationProgress();
        } else {
            showToast('翻譯失敗: ' + data.error);
            btn.disabled = false;
            progress.classList.add('hidden');
        }
    } catch (error) {
        showToast('翻譯失敗: ' + error.message);
        btn.disabled = false;
        progress.classList.add('hidden');
    }
}

async function pollTranslationProgress() {
    const bar = document.getElementById('translateBar');
    const status = document.getElementById('translateStatus');
    const startTime = Date.now();
    let lastProcessed = 0;
    let lastTime = startTime;

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/progress/${state.taskId}`);
            const data = await response.json();

            if (data.status === 'processing') {
                const progressData = data.progress || {};
                const percent = progressData.percent || 0;
                const processed = progressData.processed || 0;
                const total = progressData.total || 0;
                const message = progressData.message || '翻譯中...';

                // 计算速度
                const now = Date.now();
                const timeDiff = (now - lastTime) / 1000; // 秒
                const processedDiff = processed - lastProcessed;
                const speed = timeDiff > 0 ? processedDiff / timeDiff : 0;

                lastProcessed = processed;
                lastTime = now;

                // 计算 ETA
                const remaining = total - processed;
                const eta = speed > 0 ? remaining / speed : 0;

                updateProgressDisplay('translate', {
                    percent: percent,
                    processed: processed,
                    total: total,
                    speed: speed,
                    eta: eta,
                    message: message
                });

            } else if (data.status === 'completed') {
                clearInterval(interval);

                updateProgressDisplay('translate', {
                    percent: 100,
                    processed: data.progress.total || 0,
                    total: data.progress.total || 0,
                    speed: 0,
                    message: '翻譯完成！'
                });

                state.translatedFilePath = data.result_file;

                // 保存任務 ID 用於漏翻校對
                state.lastTranslateTaskId = state.translateTaskId;
                localStorage.setItem('last_translate_task_id', state.translateTaskId);

                setTimeout(() => {
                    document.getElementById('translateProgress').classList.add('hidden');
                    document.getElementById('translateResult').classList.remove('hidden');

                    // 顯示質量統計（如果有）
                    if (data.stats) {
                        const statsHtml = `
                            <div style="margin-top: 15px; padding: 15px; background: #f0f9ff; border-radius: 10px;">
                                <h4 style="margin-bottom: 10px;">📊 翻譯質量統計</h4>
                                <p>✅ 成功: ${data.stats.translated} 段</p>
                                <p>🔄 重試: ${data.stats.retried} 段</p>
                                <p>⚠️ 低質量: ${data.stats.failed} 段</p>
                                <button onclick="goToQualityCheck()" style="margin-top: 10px; padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer;">
                                    前往漏翻校對
                                </button>
                            </div>
                        `;
                        const resultDiv = document.getElementById('translateResult');
                        resultDiv.innerHTML += statsHtml;
                    }

                    showToast('翻譯完成！');
                }, 1000);

            } else if (data.status === 'error') {
                clearInterval(interval);
                showToast('翻譯失敗: ' + data.error);
                document.getElementById('translateProgress').classList.add('hidden');
                document.getElementById('btnTranslate').disabled = false;
            }
        } catch (error) {
            clearInterval(interval);
            showToast('獲取進度失敗');
            document.getElementById('btnTranslate').disabled = false;
        }
    }, 2000);
}

function downloadResult() {
    if (!state.translatedFilePath) {
        showToast('沒有可下載的文件');
        return;
    }

    window.location.href = `${API_BASE_URL}/api/download/${encodeURIComponent(state.translatedFilePath)}`;
    showToast('開始下載');
}

// 跳轉到漏翻校對頁面
function goToQualityCheck() {
    const taskId = state.lastTranslateTaskId || localStorage.getItem('last_translate_task_id');
    if (taskId) {
        window.open(`quality_checker.html?task_id=${taskId}`, '_blank');
    } else {
        showToast('無法找到翻譯任務 ID');
    }
}

// ==================== 設置 ====================

function loadSettings() {
    const defaultPrompts = window.DEFAULT_PROMPTS || {};
    const defaults = {
        extract_api_key: '',
        extract_api_url: 'https://api.deepseek.com',
        extract_api_model: 'deepseek-chat',
        review_api_key: '',
        review_api_url: 'https://api.deepseek.com',
        review_api_model: 'deepseek-chat',
        review_prompt: defaultPrompts.review || '',
        novel_background: '',
        translate_api_key: '',
        translate_api_url: 'https://api.deepseek.com',
        translate_api_model: 'deepseek-chat'
    };

    const saved = localStorage.getItem('settings');
    const settings = saved ? { ...defaults, ...JSON.parse(saved) } : defaults;

    // 填充表單
    if (document.getElementById('extractApiKey')) {
        document.getElementById('extractApiKey').value = settings.extract_api_key;
        document.getElementById('extractApiUrl').value = settings.extract_api_url;
        document.getElementById('extractApiModel').value = settings.extract_api_model;

        if (!document.getElementById('extractPrompt').value) {
            document.getElementById('extractPrompt').value = defaultPrompts.extract || '';
        }
        if (!document.getElementById('translatePrompt').value) {
            document.getElementById('translatePrompt').value = defaultPrompts.translate || '';
        }

        document.getElementById('reviewApiKey').value = settings.review_api_key;
        document.getElementById('reviewApiUrl').value = settings.review_api_url;
        document.getElementById('reviewApiModel').value = settings.review_api_model;
        document.getElementById('reviewPrompt').value = settings.review_prompt;
        document.getElementById('novelBackground').value = settings.novel_background;
        document.getElementById('outputLanguage').value = settings.output_language || 'traditional';

        document.getElementById('translateApiKey').value = settings.translate_api_key;
        document.getElementById('translateApiUrl').value = settings.translate_api_url;
        document.getElementById('translateApiModel').value = settings.translate_api_model;
    }

    return settings;
}

function saveSettings() {
    const settings = {
        extract_api_key: document.getElementById('extractApiKey').value,
        extract_api_url: document.getElementById('extractApiUrl').value,
        extract_api_model: document.getElementById('extractApiModel').value,
        review_api_key: document.getElementById('reviewApiKey').value,
        review_api_url: document.getElementById('reviewApiUrl').value,
        review_api_model: document.getElementById('reviewApiModel').value,
        review_prompt: document.getElementById('reviewPrompt').value,
        novel_background: document.getElementById('novelBackground').value,
        output_language: document.getElementById('outputLanguage').value,
        translate_api_key: document.getElementById('translateApiKey').value,
        translate_api_url: document.getElementById('translateApiUrl').value,
        translate_api_model: document.getElementById('translateApiModel').value
    };

    localStorage.setItem('settings', JSON.stringify(settings));
    showToast('設置已保存');
}

// ==================== UI 更新 ====================

function updateUI() {
    const hasFiles = state.files.length > 0;
    const hasGlossary = state.glossary.length > 0;
    const settings = loadSettings();

    // 術語提取按鈕
    const btnExtract = document.getElementById('btnExtract');
    if (btnExtract) {
        btnExtract.disabled = !hasFiles || !settings.extract_api_key;
    }

    // 術語校對按鈕
    const btnReview = document.getElementById('btnReview');
    if (btnReview) {
        btnReview.disabled = !hasGlossary || !settings.review_api_key;
    }

    // 翻譯按鈕
    const btnTranslate = document.getElementById('btnTranslate');
    if (btnTranslate) {
        btnTranslate.disabled = !hasFiles || !settings.translate_api_key;
    }
}

// ==================== Toast ====================

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
