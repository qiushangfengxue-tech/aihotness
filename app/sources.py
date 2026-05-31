"""Data source definitions for AIHOTNESS.

Each source has:
  - name: display name
  - type: blog / news / paper / tutorial
  - feed_url: RSS feed URL
  - website_url: main website
  - lang: zh / en
  - category_hint: suggested category for LLM-less mode
"""

SOURCES = [
    # ===== 国际 AI 公司官方博客 =====
    {
        "name": "OpenAI",
        "type": "blog",
        "feed_url": "https://openai.com/feed.xml",
        "website_url": "https://openai.com/blog",
        "lang": "en",
        "category_hint": "产品发布",
        "enabled": True,
    },
    {
        "name": "Anthropic",
        "type": "blog",
        "feed_url": "https://www.anthropic.com/feed.xml",
        "website_url": "https://www.anthropic.com/blog",
        "lang": "en",
        "category_hint": "产品发布",
        "enabled": True,
    },
    {
        "name": "Google DeepMind",
        "type": "blog",
        "feed_url": "https://blog.google/technology/ai/rss/",
        "website_url": "https://deepmind.google/blog/",
        "lang": "en",
        "category_hint": "技术突破",
        "enabled": True,
    },
    {
        "name": "Meta AI",
        "type": "blog",
        "feed_url": "https://ai.meta.com/blog/feed/",
        "website_url": "https://ai.meta.com/blog/",
        "lang": "en",
        "category_hint": "技术突破",
        "enabled": True,
    },

    # ===== 国内 AI 公司（无官方 RSS，用第三方覆盖） =====
    # 字节跳动、百度、月之暗面暂无公开 RSS
    # 通过下面中文科技媒体覆盖

    # ===== AI 学术论文 =====
    {
        "name": "arXiv AI",
        "type": "paper",
        "feed_url": "https://rss.arxiv.org/rss/cs.AI",
        "website_url": "https://arxiv.org/list/cs.AI/recent",
        "lang": "en",
        "category_hint": "学术论文",
        "enabled": True,
    },
    {
        "name": "arXiv ML",
        "type": "paper",
        "feed_url": "https://rss.arxiv.org/rss/cs.LG",
        "website_url": "https://arxiv.org/list/cs.LG/recent",
        "lang": "en",
        "category_hint": "学术论文",
        "enabled": True,
    },
    {
        "name": "arXiv CL",
        "type": "paper",
        "feed_url": "https://rss.arxiv.org/rss/cs.CL",
        "website_url": "https://arxiv.org/list/cs.CL/recent",
        "lang": "en",
        "category_hint": "学术论文",
        "enabled": True,
    },
    {
        "name": "Hugging Face Papers",
        "type": "paper",
        "feed_url": "https://huggingface.co/papers/feed",
        "website_url": "https://huggingface.co/papers",
        "lang": "en",
        "category_hint": "学术论文",
        "enabled": True,
    },

    # ===== AI 教程 / 学习资源 =====
    {
        "name": "DeepLearning.AI",
        "type": "tutorial",
        "feed_url": "https://www.deeplearning.ai/blog/feed/",
        "website_url": "https://www.deeplearning.ai/blog/",
        "lang": "en",
        "category_hint": "AI教程",
        "enabled": True,
    },
    {
        "name": "Hugging Face Blog",
        "type": "tutorial",
        "feed_url": "https://huggingface.co/blog/feed.xml",
        "website_url": "https://huggingface.co/blog",
        "lang": "en",
        "category_hint": "AI教程",
        "enabled": True,
    },

    # ===== 中文 AI 科技媒体 =====
    # 覆盖字节/百度/月之暗面等公司动态
    {
        "name": "机器之心",
        "type": "news",
        "feed_url": "https://www.jiqizhixin.com/rss",
        "website_url": "https://www.jiqizhixin.com",
        "lang": "zh",
        "category_hint": "行业趋势",
        "enabled": True,
    },
    {
        "name": "量子位",
        "type": "news",
        "feed_url": "https://www.qbitai.com/feed",
        "website_url": "https://www.qbitai.com",
        "lang": "zh",
        "category_hint": "行业趋势",
        "enabled": True,
    },
    {
        "name": "36氪 AI",
        "type": "news",
        "feed_url": "https://36kr.com/feed/tech/ai",
        "website_url": "https://36kr.com/info/tech/ai",
        "lang": "zh",
        "category_hint": "行业趋势",
        "enabled": True,
    },

    # ===== 行业资讯 =====
    {
        "name": "TechCrunch AI",
        "type": "news",
        "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "website_url": "https://techcrunch.com/category/artificial-intelligence/",
        "lang": "en",
        "category_hint": "行业趋势",
        "enabled": True,
    },
    {
        "name": "The Verge AI",
        "type": "news",
        "feed_url": "https://www.theverge.com/ai-artificial-intelligence/rss",
        "website_url": "https://www.theverge.com/ai-artificial-intelligence",
        "lang": "en",
        "category_hint": "行业趋势",
        "enabled": True,
    },
    {
        "name": "Hacker News",
        "type": "news",
        "feed_url": "https://hnrss.org/frontpage",
        "website_url": "https://news.ycombinator.com",
        "lang": "en",
        "category_hint": "行业趋势",
        "enabled": True,
    },
    {
        "name": "MIT AI News",
        "type": "news",
        "feed_url": "https://news.mit.edu/topic/artificial-intelligence/rss",
        "website_url": "https://news.mit.edu/topic/artificial-intelligence",
        "lang": "en",
        "category_hint": "技术突破",
        "enabled": True,
    },
]


def get_enabled_sources():
    """Return only enabled sources."""
    return [s for s in SOURCES if s.get("enabled", True)]


def get_sources_by_type(source_type: str):
    """Get sources filtered by type."""
    return [s for s in get_enabled_sources() if s["type"] == source_type]


def get_source_names() -> list[str]:
    """Get all enabled source names."""
    return [s["name"] for s in get_enabled_sources()]
