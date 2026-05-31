/* ═══════════════════════════════════════════════
   AIHOTNESS — Main Application
   ═══════════════════════════════════════════════ */

// ── State ──
const state = {
    articles: [],
    sources: [],
    categories: [],
    offset: 0,
    limit: 30,
    filters: {
        importance: '',
        category: '',
        source: '',
    },
    currentSection: 'news',
    loading: false,
    hasMore: true,
    user: null,
    theme: localStorage.getItem('aihotness-theme') || 'dark',
    searchQuery: '',
};

// ── DOM References ──
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Particle Background ──
function initParticles() {
    const canvas = document.getElementById('particles');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let width, height, particles = [];

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    function createParticles(count = 80) {
        particles = [];
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                r: Math.random() * 1.5 + 0.5,
                alpha: Math.random() * 0.5 + 0.1,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    const alpha = (1 - dist / 150) * 0.15;
                    ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
        particles.forEach((p) => {
            ctx.fillStyle = `rgba(0, 212, 255, ${p.alpha})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fill();
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;
        });
        requestAnimationFrame(draw);
    }

    resize();
    createParticles();
    draw();
    window.addEventListener('resize', () => { resize(); createParticles(); });
}

// ── Theme ──
function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    const btn = document.getElementById('themeToggle');
    if (btn) {
        btn.addEventListener('click', toggleTheme);
        updateThemeIcon();
    }
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('aihotness-theme', state.theme);
    updateThemeIcon();
}

function updateThemeIcon() {
    const icon = document.querySelector('.theme-icon');
    if (icon) icon.textContent = state.theme === 'dark' ? '☀️' : '🌙';
}

// ── Auth ──
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

async function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        state._authChecked = true;
        renderAuthUI();
        return;
    }

    try {
        const resp = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!resp.ok) {
            localStorage.removeItem('token');
            state._authChecked = true;
            renderAuthUI();
            return;
        }
        const data = await resp.json();
        state.user = data.user;
    } catch {
        // Network error, don't clear token — might be temporary
    }
    state._authChecked = true;
    renderAuthUI();
}

function renderAuthUI() {
    const guestLinks = document.getElementById('guestLinks');
    const userMenu = document.getElementById('userMenu');
    if (!guestLinks && !userMenu) return;

    if (state.user) {
        if (guestLinks) guestLinks.style.display = 'none';
        if (userMenu) {
            userMenu.style.display = 'flex';
            const nameEl = document.getElementById('userDisplayName');
            if (nameEl) nameEl.textContent = state.user.display_name || state.user.username;
            const adminLink = document.getElementById('adminLink');
            if (adminLink) adminLink.style.display = state.user.role === 'admin' ? 'block' : 'none';
        }
    } else {
        if (guestLinks) guestLinks.style.display = 'flex';
        if (userMenu) userMenu.style.display = 'none';
    }
}

function logout() {
    localStorage.removeItem('token');
    state.user = null;
    renderAuthUI();
    showToast('已退出登录', '');
}

// ── API Calls ──
async function apiGet(path) {
    try {
        const resp = await fetch(path, { headers: getAuthHeaders() });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error(`API GET ${path} failed:`, err);
        return null;
    }
}

async function apiPost(path, body = null) {
    try {
        const options = { method: 'POST', headers: getAuthHeaders() };
        if (body) options.body = JSON.stringify(body);
        const resp = await fetch(path, options);
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        return await resp.json().catch(() => true);
    } catch (err) {
        console.error(`API POST ${path} failed:`, err);
        return null;
    }
}

// ── Load Articles ──
async function loadArticles(reset = false) {
    if (state.loading) return;
    state.loading = true;

    if (reset) {
        state.offset = 0;
        state.hasMore = true;
    }

    const params = new URLSearchParams({
        limit: String(state.limit),
        offset: String(state.offset),
    });

    if (state.filters.importance) params.set('importance', state.filters.importance);
    if (state.filters.category && state.currentSection === 'news') params.set('category', state.filters.category);
    if (state.currentSection === 'papers') params.set('category', '学术论文');
    if (state.currentSection === 'tutorials') params.set('category', 'AI教程');
    if (state.filters.source) params.set('source', state.filters.source);
    if (state.searchQuery) params.set('q', state.searchQuery);

    const data = await apiGet(`/api/articles?${params}`);
    if (!data) {
        showToast('加载失败，请稍后再试', 'error');
        state.loading = false;
        return;
    }

    if (reset) state.articles = data.articles;
    else state.articles = [...state.articles, ...data.articles];

    state.offset = data.offset + data.articles.length;
    state.hasMore = data.articles.length === state.limit;
    renderArticles(reset);
    state.loading = false;
}

// ── Render Articles ──
function renderArticles(reset = false) {
    const grid = document.getElementById('articleGrid');
    const sSection = document.getElementById('sLevelSection');
    const sList = document.getElementById('sLevelList');
    const loadMoreBtn = document.getElementById('loadMore');
    if (!grid) return;

    const sArticles = state.articles.filter((a) => a.importance === 'S');
    const otherArticles = state.articles.filter((a) => a.importance !== 'S');

    // S-Level
    if (sArticles.length > 0) {
        sSection.style.display = 'block';
        sList.innerHTML = sArticles.map((a) => {
            const linkUrl = a.content_html ? `/article/${a.id}` : a.url;
            const target = a.content_html ? '' : ' target="_blank" rel="noopener noreferrer"';
            return `
            <a href="${linkUrl}"${target} class="s-level-card">
                <span class="s-level-tag">S</span>
                <div>
                    <div class="card-title">${escapeHtml(a.title)}</div>
                    ${a.summary ? `<div class="card-summary">${escapeHtml(a.summary)}</div>` : ''}
                    <div class="card-meta">
                        ${escapeHtml(a.source_name)} · ${timeAgo(a.published_at)}
                    </div>
                </div>
            </a>`;
        }).join('');
    } else {
        sSection.style.display = 'none';
    }

    // Grid articles
    if (reset) grid.innerHTML = '';
    else {
        const loadingState = grid.querySelector('.loading-state');
        if (loadingState) loadingState.remove();
    }

    if (otherArticles.length === 0 && state.articles.length === 0) {
        grid.innerHTML = `
            <div class="loading-state">
                <p style="font-size: 48px; margin-bottom: 12px;">📡</p>
                <p>正在采集最新资讯...</p>
                <p style="font-size: 13px; color: var(--text-muted); margin-top: 8px;">首次采集可能需要 1-2 分钟</p>
            </div>`;
        return;
    }

    const html = otherArticles.map((a) => {
        const linkUrl = a.content_html ? `/article/${a.id}` : a.url;
        const target = a.content_html ? '' : ' target="_blank" rel="noopener noreferrer"';
        const category = a.category || '未分类';
        const isExternal = !a.content_html && a.article_type !== 'original';
        return `
        <a href="${linkUrl}"${target} class="article-card">
            <div class="card-top">
                <span class="importance-badge ${(a.importance || 'c').toLowerCase()}">${a.importance || 'C'}</span>
                <span class="card-category">${escapeHtml(category)}</span>
                <span class="card-source">${escapeHtml(a.source_name)}</span>
                ${isExternal ? '<span class="card-badge-external">外部来源</span>' : ''}
            </div>
            <div class="card-title">${escapeHtml(a.title)}</div>
            ${a.summary ? `<div class="card-summary">${escapeHtml(a.summary)}</div>` : ''}
            <div class="card-footer">
                <span class="card-time">${timeAgo(a.published_at)}</span>
                ${a.like_count ? `<span class="card-time">❤️ ${a.like_count}</span>` : ''}
                ${a.comment_count ? `<span class="card-time">💬 ${a.comment_count}</span>` : ''}
                <div class="card-tags">
                    ${(a.tags || []).slice(0, 3).map((t) => `<span class="card-tag">${escapeHtml(t)}</span>`).join('')}
                </div>
            </div>
        </a>`;
    }).join('');

    if (reset) grid.innerHTML = html;
    else grid.insertAdjacentHTML('beforeend', html);

    if (loadMoreBtn) loadMoreBtn.style.display = state.hasMore ? 'flex' : 'none';
}

// ── Load Sources ──
async function loadSources() {
    const data = await apiGet('/api/sources');
    if (!data || !data.sources) return;
    state.sources = data.sources;
    renderSources();
}

function filterBySource(sourceName) {
    state.filters.category = '';
    state.filters.source = sourceName;
    $$('[data-filter="category"]').forEach((btn) => btn.classList.remove('active'));
    // Update navbar active section
    state.currentSection = 'news';
    $$('.nav-link').forEach((link) => link.classList.remove('active'));
    document.querySelector('.nav-link[data-section="news"]')?.classList.add('active');
    loadArticles(true);
    // Scroll to article grid
    document.getElementById('articleGrid')?.scrollIntoView({ behavior: 'smooth' });
}

function renderSources() {
    const grid = document.getElementById('sourcesGrid');
    if (!grid) return;
    if (state.sources.length === 0) {
        grid.innerHTML = '<div class="loading-state small"><p>暂无数据</p></div>';
        return;
    }
    grid.innerHTML = state.sources.map((s) => `
        <div class="source-card" onclick="filterBySource('${escapeHtml(s.source_name)}')" style="cursor:pointer;">
            <span class="source-name">${escapeHtml(s.source_name)}</span>
            <span class="source-type">${s.source_type}</span>
            <span class="source-count">${s.count} 篇文章</span>
            ${s.latest ? `<span class="source-latest">最近: ${timeAgo(s.latest)}</span>` : ''}
        </div>`
    ).join('');
}

// ── Load Hero Stats ──
async function loadStats() {
    const data = await apiGet('/api/articles?limit=1&days=1');
    const totalData = await apiGet('/api/articles?limit=1');
    if (data) {
        const statToday = document.getElementById('statToday');
        if (statToday) statToday.textContent = data.total;
    }
    if (totalData) {
        const statArticles = document.getElementById('statArticles');
        if (statArticles) statArticles.textContent = totalData.total;
    }
    const statSources = document.getElementById('statSources');
    if (statSources && state.sources.length > 0) statSources.textContent = state.sources.length;
}

// ── Load Categories ──
async function loadCategories() {
    const data = await apiGet('/api/categories');
    if (!data || !data.categories) return;
    state.categories = data.categories;
    const container = document.getElementById('categoryFilters');
    if (!container) return;

    data.categories.forEach((cat) => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.filter = 'category';
        btn.dataset.value = cat.name;
        btn.textContent = cat.display_name;
        container.appendChild(btn);
        btn.addEventListener('click', () => toggleFilter('category', cat.name));
    });
}

// ── Filter Logic ──
function toggleFilter(type, value) {
    if (state.filters[type] === value) state.filters[type] = '';
    else state.filters[type] = value;

    // Clear source filter when changing category/importance
    if (type !== 'source') state.filters.source = '';

    $$(`[data-filter="${type}"]`).forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.value === state.filters[type]);
    });
    loadArticles(true);
}

function loadMore() { loadArticles(false); }

// ── Search ──
function doSearch() {
    const input = document.getElementById('searchInput');
    if (!input) return;
    const q = input.value.trim();
    if (state.searchQuery === q) return;
    state.searchQuery = q;

    const clearBtn = document.getElementById('searchClear');
    if (clearBtn) clearBtn.style.display = q ? 'flex' : 'none';

    // Show search state
    const heroTitle = document.querySelector('.hero-title');
    if (q) {
        // Switch to 'news' section and show search results
        state.currentSection = 'news';
        state.filters.category = '';
        state.filters.source = '';
        state.filters.importance = '';
        $$('.filter-btn').forEach((btn) => btn.classList.remove('active'));
        document.querySelector('.filter-btn[data-value=""]')?.classList.add('active');
    }

    loadArticles(true);

    if (q) {
        showToast('搜索: "' + q + '"', '');
    }
}

function clearSearch() {
    const input = document.getElementById('searchInput');
    if (input) {
        input.value = '';
        state.searchQuery = '';
        document.getElementById('searchClear').style.display = 'none';
        loadArticles(true);
    }
}

function initSearch() {
    const input = document.getElementById('searchInput');
    if (!input) return;

    let timer = null;
    input.addEventListener('input', function() {
        clearTimeout(timer);
        timer = setTimeout(doSearch, 400);
    });
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            clearTimeout(timer);
            doSearch();
        }
    });
}

async function triggerCollection() {
    const btn = document.querySelector('.btn-primary');
    if (btn) btn.disabled = true;
    showToast('正在刷新数据...', '');
    await apiPost('/api/collect');
    setTimeout(async () => {
        await loadArticles(true);
        await loadSources();
        await loadStats();
        showToast('数据已刷新', 'success');
        if (btn) btn.disabled = false;
    }, 3000);
}

// ── Navigation ──
function initNavigation() {
    const path = window.location.pathname;
    if (path.includes('papers')) state.currentSection = 'papers';
    else if (path.includes('tutorials')) state.currentSection = 'tutorials';
    else state.currentSection = 'news';

    $$('.nav-link').forEach((link) => {
        link.classList.toggle('active', link.dataset.section === state.currentSection);
    });
}

// ── Toast ──
function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

// ── Utilities ──
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function timeAgo(dateStr) {
    if (!dateStr) return '未知';
    const now = new Date();
    const date = new Date(dateStr);
    const diffMins = Math.floor((now - date) / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffHours < 24) return `${diffHours} 小时前`;
    if (diffDays < 30) return `${diffDays} 天前`;
    return date.toLocaleDateString('zh-CN');
}

function updateFooterTime() {
    const el = document.getElementById('footerTime');
    if (el) el.textContent = `更新时间: ${new Date().toLocaleString('zh-CN')}`;
}

// ── Filter Event Listeners ──
function initFilters() {
    $$('[data-filter="importance"]').forEach((btn) => {
        btn.addEventListener('click', () => toggleFilter('importance', btn.dataset.value));
    });
}

// ── Auto Refresh ──
function startAutoRefresh() {
    setInterval(() => { loadStats(); updateFooterTime(); }, 60000);
}

// ── Init ──
async function init() {
    initParticles();
    initTheme();
    initNavigation();
    initFilters();
    initSearch();
    await checkAuth();

    await Promise.all([loadSources(), loadCategories()]);
    await loadArticles(true);
    await loadStats();
    updateFooterTime();
    startAutoRefresh();

    // Logout handler
    document.getElementById('logoutBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        logout();
    });

    // User dropdown toggle
    document.querySelector('.user-dropdown-trigger')?.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelector('.dropdown-menu')?.classList.toggle('show');
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
        document.querySelector('.dropdown-menu')?.classList.remove('show');
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
