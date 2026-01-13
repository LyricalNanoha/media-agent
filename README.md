# Media Agent

基于 AI Agent 的影视资源管理工具，支持 Alist/WebDAV 扫描、TMDB 匹配和 STRM 生成。

## ✨ 功能特性

- 🔗 **存储服务连接** - 支持 Alist、WebDAV 等存储服务
- 📂 **递归扫描** - 一键扫描所有影视文件
- 🎬 **TMDB 匹配** - 自动查询 TMDB 获取准确元数据
- 🎯 **智能分类** - LLM 驱动的智能文件分类
- 📝 **STRM 生成** - 生成 Infuse/Emby/Jellyfin 兼容的 STRM 文件
- 💬 **对话式交互** - 通过自然语言与 Agent 对话完成操作

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 拉取镜像（自动匹配 amd64/arm64 架构）
docker pull lyricalnanoha/media-agent:latest

# 运行容器
docker run -d \
  --name media-agent \
  -p 3000:3000 \
  -e LLM_API_KEY=your_llm_api_key \
  -e LLM_BASE_URL=https://api.deepseek.com \
  -e LLM_MODEL=deepseek-chat \
  -e TMDB_API_KEY=your_tmdb_api_key \
  lyricalnanoha/media-agent:latest
```

访问 http://localhost:3000 即可使用。

### 方式二：Docker Compose

```yaml
version: '3.8'
services:
  media-agent:
    image: lyricalnanoha/media-agent:latest
    ports:
      - "3000:3000"
    environment:
      - LLM_API_KEY=your_llm_api_key
      - LLM_BASE_URL=https://api.deepseek.com
      - LLM_MODEL=deepseek-chat
      - TMDB_API_KEY=your_tmdb_api_key
    restart: unless-stopped
```

```bash
docker-compose up -d
```

### 方式三：本地开发

```bash
# 克隆项目
git clone https://github.com/lyricalnanoha/media-agent.git
cd media-agent

# 配置
cp config/config.example.yaml config/config.yaml
# 编辑 config/config.yaml 填写 API Key

# 启动后端
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --port 8002

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

## ⚙️ 环境变量

| 变量名 | 必填 | 说明 | 示例 |
|--------|------|------|------|
| `LLM_API_KEY` | ✅ | LLM API 密钥 | `sk-xxx` |
| `LLM_BASE_URL` | ❌ | LLM API 地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | ❌ | 模型名称 | `deepseek-chat` |
| `TMDB_API_KEY` | ✅ | TMDB API 密钥 | 从 [TMDB](https://www.themoviedb.org/settings/api) 获取 |

### 支持的 LLM 服务

- OpenAI (`https://api.openai.com/v1`)
- DeepSeek (`https://api.deepseek.com`)
- 硅基流动 (`https://api.siliconflow.cn/v1`)
- Moonshot (`https://api.moonshot.cn/v1`)
- Ollama (`http://localhost:11434/v1`)
- 其他 OpenAI API 兼容服务

## 🛠️ 技术栈

- **后端**: FastAPI + LangGraph + CopilotKit
- **前端**: Next.js + React + TailwindCSS
- **AI**: OpenAI API 兼容的 LLM 服务
- **数据库**: SQLite

## 📦 镜像信息

| 属性 | 值 |
|------|-----|
| 镜像名称 | `lyricalnanoha/media-agent` |
| 支持架构 | `linux/amd64`, `linux/arm64` |
| 镜像大小 | ~750MB |

## 🔧 故障排查

```bash
# 查看日志
docker logs media-agent

# 实时日志
docker logs -f media-agent

# 进入容器
docker exec -it media-agent /bin/bash
```

## 📄 License

MIT
