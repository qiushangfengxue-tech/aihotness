"""AIHOTNESS — FastAPI Application"""

import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jinja2 import Environment, FileSystemLoader

from .config import APP_TITLE, APP_DESCRIPTION, COLLECTION_INTERVAL_MINUTES, LLM_ENABLED, BASE_DIR
from .database import (
    init_db, get_articles, get_sources_stats, get_categories,
    create_user, get_user_by_id, get_user_by_username, get_user_by_email,
    update_user, get_user_count, get_article_by_id,
    create_original_article, update_article_content,
    get_articles_by_author, get_community_articles,
    create_comment, get_comments_by_article, delete_comment,
    toggle_like, get_like_status, hide_comment,
    get_all_users, get_admin_stats,
    get_all_articles_admin, delete_article_admin,
    get_all_comments_admin, get_connection,
)
from .collector import run_collection
from .processor import process_unprocessed, rewrite_article
from .auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, require_user, require_admin,
)


# ── Jinja2 template engine ──
_template_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    auto_reload=False,
)


def render_template(name: str, context: dict) -> str:
    """Render a Jinja2 template directly."""
    template = _template_env.get_template(name)
    return template.render(context)


# ── Pydantic Models ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_一-鿿]+$")
    email: str = Field(min_length=5, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(default="", max_length=64)
    bio: str = Field(default="", max_length=500)


class ContentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_md: str = Field(min_length=1)
    category: str = Field(default="未分类", max_length=50)
    tags: list[str] = Field(default_factory=list)
    importance: str = Field(default="C", pattern="^[SABC]$")


class ContentUpdateRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    content_md: str = Field(default="")
    category: str = Field(default="", max_length=50)
    importance: str = Field(default="C", pattern="^[SABC]$")


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    parent_id: int | None = Field(default=None)


# ── Background collection scheduler ──

class CollectionScheduler:
    """Simple background scheduler for periodic collection."""

    def __init__(self, interval_minutes: int = 15):
        self.interval = interval_minutes * 60
        self._thread = None
        self._running = False
        self._last_run = None
        self._next_run = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"  [Scheduler] Collection every {self.interval//60} minutes")

    def stop(self):
        self._running = False

    def _loop(self):
        self._run_once()
        while self._running:
            time.sleep(self.interval)
            self._run_once()

    def _run_once(self):
        try:
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._next_run = None
            print(f"\n{'#'*50}")
            print(f"  Scheduled collection at {self._last_run}")
            print(f"{'#'*50}")

            run_collection()

            if LLM_ENABLED:
                process_unprocessed()

            self._next_run = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            print(f"  [Scheduler] Error in collection run: {e}")

    @property
    def status(self):
        return {
            "running": self._running,
            "interval_minutes": self.interval // 60,
            "last_run": self._last_run,
            "next_run": self._next_run,
        }


scheduler = CollectionScheduler(interval_minutes=COLLECTION_INTERVAL_MINUTES)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print(f"\n{'='*50}")
    print(f"  {APP_TITLE} starting up...")
    print(f"  LLM processing: {'ENABLED' if LLM_ENABLED else 'DISABLED (set DEEPSEEK_API_KEY)'}")
    print(f"{'='*50}\n")

    init_db()
    print("  Database initialized.")

    # Run initial collection in background so server starts immediately
    print("  Starting initial collection in background...")
    threading.Thread(
        target=lambda: (
            print("  Running initial collection..."),
            run_collection(),
            (LLM_ENABLED and (print("  Processing with DeepSeek LLM..."), process_unprocessed())),
        ),
        daemon=True,
    ).start()

    scheduler.start()
    yield

    scheduler.stop()
    print("  AIHOTNESS shutting down.")


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ═══════════════════════════════════════════════
#  AUTH API
# ═══════════════════════════════════════════════

@app.post("/api/auth/register")
async def api_register(data: RegisterRequest):
    """Register a new user. First user becomes admin."""
    # Check existing
    if get_user_by_username(data.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    if get_user_by_email(data.email):
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # Create user
    password_hash = get_password_hash(data.password)
    user_id = create_user(data.username, data.email, password_hash)
    if user_id is None:
        raise HTTPException(status_code=500, detail="注册失败，请重试")

    user = get_user_by_id(user_id)
    token = create_access_token({"sub": str(user_id), "role": user["role"]})

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@app.post("/api/auth/login")
async def api_login(data: LoginRequest):
    """Login with username/email and password."""
    user = get_user_by_username(data.username)
    if not user:
        # Try email
        user = get_user_by_email(data.username)

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token({"sub": str(user["id"]), "role": user["role"]})

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "display_name": user["display_name"],
            "bio": user["bio"],
            "role": user["role"],
        },
    }


@app.get("/api/auth/me")
async def api_auth_me(user: dict = Depends(require_user)):
    """Get current user info."""
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "display_name": user["display_name"],
            "bio": user["bio"],
            "avatar_url": user["avatar_url"],
            "role": user["role"],
            "created_at": user["created_at"],
        }
    }


@app.put("/api/auth/profile")
async def api_update_profile(data: ProfileUpdateRequest, user: dict = Depends(require_user)):
    """Update user profile."""
    update_user(user["id"], display_name=data.display_name, bio=data.bio)
    updated = get_user_by_id(user["id"])
    return {
        "user": {
            "id": updated["id"],
            "username": updated["username"],
            "email": updated["email"],
            "display_name": updated["display_name"],
            "bio": updated["bio"],
            "role": updated["role"],
        }
    }


# ═══════════════════════════════════════════════
#  CONTENT API (existing + new)
# ═══════════════════════════════════════════════

@app.get("/api/articles")
async def api_articles(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    importance: str = Query(None, pattern="^[SABC]$"),
    category: str = Query(None),
    source: str = Query(None),
    days: int = Query(None, ge=1, le=90),
    q: str = Query(None, max_length=100),
):
    """Get articles with filters."""
    articles, total = get_articles(
        limit=limit,
        offset=offset,
        importance=importance,
        category=category,
        source=source,
        days=days,
        q=q,
    )
    return {
        "articles": articles,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/articles/{article_id}")
async def api_article_detail(article_id: str):
    """Get a single article by ID."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"article": article}


@app.get("/api/sources")
async def api_sources():
    """Get source statistics."""
    return {"sources": get_sources_stats()}


@app.get("/api/categories")
async def api_categories():
    """Get available categories."""
    return {"categories": get_categories()}


@app.get("/api/status")
async def api_status():
    """Get system status."""
    # Get user count for richer status
    user_count = get_user_count()
    return {
        "name": APP_TITLE,
        "description": APP_DESCRIPTION,
        "llm_enabled": LLM_ENABLED,
        "collection": scheduler.status,
        "users": user_count,
        "version": "1.0.0",
    }


@app.post("/api/collect")
async def api_trigger_collection():
    """Manually trigger a collection run."""
    thread = threading.Thread(
        target=lambda: (run_collection(), process_unprocessed() if LLM_ENABLED else None),
        daemon=True,
    )
    thread.start()
    return {"status": "started", "message": "Collection triggered"}


# ═══════════════════════════════════════════════
#  REWRITE API
# ═══════════════════════════════════════════════

@app.post("/api/articles/{article_id}/rewrite")
async def api_rewrite_article(article_id: str, user: dict = Depends(require_user)):
    """Trigger LLM rewrite of an article."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    if article.get("is_rewritten"):
        raise HTTPException(status_code=400, detail="文章已改写")

    if not LLM_ENABLED:
        raise HTTPException(status_code=400, detail="LLM 未启用，请设置 DEEPSEEK_API_KEY")

    result = rewrite_article(article)
    if not result:
        raise HTTPException(status_code=500, detail="改写失败，请稍后重试")

    update_article_content(
        article_id,
        content_md=result["content_md"],
        content_html=result["content_html"],
    )
    # Also mark as rewritten
    from .database import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE articles SET is_rewritten = 1, article_type = 'rewrite' WHERE id = ?",
            (article_id,),
        )
        conn.commit()

    return {"status": "success", "article_id": article_id}


# ═══════════════════════════════════════════════
#  CONTENT CRUD API
# ═══════════════════════════════════════════════

@app.post("/api/content")
async def api_create_content(
    data: ContentCreateRequest,
    user: dict = Depends(require_user),
):
    """Create an original article."""
    article_id = create_original_article(
        title=data.title,
        content_md=data.content_md,
        category=data.category,
        author_id=user["id"],
        author_name=user.get("display_name") or user["username"],
        tags=data.tags,
        importance=data.importance,
    )
    if not article_id:
        raise HTTPException(status_code=500, detail="创建文章失败")

    article = get_article_by_id(article_id)
    return {"article": article, "status": "created"}


@app.put("/api/content/{article_id}")
async def api_update_content(
    article_id: str,
    data: ContentUpdateRequest,
    user: dict = Depends(require_user),
):
    """Update an existing original article."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # Only author or admin can edit
    if article.get("author_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权编辑此文章")

    kwargs = {}
    if data.title:
        kwargs["title"] = data.title
    if data.content_md:
        kwargs["content_md"] = data.content_md
    if data.category:
        kwargs["category"] = data.category

    if not kwargs:
        raise HTTPException(status_code=400, detail="未提供更新内容")

    # Regenerate HTML if content changed
    if data.content_md:
        from .processor import _md_to_html
        kwargs["content_html"] = _md_to_html(data.content_md)

    update_article_content(article_id, **kwargs)
    updated = get_article_by_id(article_id)
    return {"article": updated, "status": "updated"}


# ═══════════════════════════════════════════════
#  USER CONTENT MANAGEMENT API
# ═══════════════════════════════════════════════

@app.get("/api/user/articles")
async def api_user_articles(user: dict = Depends(require_user)):
    """Get current user's own articles."""
    articles = get_articles_by_author(user["id"])
    return {"articles": articles, "total": len(articles)}


@app.delete("/api/content/{article_id}")
async def api_delete_content(
    article_id: str,
    user: dict = Depends(require_user),
):
    """Delete an article (author or admin only)."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.get("author_id") != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权删除此文章")

    with get_connection() as conn:
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.execute("DELETE FROM comments WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM likes WHERE article_id = ?", (article_id,))
        conn.commit()
    return {"status": "deleted"}


# ═══════════════════════════════════════════════
#  PROFILE ROUTE
# ═══════════════════════════════════════════════

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Profile / my articles page."""
    return render_template("profile.html", {
        "title": "我的文章 — AIHOTNESS",
        "description": "管理你发布的文章",
        "llm_enabled": LLM_ENABLED,
    })


# ═══════════════════════════════════════════════
#  COMMENTS API
# ═══════════════════════════════════════════════

@app.post("/api/articles/{article_id}/comments")
async def api_create_comment(
    article_id: str,
    data: CommentCreateRequest,
    user: dict = Depends(require_user),
):
    """Create a comment on an article."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    if data.parent_id:
        from .database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM comments WHERE id = ? AND article_id = ?",
                (data.parent_id, article_id),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="父评论不存在")

    comment_id = create_comment(article_id, user["id"], data.content, data.parent_id)
    if not comment_id:
        raise HTTPException(status_code=500, detail="评论发布失败")

    return {"comment_id": comment_id, "status": "created"}


@app.get("/api/articles/{article_id}/comments")
async def api_get_comments(article_id: str):
    """Get comments for an article."""
    comments = get_comments_by_article(article_id)
    return {"comments": comments, "total": len(comments)}


@app.delete("/api/comments/{comment_id}")
async def api_delete_comment(
    comment_id: int,
    user: dict = Depends(require_user),
):
    """Delete a comment (owner or admin)."""
    from .database import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM comments WHERE id = ?", (comment_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="评论不存在")

    comment = dict(row)

    if comment["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权删除此评论")

    # Owner delete
    if comment["user_id"] == user["id"]:
        if not delete_comment(comment_id, user["id"]):
            raise HTTPException(status_code=500, detail="删除失败")
    else:
        # Admin force delete
        with get_connection() as conn:
            conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
            conn.execute(
                "UPDATE articles SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
                (comment["article_id"],),
            )
            conn.commit()

    return {"status": "deleted"}


# ═══════════════════════════════════════════════
#  LIKES API
# ═══════════════════════════════════════════════

@app.post("/api/articles/{article_id}/like")
async def api_toggle_like(
    article_id: str,
    user: dict = Depends(require_user),
):
    """Toggle like on an article."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    result = toggle_like(user["id"], article_id)
    return result


@app.get("/api/articles/{article_id}/like-status")
async def api_like_status(
    article_id: str,
    user: dict = Depends(require_user),
):
    """Check if current user has liked an article."""
    liked = get_like_status(user["id"], article_id)
    return {"liked": liked}


# ═══════════════════════════════════════════════
#  ADMIN API
# ═══════════════════════════════════════════════

@app.get("/api/admin/stats")
async def api_admin_stats(_: dict = Depends(require_admin)):
    """Get admin dashboard statistics."""
    return {"stats": get_admin_stats()}


@app.get("/api/admin/articles")
async def api_admin_articles(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_admin),
):
    """Get all articles for admin management."""
    articles, total = get_all_articles_admin(limit, offset)
    return {"articles": articles, "total": total, "limit": limit, "offset": offset}


@app.delete("/api/admin/articles/{article_id}")
async def api_admin_delete_article(
    article_id: str,
    _: dict = Depends(require_admin),
):
    """Delete an article (admin only)."""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    if delete_article_admin(article_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=500, detail="删除失败")


@app.get("/api/admin/users")
async def api_admin_users(_: dict = Depends(require_admin)):
    """Get all users."""
    users = get_all_users()
    return {"users": users, "total": len(users)}


class AdminUserUpdateRequest(BaseModel):
    role: str = Field(default="", pattern="^(user|admin)?$")
    is_active: int | None = Field(default=None, ge=0, le=1)


@app.put("/api/admin/users/{user_id}")
async def api_admin_update_user(
    user_id: int,
    data: AdminUserUpdateRequest,
    admin: dict = Depends(require_admin),
):
    """Update user role or status (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    kwargs = {}
    if data.role:
        kwargs["role"] = data.role
    if data.is_active is not None:
        kwargs["is_active"] = data.is_active

    if not kwargs:
        raise HTTPException(status_code=400, detail="未提供更新内容")

    if update_user(user_id, **kwargs):
        updated = get_user_by_id(user_id)
        return {"user": updated}
    raise HTTPException(status_code=500, detail="更新失败")


@app.get("/api/admin/comments")
async def api_admin_comments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_admin),
):
    """Get all comments for moderation."""
    comments, total = get_all_comments_admin(limit, offset)
    return {"comments": comments, "total": total, "limit": limit, "offset": offset}


@app.put("/api/admin/comments/{comment_id}/hide")
async def api_admin_hide_comment(
    comment_id: int,
    _: dict = Depends(require_admin),
):
    """Hide or unhide a comment."""
    if hide_comment(comment_id):
        return {"status": "hidden"}
    raise HTTPException(status_code=404, detail="评论不存在")


# ═══════════════════════════════════════════════
#  FRONTEND ROUTES
# ═══════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page."""
    return HTMLResponse(render_template("index.html", {
        "title": APP_TITLE,
        "description": APP_DESCRIPTION,
        "llm_enabled": LLM_ENABLED,
    }))


@app.get("/papers", response_class=HTMLResponse)
async def papers_page(request: Request):
    """Papers page."""
    return HTMLResponse(render_template("index.html", {
        "title": f"{APP_TITLE} — 论文",
        "description": "AI 学术论文速递",
        "llm_enabled": LLM_ENABLED,
        "section": "papers",
    }))


@app.get("/tutorials", response_class=HTMLResponse)
async def tutorials_page(request: Request):
    """Tutorials page."""
    return HTMLResponse(render_template("index.html", {
        "title": f"{APP_TITLE} — AI教程",
        "description": "AI 学习资源与教程",
        "llm_enabled": LLM_ENABLED,
        "section": "tutorials",
    }))


@app.get("/community", response_class=HTMLResponse)
async def community_page(request: Request):
    """Community articles page (user-written originals)."""
    return HTMLResponse(render_template("community.html", {
        "title": f"{APP_TITLE} — 社区文章",
        "description": "用户原创 AI 文章",
        "llm_enabled": LLM_ENABLED,
    }))


@app.get("/api/community/articles")
async def api_community_articles(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get community (user-written) articles."""
    articles, total = get_community_articles(limit=limit, offset=offset)
    return {
        "articles": articles,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return HTMLResponse(render_template("login.html", {
        "title": f"{APP_TITLE} — 登录",
    }))


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page."""
    return HTMLResponse(render_template("register.html", {
        "title": f"{APP_TITLE} — 注册",
    }))


@app.get("/article/{article_id}", response_class=HTMLResponse)
async def article_page(request: Request, article_id: str):
    """Article detail page."""
    article = get_article_by_id(article_id)
    if not article:
        return HTMLResponse(render_template("index.html", {
            "title": f"{APP_TITLE} — 文章未找到",
            "description": "文章不存在",
            "llm_enabled": LLM_ENABLED,
        }), status_code=404)

    # If the article doesn't have content_html but was rewritten, try to generate
    if not article.get("content_html") and article.get("content_md"):
        from .processor import _md_to_html
        html = _md_to_html(article["content_md"])
        update_article_content(article_id, content_html=html)
        article["content_html"] = html

    return HTMLResponse(render_template("article.html", {
        "title": APP_TITLE,
        "llm_enabled": LLM_ENABLED,
        "article": article,
    }))


@app.get("/editor", response_class=HTMLResponse)
async def editor_page(request: Request):
    """Markdown editor for new articles."""
    return HTMLResponse(render_template("editor.html", {
        "title": f"{APP_TITLE}",
        "content_md": "",
    }))


@app.get("/editor/{article_id}", response_class=HTMLResponse)
async def editor_edit_page(request: Request, article_id: str):
    """Markdown editor for editing existing articles."""
    article = get_article_by_id(article_id)
    if not article:
        return HTMLResponse(render_template("index.html", {
            "title": f"{APP_TITLE} — 文章未找到",
            "description": "文章不存在",
            "llm_enabled": LLM_ENABLED,
        }), status_code=404)

    return HTMLResponse(render_template("editor.html", {
        "title": f"{APP_TITLE} — 编辑文章",
        "content_md": article.get("content_md", ""),
    }))


# ═══════════════════════════════════════════════
#  ADMIN FRONTEND ROUTES
# ═══════════════════════════════════════════════

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin dashboard page."""
    return HTMLResponse(render_template("admin/dashboard.html", {
        "title": f"{APP_TITLE} — 管理后台",
        "llm_enabled": LLM_ENABLED,
        "section": "dashboard",
    }))


@app.get("/admin/articles", response_class=HTMLResponse)
async def admin_articles_page(request: Request):
    """Admin articles management page."""
    return HTMLResponse(render_template("admin/articles.html", {
        "title": f"{APP_TITLE} — 文章管理",
        "llm_enabled": LLM_ENABLED,
        "section": "articles",
    }))


@app.get("/admin/comments", response_class=HTMLResponse)
async def admin_comments_page(request: Request):
    """Admin comments moderation page."""
    return HTMLResponse(render_template("admin/comments.html", {
        "title": f"{APP_TITLE} — 评论审核",
        "llm_enabled": LLM_ENABLED,
        "section": "comments",
    }))
