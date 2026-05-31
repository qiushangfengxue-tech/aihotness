"""DeepSeek LLM processor for classification, grading, summarization, and rewriting."""

import json
import time
from typing import Optional
from datetime import datetime, timezone

import markdown as _md
import bleach as _bleach

from .config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, LLM_ENABLED
from .database import get_connection


def _call_deepseek(messages: list, max_tokens: int = 1024) -> Optional[str]:
    """Call DeepSeek API with retry logic."""
    if not LLM_ENABLED:
        return None

    try:
        import httpx
        import certifi

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Low temperature for consistent output
        }

        # Use explicit certifi bundle to work around env var issues on Windows
        with httpx.Client(timeout=60.0, verify=certifi.where()) as client:
            resp = client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"  [DeepSeek] API error: {e}")
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response (handles markdown-wrapped JSON)."""
    if not text:
        return None
    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def process_article(article: dict) -> dict:
    """Process a single article: classify, grade importance, generate summary.

    Returns the article with enriched fields.
    """
    if not LLM_ENABLED:
        return article  # Pass through in cold mode

    title = article.get("title", "")[:200]
    content = article.get("content", "")[:1500] or article.get("summary", "")[:1500]

    if not title and not content:
        return article

    prompt_template = (
        "你是一个 AI 新闻分析师。分析以下 AI 相关文章，输出 JSON：\n\n"
        '{\n'
        '  "summary_zh": "中文一句话摘要（20字以内）",\n'
        '  "summary_en": "English one-line summary (15 words max)",\n'
        '  "importance": "S/A/B/C",\n'
        '  "category": "技术突破/产品发布/政策监管/行业趋势/学术论文/AI教程/未分类",\n'
        '  "tags": ["标签1", "标签2"]\n'
        '}\n\n'
        "重要性分级标准：\n"
        "- S (必读): 行业地震级事件，如 GPT-5 发布、主要公司战略转向\n"
        "- A (重要): 值得细读的重要进展、技术报告、政策变化\n"
        "- B (参考): 值得了解的一般动态\n"
        "- C (浏览): 常规更新、噪音\n\n"
        f"文章标题：{title}\n"
        f"文章内容：{content[:1500]}"
    )
    prompt = prompt_template

    response = _call_deepseek([
        {"role": "system", "content": "你是一个精准的 AI 新闻分析师。只输出 JSON，不要额外说明。"},
        {"role": "user", "content": prompt},
    ], max_tokens=512)

    parsed = _parse_json_response(response)
    if parsed:
        article["summary"] = parsed.get("summary_zh", article.get("summary", ""))
        article["importance"] = parsed.get("importance", "C")
        article["category"] = parsed.get("category", "未分类")
        article["tags"] = parsed.get("tags", [article["source_name"]])
        article["_llm_updated"] = True

    return article


def batch_process(articles: list[dict], batch_size: int = 5) -> list[dict]:
    """Process a batch of articles through the LLM."""
    if not LLM_ENABLED:
        return articles

    processed = []
    total = len(articles)
    for i in range(0, total, batch_size):
        batch = articles[i : i + batch_size]
        print(f"  [DeepSeek] Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}...")

        for article in batch:
            result = process_article(article)
            processed.append(result)
            time.sleep(0.5)  # Rate limiting

    return processed


def process_unprocessed():
    """Find and process articles that haven't been LLM-processed yet.

    An article is "unprocessed" if it has default importance 'C' and
    no meaningful summary.
    """
    if not LLM_ENABLED:
        print("  [DeepSeek] LLM not enabled — skipping processing. Set DEEPSEEK_API_KEY to activate.")
        return 0

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE (summary IS NULL OR summary = '' OR importance = 'C')
               AND collected_at >= datetime('now', '-7 days')
               ORDER BY published_at DESC
               LIMIT 50"""
        ).fetchall()

    if not rows:
        print("  [DeepSeek] No unprocessed articles found.")
        return 0

    articles = [dict(r) for r in rows]
    print(f"  [DeepSeek] Processing {len(articles)} articles...")

    processed = batch_process(articles)

    updated = 0
    rewritten = 0
    with get_connection() as conn:
        for article in processed:
            if article.get("_llm_updated"):
                conn.execute(
                    """UPDATE articles SET summary=?, importance=?, category=?, tags=?
                       WHERE id=?""",
                    (
                        article.get("summary", ""),
                        article.get("importance", "C"),
                        article.get("category", "未分类"),
                        json.dumps(article.get("tags", []), ensure_ascii=False),
                        article["id"],
                    ),
                )
                updated += 1

                # Auto-rewrite S-level articles into on-site content
                if article.get("importance") == "S" and not article.get("is_rewritten"):
                    result = rewrite_article(article)
                    if result:
                        conn.execute(
                            """UPDATE articles SET content_md=?, content_html=?,
                               is_rewritten=1, article_type='rewrite'
                               WHERE id=?""",
                            (result["content_md"], result["content_html"], article["id"]),
                        )
                        rewritten += 1

        conn.commit()

    print(f"  [DeepSeek] Updated {updated} articles (auto-rewritten {rewritten} S-level).")
    return updated


def _md_to_html(md_text: str) -> str:
    """Convert Markdown to safe HTML."""
    if not md_text:
        return ""
    # Convert markdown to HTML with extensions
    html = _md.markdown(md_text, extensions=["fenced_code", "tables", "codehilite"])
    # Sanitize with bleach (allow basic formatting tags)
    allowed_tags = [
        "p", "br", "strong", "em", "u", "s", "del", "ins",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "dl", "dt", "dd",
        "blockquote", "pre", "code", "hr",
        "a", "img",
        "table", "thead", "tbody", "tr", "th", "td",
        "span", "div", "sup", "sub",
    ]
    allowed_attrs = {
        "a": ["href", "title", "rel", "target"],
        "img": ["src", "alt", "title"],
        "code": ["class"],
        "span": ["class"],
        "div": ["class"],
        "pre": ["class"],
    }
    return _bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True,
    )


def rewrite_article(article: dict) -> Optional[dict]:
    """Rewrite an RSS article into an original Chinese article using DeepSeek.

    Returns dict with 'content_md' and 'content_html' keys, or None on failure.
    """
    if not LLM_ENABLED:
        return None

    title = article.get("title", "")[:200]
    content = article.get("content", "")[:3000] or article.get("summary", "")[:3000]

    if not title and not content:
        return None

    prompt = (
        "你是一个专业 AI 科技媒体编辑。请根据以下资料，撰写一篇原创中文文章。\n\n"
        "要求：\n"
        "- 500-800 字\n"
        "- 使用 Markdown 格式\n"
        "- 包含小标题分段\n"
        "- 语言流畅、专业，适合中文科技读者\n"
        "- 开头要有吸引力，结尾要有总结或展望\n"
        "- 不要输出 '以下是原创文章' 之类的引导语\n\n"
        f"原文标题：{title}\n"
        f"原文内容：{content[:3000]}\n\n"
        "请直接输出 Markdown 格式的完整文章："
    )

    response = _call_deepseek([
        {"role": "system", "content": "你是一个专业的 AI 科技媒体编辑。用中文撰写原创文章。"},
        {"role": "user", "content": prompt},
    ], max_tokens=2048)

    if not response:
        return None

    content_md = response.strip()
    # Strip markdown code fence if present
    if content_md.startswith("```markdown"):
        content_md = content_md[len("```markdown"):].strip()
        if content_md.endswith("```"):
            content_md = content_md[:-3].strip()
    elif content_md.startswith("```"):
        content_md = content_md[3:].strip()
        if content_md.endswith("```"):
            content_md = content_md[:-3].strip()

    content_html = _md_to_html(content_md)

    return {
        "content_md": content_md,
        "content_html": content_html,
    }
