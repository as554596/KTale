// 漏翻校對頁面邏輯

const API_BASE = '/api';

let qualityReport = null;
let allParagraphs = [];
let filteredParagraphs = [];
let selectedIndices = new Set();
let currentFilter = 'all';

// 從 URL 獲取 task_id
const urlParams = new URLSearchParams(window.location.search);
const taskId = urlParams.get('task_id');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    if (!taskId) {
        showToast('錯誤：缺少任務 ID', 'error');
        document.getElementById('loading').style.display = 'none';
        document.getElementById('emptyState').style.display = 'block';
        return;
    }

    loadQualityReport();
    setupEventListeners();
});

// 加載質量報告
async function loadQualityReport() {
    try {
        const response = await fetch(`${API_BASE}/quality-report/${taskId}`);
        const data = await response.json();

        if (data.status === 'success') {
            qualityReport = data.report;
            allParagraphs = data.report.all_paragraphs;
            displayReport();
        } else {
            throw new Error(data.error || '加載失敗');
        }
    } catch (error) {
        console.error('加載質量報告失敗:', error);
        showToast(`加載失敗: ${error.message}`, 'error');
        document.getElementById('loading').style.display = 'none';
        document.getElementById('emptyState').style.display = 'block';
    }
}

// 顯示報告
function displayReport() {
    document.getElementById('loading').style.display = 'none';

    // 顯示統計信息
    const stats = qualityReport.stats;
    const summary = qualityReport.summary;

    document.getElementById('totalCount').textContent = summary.total;
    document.getElementById('lowQualityCount').textContent = summary.low_quality_count;
    document.getElementById('retriedCount').textContent = stats.retried || 0;
    document.getElementById('qualityPercent').textContent =
        `${(100 - summary.low_quality_percent).toFixed(1)}%`;

    document.getElementById('statsBar').style.display = 'block';
    document.getElementById('filterBar').style.display = 'flex';
    document.getElementById('actionBar').style.display = 'flex';

    // 顯示段落列表
    applyFilter(currentFilter);
}

// 應用篩選
function applyFilter(filter) {
    currentFilter = filter;

    if (filter === 'all') {
        filteredParagraphs = [...allParagraphs];
    } else if (filter === 'low') {
        filteredParagraphs = allParagraphs.filter(p => (p.confidence || 1.0) < 0.7);
    } else if (filter === 'high') {
        filteredParagraphs = allParagraphs.filter(p => (p.confidence || 1.0) >= 0.7);
    }

    renderParagraphs();
}

// 渲染段落列表
function renderParagraphs() {
    const container = document.getElementById('paragraphList');
    container.innerHTML = '';

    if (filteredParagraphs.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>沒有符合條件的段落</p></div>';
        return;
    }

    filteredParagraphs.forEach(para => {
        const confidence = para.confidence || 1.0;
        const isLowQuality = confidence < 0.7;
        const isSelected = selectedIndices.has(para.index);

        const item = document.createElement('div');
        item.className = `paragraph-item ${isLowQuality ? 'low-quality' : ''} ${isSelected ? 'selected' : ''}`;
        item.dataset.index = para.index;

        item.innerHTML = `
            <div class="paragraph-header">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="checkbox" class="checkbox" data-index="${para.index}" ${isSelected ? 'checked' : ''}>
                    <span class="paragraph-index">#${para.index + 1}</span>
                </div>
                <span class="confidence-badge confidence-${getConfidenceLevel(confidence)}">
                    置信度: ${(confidence * 100).toFixed(0)}%
                </span>
            </div>
            <div class="paragraph-content">
                <div class="text-box original">
                    <label>原文</label>
                    <textarea readonly>${para.original || para.text}</textarea>
                </div>
                <div class="text-box translation">
                    <label>譯文</label>
                    <textarea data-index="${para.index}">${para.text}</textarea>
                </div>
            </div>
            <div class="paragraph-actions">
                <button class="btn-small btn-retry" data-index="${para.index}">
                    🔄 重新翻譯
                </button>
                <button class="btn-small btn-save" data-index="${para.index}">
                    💾 保存修改
                </button>
            </div>
        `;

        container.appendChild(item);
    });

    updateSelectedCount();
}

// 獲取置信度級別
function getConfidenceLevel(confidence) {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.5) return 'medium';
    return 'low';
}

// 設置事件監聽
function setupEventListeners() {
    // 篩選按鈕
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyFilter(btn.dataset.filter);
        });
    });

    // 批量重試
    document.getElementById('batchRetryBtn').addEventListener('click', batchRetry);

    // 保存全部
    document.getElementById('saveAllBtn').addEventListener('click', saveAll);

    // 下載文件
    document.getElementById('downloadBtn').addEventListener('click', downloadFile);

    // 段落操作（使用事件委託）
    document.getElementById('paragraphList').addEventListener('click', async (e) => {
        const target = e.target;

        // 複選框
        if (target.classList.contains('checkbox')) {
            const index = parseInt(target.dataset.index);
            if (target.checked) {
                selectedIndices.add(index);
            } else {
                selectedIndices.delete(index);
            }
            updateSelectedCount();
            renderParagraphs();
        }

        // 重新翻譯按鈕
        if (target.classList.contains('btn-retry')) {
            const index = parseInt(target.dataset.index);
            await retryParagraph(index);
        }

        // 保存按鈕
        if (target.classList.contains('btn-save')) {
            const index = parseInt(target.dataset.index);
            await saveParagraph(index);
        }
    });
}

// 更新選中數量
function updateSelectedCount() {
    const count = selectedIndices.size;
    document.getElementById('selectedCount').textContent =
        count > 0 ? `已選中 ${count} 段` : '';
    document.getElementById('batchRetryBtn').disabled = count === 0;
}

// 重新翻譯單個段落
async function retryParagraph(index) {
    const para = allParagraphs.find(p => p.index === index);
    if (!para) return;

    try {
        showToast('重新翻譯中...', 'info');

        // 獲取API配置
        const apiKey = localStorage.getItem('translate_api_key');
        const baseUrl = localStorage.getItem('translate_base_url') || 'https://api.deepseek.com';
        const model = localStorage.getItem('translate_model') || 'deepseek-chat';

        if (!apiKey) {
            showToast('請先在翻譯頁面設置 API Key', 'error');
            return;
        }

        // 獲取上下文（前後 3 段）
        const context = allParagraphs
            .filter(p => p.index >= index - 3 && p.index < index)
            .map(p => p.original || p.text);

        const response = await fetch(`${API_BASE}/retry-paragraph`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                original: para.original || para.text,
                context: context,
                glossary: JSON.parse(localStorage.getItem('current_glossary') || '[]'),
                api_key: apiKey,
                base_url: baseUrl,
                model: model
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            // 更新段落
            para.text = data.translation;
            para.confidence = data.confidence;

            // 更新 textarea
            const textarea = document.querySelector(`textarea[data-index="${index}"]`);
            if (textarea) textarea.value = data.translation;

            // 更新置信度徽章
            const badge = document.querySelector(`[data-index="${index}"]`)
                .closest('.paragraph-item')
                .querySelector('.confidence-badge');
            badge.textContent = `置信度: ${(data.confidence * 100).toFixed(0)}%`;
            badge.className = `confidence-badge confidence-${getConfidenceLevel(data.confidence)}`;

            showToast('重新翻譯成功', 'success');
        } else {
            throw new Error(data.error || '翻譯失敗');
        }
    } catch (error) {
        console.error('重新翻譯失敗:', error);
        showToast(`翻譯失敗: ${error.message}`, 'error');
    }
}

// 批量重試
async function batchRetry() {
    if (selectedIndices.size === 0) return;

    const confirmed = confirm(`確定要重新翻譯選中的 ${selectedIndices.size} 個段落嗎？`);
    if (!confirmed) return;

    try {
        showToast(`批量重新翻譯 ${selectedIndices.size} 段...`, 'info');

        const apiKey = localStorage.getItem('translate_api_key');
        const baseUrl = localStorage.getItem('translate_base_url') || 'https://api.deepseek.com';
        const model = localStorage.getItem('translate_model') || 'deepseek-chat';

        if (!apiKey) {
            showToast('請先在翻譯頁面設置 API Key', 'error');
            return;
        }

        const paragraphs = Array.from(selectedIndices).map(index => {
            const para = allParagraphs.find(p => p.index === index);
            return {
                index: para.index,
                original: para.original || para.text
            };
        });

        const response = await fetch(`${API_BASE}/batch-retry`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                paragraphs: paragraphs,
                glossary: JSON.parse(localStorage.getItem('current_glossary') || '[]'),
                api_key: apiKey,
                base_url: baseUrl,
                model: model
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            // 更新所有段落
            data.translations.forEach(trans => {
                const para = allParagraphs.find(p => p.index === trans.index);
                if (para) {
                    para.text = trans.translation;
                    para.confidence = trans.confidence;
                }
            });

            // 重新渲染
            renderParagraphs();
            showToast(`成功重新翻譯 ${data.translations.length} 段`, 'success');

            // 清空選擇
            selectedIndices.clear();
            updateSelectedCount();
        } else {
            throw new Error(data.error || '批量翻譯失敗');
        }
    } catch (error) {
        console.error('批量翻譯失敗:', error);
        showToast(`批量翻譯失敗: ${error.message}`, 'error');
    }
}

// 保存單個段落
async function saveParagraph(index) {
    const textarea = document.querySelector(`textarea[data-index="${index}"]`);
    if (!textarea) return;

    const newText = textarea.value.trim();
    if (!newText) {
        showToast('譯文不能為空', 'error');
        return;
    }

    // 更新本地數據
    const para = allParagraphs.find(p => p.index === index);
    if (para) {
        para.text = newText;
        para.confidence = 1.0; // 手動編輯視為高質量
    }

    showToast('已保存修改（記得點擊"保存全部修改"）', 'success');
}

// 保存全部修改
async function saveAll() {
    try {
        showToast('保存修改中...', 'info');

        const response = await fetch(`${API_BASE}/update-translation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task_id: taskId,
                paragraphs: allParagraphs.map(p => ({
                    index: p.index,
                    text: p.text
                }))
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            showToast('保存成功！', 'success');
            // 重新加載報告
            await loadQualityReport();
        } else {
            throw new Error(data.error || '保存失敗');
        }
    } catch (error) {
        console.error('保存失敗:', error);
        showToast(`保存失敗: ${error.message}`, 'error');
    }
}

// 下載文件
function downloadFile() {
    // 觸發下載翻譯結果
    window.location.href = `${API_BASE}/download-result/${taskId}`;
    showToast('開始下載...', 'success');
}

// Toast 通知
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show';

    if (type === 'error') {
        toast.style.background = '#ff6b6b';
    } else if (type === 'success') {
        toast.style.background = '#51cf66';
    } else {
        toast.style.background = '#333';
    }

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
