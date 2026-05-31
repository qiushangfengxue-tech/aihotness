"""Database setup and operations"""

import sqlite3
import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from .config import DB_PATH


def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'blog',
                summary TEXT DEFAULT '',
                content TEXT DEFAULT '',
                content_md TEXT DEFAULT '',
                content_html TEXT DEFAULT '',
                article_type TEXT DEFAULT 'rss' CHECK(article_type IN ('rss','rewrite','original')),
                author TEXT DEFAULT '',
                author_id INTEGER DEFAULT NULL,
                is_rewritten INTEGER DEFAULT 0,
                published_at TEXT,
                collected_at TEXT NOT NULL,
                importance TEXT DEFAULT 'C',
                category TEXT DEFAULT '未分类',
                tags TEXT DEFAULT '[]',
                image_url TEXT DEFAULT '',
                is_read INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                bio TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                is_hidden INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, article_id)
            );

            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                status TEXT NOT NULL,
                articles_count INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                collected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                color TEXT DEFAULT '#6366f1',
                sort_order INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_published
                ON articles(published_at DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_importance
                ON articles(importance);
            CREATE INDEX IF NOT EXISTS idx_articles_source
                ON articles(source_name);
            CREATE INDEX IF NOT EXISTS idx_articles_category
                ON articles(category);
            CREATE INDEX IF NOT EXISTS idx_articles_type
                ON articles(article_type);
            CREATE INDEX IF NOT EXISTS idx_comments_article
                ON comments(article_id);
            CREATE INDEX IF NOT EXISTS idx_comments_user
                ON comments(user_id);
            CREATE INDEX IF NOT EXISTS idx_likes_article
                ON likes(article_id);
            CREATE INDEX IF NOT EXISTS idx_likes_user
                ON likes(user_id);
        """)

        # Insert default categories if not exist
        default_cats = [
            ("技术突破", "技术突破", "#ef4444", 1),
            ("产品发布", "产品发布", "#f59e0b", 2),
            ("政策监管", "政策监管", "#8b5cf6", 3),
            ("行业趋势", "行业趋势", "#06b6d4", 4),
            ("学术论文", "学术论文", "#10b981", 5),
            ("AI教程", "AI教程", "#3b82f6", 6),
        ]
        for name, display, color, order in default_cats:
            conn.execute(
                """INSERT OR IGNORE INTO categories (name, display_name, color, sort_order)
                   VALUES (?, ?, ?, ?)""",
                (name, display, color, order),
            )
        conn.commit()


@contextmanager
def db_session():
    """Context manager for database sessions."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def article_id(url: str) -> str:
    """Generate a deterministic ID from URL."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def save_article(conn, article: dict) -> bool:
    """Save an article, returns True if new, False if duplicate."""
    try:
        aid = article_id(article["url"])
        published = article.get("published_at") or datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(article.get("tags", []), ensure_ascii=False)

        conn.execute(
            """INSERT OR IGNORE INTO articles
               (id, title, url, source_name, source_type, summary, content,
                author, published_at, collected_at, importance, category, tags, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                aid,
                article["title"],
                article["url"],
                article["source_name"],
                article.get("source_type", "blog"),
                article.get("summary", ""),
                article.get("content", ""),
                article.get("author", ""),
                published,
                datetime.now(timezone.utc).isoformat(),
                article.get("importance", "C"),
                article.get("category", "未分类"),
                tags_json,
                article.get("image_url", ""),
            ),
        )
        conn.commit()
        return conn.total_changes > 0
    except Exception as e:
        print(f"Error saving article '{article.get('title', '')[:30]}': {e}")
        return False


def get_articles(
    limit: int = 50,
    offset: int = 0,
    importance: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    days: Optional[int] = None,
    q: Optional[str] = None,
):
    """Query articles with filters."""
    with db_session() as conn:
        where_clauses = []
        params = []

        if importance:
            where_clauses.append("importance = ?")
            params.append(importance)
        if category:
            where_clauses.append("category = ?")
            params.append(category)
        if source:
            where_clauses.append("source_name = ?")
            params.append(source)
        if days:
            where_clauses.append(
                "published_at >= datetime('now', ? || ' days')"
            )
            params.append(f"-{days}")
        if q:
            where_clauses.append("(title LIKE ? OR summary LIKE ? OR content LIKE ?)")
            like_q = f"%{q}%"
            params.extend([like_q, like_q, like_q])

        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)

        rows = conn.execute(
            f"""SELECT * FROM articles {where}
                ORDER BY
                    CASE importance
                        WHEN 'S' THEN 0 WHEN 'A' THEN 1
                        WHEN 'B' THEN 2 WHEN 'C' THEN 3
                        ELSE 4
                    END,
                    published_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        total = conn.execute(
            f"SELECT COUNT(*) FROM articles {where}", params
        ).fetchone()[0]

        articles = []
        for row in rows:
            a = dict(row)
            a["tags"] = json.loads(a.get("tags", "[]"))
            articles.append(a)

        return articles, total


def get_community_articles(limit: int = 50, offset: int = 0):
    """Get user-written original articles only."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE article_type = 'original'
               ORDER BY published_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE article_type = 'original'"
        ).fetchone()[0]

        articles = []
        for row in rows:
            a = dict(row)
            a["tags"] = json.loads(a.get("tags", "[]"))
            articles.append(a)

        return articles, total


def get_sources_stats():
    """Get statistics by source."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT source_name, source_type, COUNT(*) as count,
                      MAX(published_at) as latest
               FROM articles
               GROUP BY source_name
               ORDER BY count DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_categories():
    """Get all categories."""
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY sort_order"
        ).fetchall()
        return [dict(r) for r in rows]


def log_collection(source_name: str, status: str, count: int = 0, error: str = ""):
    """Log a collection run."""
    with db_session() as conn:
        conn.execute(
            """INSERT INTO collection_log (source_name, status, articles_count, error_message)
               VALUES (?, ?, ?, ?)""",
            (source_name, status, count, error),
        )
        conn.commit()


# ── User CRUD ──

def create_user(username: str, email: str, password_hash: str) -> Optional[int]:
    """Create a new user. Returns user_id or None if username/email taken."""
    with db_session() as conn:
        try:
            # First registered user becomes admin
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if count == 0 else "user"

            cur = conn.execute(
                """INSERT INTO users (username, email, password_hash, display_name, role)
                   VALUES (?, ?, ?, ?, ?)""",
                (username, email, password_hash, username, role),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get a user by their ID."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    """Get a user by username."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    """Get a user by email."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        return dict(row) if row else None


def update_user(user_id: int, **kwargs) -> bool:
    """Update user fields. Returns True if successful."""
    allowed = {"display_name", "bio", "avatar_url", "role", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]

    with db_session() as conn:
        conn.execute(
            f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        conn.commit()
        return True


def get_user_count() -> int:
    """Get total number of registered users."""
    with db_session() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_article_by_id(article_id: str) -> Optional[dict]:
    """Get a single article by ID."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
        if not row:
            return None
        a = dict(row)
        a["tags"] = json.loads(a.get("tags", "[]"))
        return a


def create_original_article(
    title: str,
    content_md: str,
    category: str,
    author_id: int,
    author_name: str,
    tags: Optional[list] = None,
    importance: str = "C",
) -> Optional[str]:
    """Create a user-written original article. Returns article ID or None."""
    import uuid

    article_id_val = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(tags or [category], ensure_ascii=False)

    with db_session() as conn:
        try:
            conn.execute(
                """INSERT INTO articles
                   (id, title, url, source_name, source_type, article_type,
                    content_md, content_html,
                    author, author_id,
                    published_at, collected_at, importance, category, tags,
                    like_count, comment_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)""",
                (
                    article_id_val,
                    title,
                    f"/article/{article_id_val}",
                    author_name,
                    "original",
                    "original",
                    content_md,
                    "",  # content_html will be generated on first view
                    author_name,
                    author_id,
                    now,
                    now,
                    importance,
                    category,
                    tags_json,
                ),
            )
            conn.commit()
            return article_id_val
        except Exception as e:
            print(f"Error creating article: {e}")
            return None


def get_articles_by_author(author_id: int) -> list[dict]:
    """Get all articles by a specific author."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE author_id = ?
               ORDER BY published_at DESC""",
            (author_id,),
        ).fetchall()
        articles = [dict(r) for r in rows]
        for a in articles:
            a["tags"] = json.loads(a.get("tags", "[]"))
        return articles


def update_article_content(
    article_id: str,
    content_md: Optional[str] = None,
    content_html: Optional[str] = None,
    title: Optional[str] = None,
    category: Optional[str] = None,
    importance: Optional[str] = None,
) -> bool:
    """Update an article's content fields. Returns True if successful."""
    updates = {}
    if content_md is not None:
        updates["content_md"] = content_md
    if content_html is not None:
        updates["content_html"] = content_html
    if title is not None:
        updates["title"] = title
    if category is not None:
        updates["category"] = category
    if importance is not None:
        updates["importance"] = importance

    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [article_id]

    with db_session() as conn:
        try:
            conn.execute(
                f"UPDATE articles SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            return conn.total_changes > 0
        except Exception as e:
            print(f"Error updating article {article_id}: {e}")
            return False


# ── Comments CRUD ──

def create_comment(article_id: str, user_id: int, content: str, parent_id: Optional[int] = None) -> Optional[int]:
    """Create a comment. Returns comment ID or None."""
    with db_session() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO comments (article_id, user_id, parent_id, content)
                   VALUES (?, ?, ?, ?)""",
                (article_id, user_id, parent_id, content),
            )
            # Update comment count on article
            conn.execute(
                "UPDATE articles SET comment_count = comment_count + 1 WHERE id = ?",
                (article_id,),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            print(f"Error creating comment: {e}")
            return None


def get_comments_by_article(article_id: str) -> list[dict]:
    """Get all comments for an article, with user info."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT c.*, u.username, u.display_name, u.avatar_url
               FROM comments c
               JOIN users u ON c.user_id = u.id
               WHERE c.article_id = ? AND c.is_hidden = 0
               ORDER BY c.created_at ASC""",
            (article_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_comment(comment_id: int, user_id: int) -> bool:
    """Delete a comment. User must own the comment. Returns True if deleted."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT article_id FROM comments WHERE id = ? AND user_id = ?",
            (comment_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.execute(
            "UPDATE articles SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
            (row["article_id"],),
        )
        conn.commit()
        return True


def hide_comment(comment_id: int) -> bool:
    """Hide a comment (admin only)."""
    with db_session() as conn:
        conn.execute(
            "UPDATE comments SET is_hidden = 1 WHERE id = ?",
            (comment_id,),
        )
        conn.commit()
        return conn.total_changes > 0


# ── Likes ──

def toggle_like(user_id: int, article_id: str) -> dict:
    """Toggle a like. Returns {'liked': bool, 'count': int}."""
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM likes WHERE user_id = ? AND article_id = ?",
            (user_id, article_id),
        ).fetchone()

        if existing:
            # Unlike
            conn.execute("DELETE FROM likes WHERE id = ?", (existing["id"],))
            conn.execute(
                "UPDATE articles SET like_count = MAX(0, like_count - 1) WHERE id = ?",
                (article_id,),
            )
            conn.commit()
            liked = False
        else:
            # Like
            conn.execute(
                "INSERT INTO likes (user_id, article_id) VALUES (?, ?)",
                (user_id, article_id),
            )
            conn.execute(
                "UPDATE articles SET like_count = like_count + 1 WHERE id = ?",
                (article_id,),
            )
            conn.commit()
            liked = True

        # Get updated count
        count = conn.execute(
            "SELECT like_count FROM articles WHERE id = ?",
            (article_id,),
        ).fetchone()[0]

        return {"liked": liked, "count": count}


def get_like_status(user_id: int, article_id: str) -> bool:
    """Check if a user has liked an article."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT id FROM likes WHERE user_id = ? AND article_id = ?",
            (user_id, article_id),
        ).fetchone()
        return row is not None


# ── Admin ──

def get_all_users() -> list[dict]:
    """Get all users (admin only)."""
    with db_session() as conn:
        rows = conn.execute(
            """SELECT id, username, email, display_name, role, is_active,
                      created_at, updated_at
               FROM users ORDER BY id ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_admin_stats() -> dict:
    """Get admin dashboard statistics."""
    with db_session() as conn:
        total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        total_likes = conn.execute("SELECT COUNT(*) FROM likes").fetchone()[0]

        articles_today = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE date(collected_at) = date('now')"
        ).fetchone()[0]

        rewritten = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE is_rewritten = 1"
        ).fetchone()[0]

        original = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE article_type = 'original'"
        ).fetchone()[0]

        # Top sources
        sources = conn.execute(
            """SELECT source_name, COUNT(*) as count
               FROM articles GROUP BY source_name
               ORDER BY count DESC LIMIT 5"""
        ).fetchall()

        # Recent activity (last 7 days)
        recent_articles = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE collected_at >= datetime('now', '-7 days')"
        ).fetchone()[0]

        recent_comments = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]

        return {
            "total_articles": total_articles,
            "total_users": total_users,
            "total_comments": total_comments,
            "total_likes": total_likes,
            "articles_today": articles_today,
            "rewritten": rewritten,
            "original": original,
            "top_sources": [dict(r) for r in sources],
            "recent_articles_7d": recent_articles,
            "recent_comments_7d": recent_comments,
        }


def get_all_articles_admin(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """Get all articles for admin management."""
    with db_session() as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        rows = conn.execute(
            """SELECT id, title, source_name, article_type, importance, category,
                      is_rewritten, author_id, like_count, comment_count,
                      published_at, collected_at
               FROM articles
               ORDER BY collected_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows], total


def delete_article_admin(article_id: str) -> bool:
    """Delete an article and its associated comments/likes (admin only)."""
    with db_session() as conn:
        try:
            conn.execute("DELETE FROM comments WHERE article_id = ?", (article_id,))
            conn.execute("DELETE FROM likes WHERE article_id = ?", (article_id,))
            conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting article {article_id}: {e}")
            return False


def get_all_comments_admin(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    """Get all comments for admin moderation."""
    with db_session() as conn:
        total = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        rows = conn.execute(
            """SELECT c.*, u.username, u.display_name, a.title as article_title
               FROM comments c
               JOIN users u ON c.user_id = u.id
               JOIN articles a ON c.article_id = a.id
               ORDER BY c.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows], total
