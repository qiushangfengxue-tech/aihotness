"""RSS/Feed collector for AIHOTNESS."""

import feedparser
import time
import re
from datetime import datetime, timezone
from typing import Optional
from html import unescape

from .sources import get_enabled_sources
from .database import save_article, log_collection, get_connection
from .config import MAX_ARTICLES_PER_SOURCE


def clean_html(html_text: str) -> str:
    """Strip HTML tags and clean whitespace."""
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]  # Limit content length


def parse_date(date_struct) -> Optional[str]:
    """Parse feedparser date to ISO string."""
    if not date_struct:
        return None
    try:
        t = time.mktime(date_struct)
        return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
    except (OverflowError, ValueError, TypeError):
        return None


def extract_image(entry) -> str:
    """Try to extract an image URL from the entry."""
    # Check media content
    if hasattr(entry, "media_content"):
        for media in entry.media_content:
            if media.get("url") and "image" in media.get("type", ""):
                return media["url"]

    # Check media thumbnail
    if hasattr(entry, "media_thumbnail"):
        for thumb in entry.media_thumbnail:
            if thumb.get("url"):
                return thumb["url"]

    # Check links for enclosures
    if hasattr(entry, "links"):
        for link in entry.links:
            if link.get("type", "").startswith("image"):
                return link["href"]

    # Try to extract first image from content
    content = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)

    return ""


def collect_source(source: dict) -> int:
    """Collect articles from a single RSS source. Returns count of new articles."""
    feed_url = source["feed_url"]
    source_name = source["name"]
    new_count = 0

    try:
        # Set a user-agent to avoid being blocked
        feed = feedparser.parse(
            feed_url,
            agent="AIHOTNESS/1.0 (News Aggregator; +https://aihotness.app)",
        )

        if feed.bozo and not feed.entries:
            error_msg = str(feed.bozo_exception)[:200] if feed.bozo_exception else "Unknown parse error"
            log_collection(source_name, "error", error=error_msg)
            print(f"  [ERR] {source_name}: {error_msg}")
            return 0

        entries = feed.entries[:MAX_ARTICLES_PER_SOURCE]
        with get_connection() as conn:
            for entry in entries:
                title = clean_html(entry.get("title", ""))
                if not title:
                    continue

                # Get URL - prefer the 'link' field
                url = entry.get("link", "")

                # Get content/summary
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                summary = clean_html(entry.get("summary", "") or content)
                content_text = clean_html(content) if content else summary

                # Get author
                author = ""
                if hasattr(entry, "author") and entry.author:
                    author = entry.author
                elif hasattr(entry, "authors") and entry.authors:
                    author = ", ".join(
                        a.get("name", "") for a in entry.authors if a.get("name")
                    )

                article = {
                    "title": title,
                    "url": url,
                    "source_name": source_name,
                    "source_type": source["type"],
                    "summary": summary[:500] if summary else "",
                    "content": content_text,
                    "author": author,
                    "published_at": parse_date(entry.get("published_parsed")),
                    "category": source.get("category_hint", "未分类"),
                    "importance": "C",  # Default, will be upgraded by LLM
                    "tags": [source_name],
                    "image_url": extract_image(entry),
                }

                if save_article(conn, article):
                    new_count += 1

        log_collection(source_name, "success", count=new_count)
        print(f"  [OK] {source_name}: {new_count} new articles")

    except Exception as e:
        error_msg = str(e)[:200]
        log_collection(source_name, "error", error=error_msg)
        print(f"  [ERR] {source_name}: {error_msg[:200]}")

    return new_count


def run_collection() -> dict:
    """Run collection for all enabled sources."""
    sources = get_enabled_sources()
    results = {
        "total_sources": len(sources),
        "success_count": 0,
        "error_count": 0,
        "total_new_articles": 0,
        "details": [],
    }

    print(f"\n{'='*50}")
    print(f"AIHOTNESS Collection Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Sources: {len(sources)} enabled")
    print(f"{'='*50}")

    for source in sources:
        count = collect_source(source)
        results["total_new_articles"] += count
        if count >= 0:
            results["success_count"] += 1
        else:
            results["error_count"] += 1
        results["details"].append({"name": source["name"], "new_articles": count})

    print(f"{'='*50}")
    print(f"Summary: {results['total_new_articles']} new articles from {results['success_count']}/{results['total_sources']} sources")
    print(f"{'='*50}\n")

    return results
