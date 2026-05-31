/* ═══════════════════════════════════════════════
   AIHOTNESS — Admin Dashboard
   ═══════════════════════════════════════════════ */

// ── Auth check ──
function requireAdmin() {
    if (!state.user) {
        showToast('请先登录', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 1500);
        return false;
    }
    if (state.user.role !== 'admin') {
        showToast('需要管理员权限', 'error');
        setTimeout(() => { window.location.href = '/'; }, 1500);
        return false;
    }
    return true;
}

// ── Dashboard Stats ──
async function loadStats() {
    if (!requireAdmin()) return;

    try {
        const data = await apiGet('/api/admin/stats');
        if (!data || !data.stats) return;

        const s = data.stats;
        setText('statTotalArticles', s.total_articles);
        setText('statTotalUsers', s.total_users);
        setText('statTotalComments', s.total_comments);
        setText('statTotalLikes', s.total_likes);
        setText('statToday', s.articles_today);
        setText('statRewritten', s.rewritten);
        setText('statOriginal', s.original);
        setText('statRecent7d', s.recent_articles_7d);

        // Top sources
        const sourcesEl = document.getElementById('topSources');
        if (sourcesEl && s.top_sources) {
            if (s.top_sources.length === 0) {
                sourcesEl.innerHTML = '<p class="no-comments">暂无数据</p>';
            } else {
                sourcesEl.innerHTML = s.top_sources.map(src =>
                    `<div class="source-row">
                        <span class="source-row-name">${escapeHtml(src.source_name)}</span>
                        <span class="source-row-count">${src.count} 篇文章</span>
                    </div>`
                ).join('');
            }
        }
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val ?? '--';
}

// ── Article Management ──
let allArticles = [];

async function loadArticles() {
    if (!requireAdmin()) return;

    try {
        const data = await apiGet('/api/admin/articles?limit=200');
        if (!data) return;
        allArticles = data.articles || [];

        const totalEl = document.getElementById('articlesTotal');
        if (totalEl) totalEl.textContent = `共 ${data.total} 篇文章`;

        renderArticles(allArticles);
    } catch (e) {
        console.error('Failed to load articles:', e);
    }
}

function renderArticles(articles) {
    const tbody = document.getElementById('articlesBody');
    if (!tbody) return;

    if (articles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8"><p class="no-comments">暂无文章</p></td></tr>';
        return;
    }

    tbody.innerHTML = articles.map(a => `
        <tr>
            <td class="article-title-cell">
                <a href="/article/${a.id}" target="_blank">${escapeHtml(a.title || '无标题')}</a>
            </td>
            <td>${escapeHtml(a.source_name)}</td>
            <td><span class="type-badge ${a.article_type || 'rss'}">${a.article_type || 'rss'}</span></td>
            <td><span class="importance-badge ${(a.importance || 'c').toLowerCase()}">${a.importance || 'C'}</span></td>
            <td>${escapeHtml(a.category || '--')}</td>
            <td>❤️ ${a.like_count || 0} 💬 ${a.comment_count || 0}</td>
            <td>${timeAgo(a.collected_at)}</td>
            <td>
                <div class="action-btns">
                    <button class="action-btn" onclick="window.open('/article/${a.id}','_blank')">查看</button>
                    <button class="action-btn danger" onclick="deleteArticle('${a.id}')">删除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function filterArticles() {
    const search = document.getElementById('articleSearch')?.value?.toLowerCase() || '';
    if (!search) {
        renderArticles(allArticles);
        return;
    }
    const filtered = allArticles.filter(a =>
        (a.title || '').toLowerCase().includes(search)
    );
    renderArticles(filtered);
}

async function deleteArticle(articleId) {
    if (!confirm('确定删除此文章？此操作不可撤销。')) return;

    try {
        const resp = await fetch(`/api/admin/articles/${articleId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        if (resp.ok) {
            showToast('文章已删除', 'success');
            loadArticles();
        } else {
            const data = await resp.json().catch(() => ({}));
            showToast(data.detail || '删除失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

// ── User Management ──
async function loadUsers() {
    if (!requireAdmin()) return;

    try {
        const data = await apiGet('/api/admin/users');
        if (!data) return;
        renderUsers(data.users || []);
    } catch (e) {
        console.error('Failed to load users:', e);
    }
}

function renderUsers(users) {
    // This is for future use — user management on a separate tab if needed
}

// ── Comment Moderation ──
async function loadComments() {
    if (!requireAdmin()) return;

    try {
        const data = await apiGet('/api/admin/comments?limit=200');
        if (!data) return;

        const totalEl = document.getElementById('commentsTotal');
        if (totalEl) totalEl.textContent = `共 ${data.total} 条评论`;

        renderCommentsTable(data.comments || []);
    } catch (e) {
        console.error('Failed to load comments:', e);
    }
}

function renderCommentsTable(comments) {
    const tbody = document.getElementById('commentsBody');
    if (!tbody) return;

    if (comments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6"><p class="no-comments">暂无评论</p></td></tr>';
        return;
    }

    tbody.innerHTML = comments.map(c => `
        <tr>
            <td>
                <a href="/article/${c.article_id}" target="_blank" class="comment-article-link">
                    ${escapeHtml(c.article_title || '--')}
                </a>
            </td>
            <td>${escapeHtml(c.display_name || c.username || '匿名')}</td>
            <td class="comment-content-cell">${escapeHtml(c.content)}</td>
            <td>${c.is_hidden ? '<span style="color:#ef4444;">已隐藏</span>' : '<span style="color:#10b981;">正常</span>'}</td>
            <td>${timeAgo(c.created_at)}</td>
            <td>
                <div class="action-btns">
                    ${c.is_hidden
                        ? `<button class="action-btn success" onclick="toggleCommentVisibility(${c.id}, false)">显示</button>`
                        : `<button class="action-btn danger" onclick="toggleCommentVisibility(${c.id}, true)">隐藏</button>`
                    }
                    <button class="action-btn danger" onclick="deleteComment(${c.id})">删除</button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function toggleCommentVisibility(commentId, hide) {
    try {
        const resp = await fetch(`/api/admin/comments/${commentId}/hide`, {
            method: 'PUT',
            headers: getAuthHeaders(),
        });
        if (resp.ok) {
            showToast(hide ? '评论已隐藏' : '评论已显示', 'success');
            loadComments();
        } else {
            showToast('操作失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

async function deleteComment(commentId) {
    if (!confirm('确定删除此评论？')) return;

    try {
        const resp = await fetch(`/api/comments/${commentId}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        if (resp.ok) {
            showToast('评论已删除', 'success');
            loadComments();
        } else {
            showToast('删除失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

// ── Init ──
function initAdmin() {
    // Wait for auth state from main.js init
    setTimeout(() => {
        if (!requireAdmin()) return;

        // Check which page we're on
        const path = window.location.pathname;

        if (path === '/admin' || path === '/admin/') {
            loadStats();
        }

        if (path.includes('/admin/articles')) {
            loadArticles();
        }

        if (path.includes('/admin/comments')) {
            loadComments();
        }

        renderAuthUI();
    }, 300);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdmin);
} else {
    initAdmin();
}
