# AIHOTNESS 🔥

> AI 热点资讯聚合平台 — 追踪全球 AI 前沿动态

AIHOTNESS 是一个 AI 热点资讯聚合系统，自动从全球主流 AI 公司博客、科技媒体、学术论文平台采集最新动态，通过 DeepSeek LLM 进行分类、分级和摘要生成，以科技感 Web 界面呈现。

## 架构

```
RSS Feeds → 采集器 → LLM 处理 → 数据库 → Web 展示
             │          │
        18+ 信息源   DeepSeek 分类/分级/摘要
```

### 信息源覆盖

| 类型 | 来源 |
|------|------|
| **AI 公司博客** | OpenAI, Anthropic, Google DeepMind, Meta AI, Hugging Face |
| **学术论文** | arXiv (cs.AI, cs.LG, cs.CL), Hugging Face Papers |
| **中文媒体** | 机器之心, 量子位, 36氪 AI |
| **国际资讯** | TechCrunch AI, The Verge AI, Hacker News, MIT AI News |
| **AI 教程** | DeepLearning.AI, Hugging Face Blog |

## 快速开始

### 本地运行

```bash
# 1. 克隆项目
git clone <repo-url> && cd aihotness

# 2. 安装依赖
pip install -r requirements.txt

# 3. (可选) 配置 DeepSeek API Key
# 复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY
# 不配置则运行 Cold Mode（无 LLM 处理）
cp .env.example .env

# 4. 启动
uvicorn app.main:app --reload
```

访问 **http://localhost:8000**

### Docker 部署

```bash
# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 启动
docker compose up -d

# 查看日志
docker compose logs -f
```

## LLM 配置

AIHOTNESS 使用 DeepSeek API 进行文章处理：

1. 注册 [DeepSeek Platform](https://platform.deepseek.com)
2. 获取 API Key（新用户赠送 500 万 tokens）
3. 填入 `.env` 的 `DEEPSEEK_API_KEY`

**Cold Mode**: 未配置 API Key 时，系统仅采集和展示原始 RSS 内容，不做智能分级和摘要。

## 部署到云服务器

```bash
# 1. 服务器上安装 Docker
# 2. 上传项目文件
# 3. 配置 .env
# 4. docker compose up -d
# 5. Nginx 反向代理 + 域名绑定
# 6. 备案域名，正式上线
```

## 技术栈

- **后端**: Python / FastAPI
- **前端**: HTML / CSS / JavaScript（无框架，纯静态）
- **LLM**: DeepSeek API
- **数据库**: SQLite（本地）→ 可升级 PostgreSQL
- **采集**: feedparser（RSS）
- **部署**: Docker / docker-compose

## License

MIT
