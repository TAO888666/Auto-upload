# social-auto-upload

`social-auto-upload` 是一个面向多平台内容分发的自动化发布项目，包含：

- 统一 CLI：登录、账号校验、视频发布、图文发布、定时发布
- Flask 后端：提供发布、账号管理、任务进度、AI 文案生成等接口
- Vue 3 管理前端：首页、账号管理、素材管理、发布中心、任务进度、AI 发布、关于页

这份仓库是面向 GitHub 公开整理过的版本，已经去掉了本地运行数据、内部规划文档、捆绑模型和 FFmpeg 二进制文件。

## 主要能力

- 抖音：登录、校验、视频发布、图文发布、定时发布
- 快手：登录、校验、视频发布、图文发布、定时发布
- 小红书：登录、校验、视频发布、图文发布、定时发布
- Bilibili：登录、校验、视频发布、定时发布
- 视频号：后端接口与发布流程已接入
- 发布中心：Tab 管理、账号筛选、作品队列、内容配置、定时发布、浏览器模式
- 任务进度：按任务卡片查看发布状态、失败重试、进度流
- AI 发布：AI 配置、素材分析、文案生成、对话式任务整理

## 技术栈

- Python 3.10 - 3.12
- Flask
- patchright / Playwright
- Vue 3
- Vite
- Element Plus
- Pinia

## 目录结构

```text
.
├─ sau_cli.py                  # 统一 CLI 入口
├─ sau_backend.py              # Flask 后端入口
├─ sau_frontend/               # Vue 3 + Vite 前端
├─ uploader/                   # 各平台上传实现
├─ myUtils/                    # AI 发布、登录、发布桥接等逻辑
├─ utils/                      # 通用工具与浏览器辅助
├─ examples/                   # 示例脚本
├─ skills/                     # 面向 Agent 的技能说明
├─ tests/                      # 回归测试
├─ docs/                       # 使用说明
└─ videos/                     # 示例素材
```

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/TAO888666/Auto-upload.git
cd Auto-upload
```

### 2. 创建环境并安装依赖

推荐使用 `uv`：

```bash
uv venv
uv pip install -e .
```

如果你使用 `pip`：

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
```

### 3. 安装浏览器运行时

```bash
patchright install chromium
```

如果在国内网络环境，Windows PowerShell 可先指定镜像：

```powershell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"
patchright install chromium
```

### 4. 准备配置文件

```bash
cp conf.example.py conf.py
```

至少建议检查这些配置项：

- `LOCAL_CHROME_PATH`
- `LOCAL_CHROME_HEADLESS`
- `DEBUG_MODE`

### 5. 启动后端

```bash
python sau_backend.py
```

默认监听：

- 后端 API：`http://localhost:5409`

### 6. 启动前端

```bash
cd sau_frontend
npm install
npm run dev
```

默认访问：

- 前端开发环境：`http://localhost:5173`

## CLI 示例

### 抖音

```bash
sau douyin login --account creator_a
sau douyin check --account creator_a
sau douyin upload-video --account creator_a --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
sau douyin upload-note --account creator_a --images videos/demo1.png videos/demo2.png --title "图文标题" --note "图文内容"
```

### 快手

```bash
sau kuaishou login --account creator_a
sau kuaishou check --account creator_a
sau kuaishou upload-video --account creator_a --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
```

### 小红书

```bash
sau xiaohongshu login --account creator_a
sau xiaohongshu check --account creator_a
sau xiaohongshu upload-video --account creator_a --file videos/demo.mp4 --title "示例标题" --desc "示例简介"
```

### Bilibili

```bash
sau bilibili login --account creator_a
sau bilibili check --account creator_a
sau bilibili upload-video --account creator_a --file videos/demo.mp4 --title "示例标题" --desc "示例简介" --tid 249
```

### 定时发布

```bash
sau douyin upload-video --account creator_a --file videos/demo.mp4 --title "定时标题" --desc "定时简介" --schedule "2026-06-18 21:30"
```

## AI 发布说明

公开仓库版本没有再捆绑：

- `vendor/` 下的本地 Whisper 模型和依赖副本
- `tools/ffmpeg/` 下的 FFmpeg 二进制

这不影响代码结构，但如果你要使用 AI 素材分析、音频转写、自动文案生成，建议自行准备：

1. 系统可用的 `ffmpeg` 和 `ffprobe`，并加入 `PATH`
2. 正常安装 Python 依赖中的 `faster-whisper`
3. 在“关于”页或 `gui_config.json` 中配置 AI 提供商、API Base、API Key、默认模型

## 文档

- [安装说明](./docs/install.md)
- [CLI 说明](./docs/CLI.md)
- [更新说明](./docs/update.md)
- [Agent Bootstrap](./docs/agent-bootstrap.md)
- [历史 Web 说明](./docs/legacy-web.md)

## 仓库整理说明

这份 GitHub 版本默认不提交以下内容：

- Cookie、账号会话、本地数据库、运行日志
- 前端构建产物、Node 模块缓存
- 本地视频上传目录和临时文件
- 内部 `docs/superpowers/` 规划与设计文档
- 捆绑式 `vendor/` 模型依赖和 `tools/ffmpeg/` 二进制

如果你要在本地完整恢复原始运行环境，可以按自己的部署方式补回这些运行时依赖。
