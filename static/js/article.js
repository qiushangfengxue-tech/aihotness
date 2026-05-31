/* ═══════════════════════════════════════════════
   AIHOTNESS — Article Detail (Comments + Likes)
   ═══════════════════════════════════════════════ */

const ARTICLE_ID = document.getElementById('likeBtn')?.dataset.articleId;

// ── Likes ──

async function initLike() {
    const btn = document.getElementById('likeBtn');
    if (!btn || !state.user) return;

    try {
        const data = await apiGet(`/api/articles/${ARTICLE_ID}/like-status`);
        if (data && data.liked) {
            btn.classList.add('liked');
        }
    } catch (e) {
        // Silently fail
    }
}

async function toggleLike() {
    if (!state.user) {
        showToast('请先登录后点赞', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 1500);
        return;
    }

    const btn = document.getElementById('likeBtn');
    const countEl = document.getElementById('likeCount');

    try {
        const data = await apiPost(`/api/articles/${ARTICLE_ID}/like`);
        if (data) {
            btn.classList.toggle('liked', data.liked);
            if (countEl) countEl.textContent = data.count;
        }
    } catch (e) {
        showToast('操作失败，请重试', 'error');
    }
}

// ── Comments ──

async function loadComments() {
    const area = document.getElementById('commentsArea');
    if (!area) return;

    try {
        const data = await apiGet(`/api/articles/${ARTICLE_ID}/comments`);
        if (!data) {
            area.innerHTML = '<p class="comments-placeholder">加载评论失败</p>';
            return;
        }
        renderComments(data.comments || []);
    } catch (e) {
        area.innerHTML = '<p class="comments-placeholder">加载评论失败</p>';
    }
}

function renderComments(comments) {
    const area = document.getElementById('commentsArea');
    const countEl = document.getElementById('commentCount');

    if (countEl) countEl.textContent = comments.length;

    if (comments.length === 0) {
        area.innerHTML = '<p class="no-comments">还没有评论，来写第一条吧 ✍️</p>';
        return;
    }

    // Separate top-level comments and replies
    const topLevel = comments.filter(c => !c.parent_id);
    const replies = comments.filter(c => c.parent_id);

    let html = '';
    topLevel.forEach((c) => {
        html += renderCommentItem(c, false);
        // Find and render replies
        const childReplies = replies.filter(r => r.parent_id === c.id);
        childReplies.forEach((r) => {
            html += renderCommentItem(r, true);
        });
    });

    area.innerHTML = html;
}

function renderCommentItem(comment, isReply) {
    const authorName = comment.display_name || comment.username || '匿名';
    const timeAgoStr = timeAgo(comment.created_at);
    const isAuthor = state.user && (state.user.id === comment.user_id);
    const canDelete = isAuthor || (state.user && state.user.role === 'admin');

    return `
    <div class="comment-item ${isReply ? 'is-reply' : ''}" data-comment-id="${comment.id}">
        <div class="comment-header">
            <span class="comment-author">${escapeHtml(authorName)}</span>
            ${comment.is_hidden ? '<span class="comment-badge-author">已隐藏</span>' : ''}
            <span class="comment-time">${timeAgoStr}</span>
        </div>
        <div class="comment-content">${escapeHtml(comment.content)}</div>
        <div class="comment-actions">
            <button class="comment-action-btn" onclick="showReplyForm(${comment.id})">回复</button>
            ${canDelete ? `<button class="comment-action-btn danger" onclick="deleteComment(${comment.id})">删除</button>` : ''}
        </div>
        <div class="reply-form-wrapper" id="replyForm-${comment.id}" style="display:none;"></div>
    </div>`;
}

function showReplyForm(parentId) {
    const wrapper = document.getElementById(`replyForm-${parentId}`);
    if (!wrapper) return;

    if (wrapper.style.display !== 'none') {
        wrapper.style.display = 'none';
        return;
    }

    wrapper.innerHTML = `
    <div class="reply-form">
        <textarea placeholder="写下你的回复..." rows="2" maxlength="2000"></textarea>
        <div class="reply-form-actions">
            <button class="btn-save-draft" onclick="document.getElementById('replyForm-${parentId}').style.display='none'">取消</button>
            <button class="btn-publish" onclick="submitReply(${parentId}, this)">回复</button>
        </div>
    </div>`;
    wrapper.style.display = 'block';
    wrapper.querySelector('textarea').focus();
}

async function submitComment() {
    if (!state.user) {
        showToast('请先登录', 'error');
        return;
    }

    const input = document.getElementById('commentInput');
    const content = input.value.trim();
    if (!content) {
        showToast('请输入评论内容', 'error');
        return;
    }

    try {
        const data = await apiPost(`/api/articles/${ARTICLE_ID}/comments`, {
            content: content,
        });
        if (data) {
            input.value = '';
            showToast('评论发表成功', 'success');
            loadComments();
            // Update comment count
            const countEl = document.getElementById('commentCount');
            if (countEl) countEl.textContent = parseInt(countEl.textContent || '0') + 1;
        } else {
            showToast('评论失败，请重试', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

async function submitReply(parentId, btn) {
    if (!state.user) {
        showToast('请先登录', 'error');
        return;
    }

    const wrapper = document.getElementById(`replyForm-${parentId}`);
    const textarea = wrapper.querySelector('textarea');
    const content = textarea.value.trim();
    if (!content) {
        showToast('请输入回复内容', 'error');
        return;
    }

    btn.disabled = true;
    btn.textContent = '发送中...';

    try {
        const data = await apiPost(`/api/articles/${ARTICLE_ID}/comments`, {
            content: content,
            parent_id: parentId,
        });
        if (data) {
            wrapper.style.display = 'none';
            textarea.value = '';
            showToast('回复成功', 'success');
            loadComments();
        } else {
            showToast('回复失败', 'error');
            btn.disabled = false;
            btn.textContent = '回复';
        }
    } catch (e) {
        showToast('网络错误', 'error');
        btn.disabled = false;
        btn.textContent = '回复';
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
            // Update comment count
            const countEl = document.getElementById('commentCount');
            if (countEl) {
                const current = parseInt(countEl.textContent || '0');
                countEl.textContent = Math.max(0, current - 1);
            }
        } else {
            const data = await resp.json().catch(() => ({}));
            showToast(data.detail || '删除失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

// ── Keyboard shortcut ──
function initCommentKeyboard() {
    const input = document.getElementById('commentInput');
    if (!input) return;

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitComment();
        }
    });
}

// ── Rewrite trigger ──

async function triggerRewrite(articleId, btnElement) {
    if (!state.user) {
        showToast('请先登录后使用 AI 改写', 'error');
        setTimeout(() => { window.location.href = '/login'; }, 1500);
        return;
    }

    const btn = btnElement || document.querySelector('.notice-actions .btn-outline');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '改写中...';
    }

    try {
        const data = await apiPost(`/api/articles/${articleId}/rewrite`);
        if (data && data.status === 'success') {
            showToast('改写完成，正在刷新...', 'success');
            setTimeout(() => { window.location.reload(); }, 1500);
        } else {
            showToast('改写失败，请稍后重试', 'error');
            if (btn) {
                btn.disabled = false;
                btn.textContent = '🤖 AI 改写';
            }
        }
    } catch (e) {
        showToast('网络错误', 'error');
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🤖 AI 改写';
        }
    }
}

// ── Init ──
function initArticle() {
    const likeBtn = document.getElementById('likeBtn');
    if (likeBtn) likeBtn.addEventListener('click', toggleLike);

    initLike();
    loadComments();
    initCommentKeyboard();

    // Show/hide comment form based on auth state
    const commentForm = document.getElementById('commentForm');
    const loginPrompt = document.getElementById('commentLoginPrompt');
    if (state.user) {
        if (commentForm) commentForm.style.display = 'block';
        if (loginPrompt) loginPrompt.style.display = 'none';
    } else {
        if (commentForm) commentForm.style.display = 'none';
        if (loginPrompt) loginPrompt.style.display = 'block';
    }
}

// Run after main.js init completes
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initArticle, 200));
} else {
    setTimeout(initArticle, 200);
}
