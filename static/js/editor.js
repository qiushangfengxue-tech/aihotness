/* ═══════════════════════════════════════════════
   AIHOTNESS — Markdown Editor
   ═══════════════════════════════════════════════ */

// ── State ──
const editorState = {
    articleId: null,  // null = new article
    isDirty: false,
    autoSaveTimer: null,
};

// ── DOM refs ──
const mdEditor = document.getElementById('markdownEditor');
const previewPane = document.getElementById('previewPane');
const titleInput = document.getElementById('articleTitle');
const categorySelect = document.getElementById('articleCategory');
const statusEl = document.getElementById('editorStatus');
const wordCountEl = document.getElementById('wordCount');

// ── Simple Markdown → HTML renderer ──
function renderMarkdown(text) {
    if (!text || !text.trim()) {
        return '<div class="editor-empty-preview">在左侧开始写作，实时预览将显示在这里</div>';
    }

    let html = text
        // Escape HTML
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')

        // Headings (must be before bold/italic)
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')

        // Horizontal rule
        .replace(/^---$/gm, '<hr>')
        .replace(/^\*\*\*$/gm, '<hr>')

        // Blockquotes
        .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')

        // Inline formatting
        .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/~~(.+?)~~/g, '<s>$1</s>')
        .replace(/`(.+?)`/g, '<code>$1</code>')

        // Images
        .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">')

        // Links
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')

        // Unordered lists
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        // Ordered lists
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')

        // Paragraphs (double newlines)
        .replace(/\n\n/g, '</p><p>')

        // Single newlines within paragraphs
        .replace(/\n/g, '<br>')

        // Wrap in paragraph if not already
        .replace(/^((?!<[hHpPbdio]|<li|<pre).*)$/gm, match => {
            if (!match.startsWith('<') && match.trim()) {
                return `<p>${match}</p>`;
            }
            return match;
        });

    // Clean up nested paragraphs from list items
    html = html.replace(/<li><p>/g, '<li>').replace(/<\/p><\/li>/g, '</li>');

    // Wrap consecutive <li> in <ul>
    html = html.replace(/(<li>[\s\S]*?(?:<\/li>[\s\S]*?)*<\/li>)/g, '<ul>$1</ul>');

    // Merge adjacent blockquotes
    html = html.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');

    return html;
}

// ── Update Preview ──
function updatePreview() {
    const text = mdEditor.value;
    previewPane.innerHTML = renderMarkdown(text);
    updateWordCount(text);
    editorState.isDirty = true;
    updateStatus('未保存');
}

function updateWordCount(text) {
    if (!text) {
        wordCountEl.textContent = '0 字';
        return;
    }
    // Count Chinese characters + words
    const cn = (text.match(/[一-鿿]/g) || []).length;
    const en = text.replace(/[一-鿿]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 0).length;
    const total = cn + en;
    wordCountEl.textContent = `${total} 字`;
}

function updateStatus(msg) {
    statusEl.textContent = msg;
    clearTimeout(statusEl._resetTimer);
    statusEl._resetTimer = setTimeout(() => {
        if (!editorState.isDirty) statusEl.textContent = '已保存';
    }, 3000);
}

// ── Insert Markdown syntax ──
function insertMd(before, after) {
    const start = mdEditor.selectionStart;
    const end = mdEditor.selectionEnd;
    const selected = mdEditor.value.substring(start, end);

    // Handle newline prefixes for block elements
    let prefix = before;
    let suffix = after;

    // If inserting at start of line for block elements
    if (before.startsWith('\n') && start > 0) {
        const beforeChar = mdEditor.value[start - 1];
        if (beforeChar !== '\n') {
            prefix = '\n' + prefix.trimStart();
        } else {
            prefix = prefix.trimStart();
        }
    }

    const replacement = prefix + selected + suffix;
    mdEditor.setRangeText(replacement, start, end, 'end');
    mdEditor.focus();
    updatePreview();
}

// ── Draft save/restore ──
function saveDraft() {
    const data = {
        title: titleInput.value,
        content: mdEditor.value,
        category: categorySelect.value,
        savedAt: new Date().toISOString(),
    };
    localStorage.setItem('aihotness-draft', JSON.stringify(data));
    editorState.isDirty = false;
    updateStatus('草稿已保存');
    showToast('草稿已保存到本地', 'success');
}

function loadDraft() {
    try {
        const raw = localStorage.getItem('aihotness-draft');
        if (!raw) return;
        const data = JSON.parse(raw);
        if (data.title) titleInput.value = data.title;
        if (data.content) {
            mdEditor.value = data.content;
            updatePreview();
        }
        if (data.category) categorySelect.value = data.category;

        // Show restore notification
        const timeAgo = data.savedAt ? timeAgo(data.savedAt) : '之前';
        showToast(`已恢复草稿（${timeAgo}）`, '');
    } catch (e) {
        console.error('Failed to load draft:', e);
    }
}

// ── Publish ──
async function publishArticle() {
    const title = titleInput.value.trim();
    const content = mdEditor.value.trim();
    const category = categorySelect.value;

    if (!title) {
        showToast('请输入文章标题', 'error');
        titleInput.focus();
        return;
    }
    if (!content) {
        showToast('请输入文章内容', 'error');
        mdEditor.focus();
        return;
    }

    const btn = document.getElementById('publishBtn');
    btn.disabled = true;
    btn.textContent = '发布中...';

    try {
        const method = editorState.articleId ? 'PUT' : 'POST';
        const url = editorState.articleId
            ? `/api/content/${editorState.articleId}`
            : '/api/content';

        const resp = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify({
                title,
                content_md: content,
                category: category || '未分类',
                tags: [category || '未分类'],
            }),
        });

        const data = await resp.json();

        if (resp.ok && data.article) {
            editorState.articleId = data.article.id;
            editorState.isDirty = false;
            // Clear draft on successful publish
            localStorage.removeItem('aihotness-draft');
            showToast('文章发布成功！', 'success');
            updateStatus('已发布');
            btn.textContent = '✅ 已发布';
            setTimeout(() => {
                window.location.href = `/article/${data.article.id}`;
            }, 1000);
        } else {
            showToast(data.detail || '发布失败，请重试', 'error');
            btn.disabled = false;
            btn.textContent = '📝 发布文章';
        }
    } catch (err) {
        showToast('网络错误，请稍后重试', 'error');
        btn.disabled = false;
        btn.textContent = '📝 发布文章';
    }
}

// ── Auto-save ──
function startAutoSave() {
    mdEditor.addEventListener('input', () => {
        clearTimeout(editorState.autoSaveTimer);
        editorState.autoSaveTimer = setTimeout(saveDraft, 30000); // Auto-save every 30s
    });

    titleInput.addEventListener('input', () => {
        editorState.isDirty = true;
        updateStatus('未保存');
    });
}

// ── Keyboard shortcuts ──
function initKeyboardShortcuts() {
    mdEditor.addEventListener('keydown', (e) => {
        // Ctrl+S = save draft
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            saveDraft();
        }
        // Tab = indent
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = mdEditor.selectionStart;
            mdEditor.setRangeText('    ', start, start, 'end');
            updatePreview();
        }
    });
}

// ── Init ──
function initEditor() {
    // Check if user is logged in
    if (!state.user) {
        showToast('请先登录后再写文章', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 1500);
        return;
    }

    // Load existing article if editing
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length === 3 && pathParts[1] === 'editor' && pathParts[2]) {
        editorState.articleId = pathParts[2];
        loadExistingArticle(editorState.articleId);
    } else {
        loadDraft();
    }

    mdEditor.addEventListener('input', updatePreview);
    startAutoSave();
    initKeyboardShortcuts();

    // Warn before leaving with unsaved changes
    window.addEventListener('beforeunload', (e) => {
        if (editorState.isDirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

async function loadExistingArticle(articleId) {
    try {
        const data = await apiGet(`/api/articles/${articleId}`);
        if (data && data.article) {
            const a = data.article;
            titleInput.value = a.title;
            mdEditor.value = a.content_md || '';
            categorySelect.value = a.category || '';
            updatePreview();
            updateStatus('编辑已有文章');
        } else {
            showToast('文章不存在', 'error');
        }
    } catch (e) {
        showToast('加载文章失败', 'error');
    }
}

// ── Boot ──
function bootEditor() {
    // Wait for auth state from main.js to resolve (main.js sets state._authChecked)
    if (state._authChecked) {
        initEditor();
    } else {
        // Retry until auth is resolved
        let attempts = 0;
        const check = () => {
            if (state._authChecked) { initEditor(); return; }
            attempts++;
            if (attempts > 30) { initEditor(); return; } // Timeout after ~3s
            setTimeout(check, 100);
        };
        check();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(bootEditor, 200));
} else {
    setTimeout(bootEditor, 200);
}
