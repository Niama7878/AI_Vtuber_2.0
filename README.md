# AI Vtuber 2.0

**注意:** 本项目 (v2.0) 是基于第一代版本 [AI_Chat_Vtuber](https://github.com/Niama7878/AI_Chat_Vtuber) 进行代码重构和功能增强后的版本。

这是一个集成了多种功能的 AI VTuber 聊天助手项目。它能够通过麦克风接收语音输入，连接 OpenAI 进行实时语音识别和对话生成，播放 AI 生成的语音回复，并能控制 VTube Studio 中的 Live2D 模型进行动作和表情展示。此外，它还可以选择性地爬取 Bilibili 和 YouTube 直播间的弹幕信息作为输入来源，并通过一个独立的 Pygame 窗口实时显示 AI 的回复文本。项目还包含一个 Flask Web 界面用于监控系统状态和查看聊天记录。

## 主要功能

* **实时语音交互**: 使用 OpenAI Whisper 进行语音转文字（STT），并通过 OpenAI GPT-4o Mini 实时生成对话回复。
* **语音合成输出**: 播放由 OpenAI 生成的语音回复。
* **VTube Studio 集成**:
    * 连接到本地运行的 VTube Studio。
    * 实现 Live2D 模型的自然随机头部摆动。
    * 根据 OpenAI 分析的对话情绪触发 VTube Studio 中的预设热键动画。
* **直播弹幕爬取 (可选)**:
    * 爬取指定 Bilibili 直播间的弹幕和礼物信息。
    * 爬取指定 YouTube 直播间的聊天消息。
* **聊天记忆与管理**:
    * 使用 SQLite 数据库 (`chat_memory.db`) 保存聊天记录（包括语音输入和直播弹幕）。
    * 在生成回复时，会检索相关的历史聊天记录作为上下文。
    * 对相似度较高的问题进行分组处理，并能利用相似的已回答问题作为参考。
* **实时文本显示**: 通过一个独立的 Pygame/OpenGL 窗口，以打字机效果实时显示 AI 回复的文本。
* **Web 监控界面**:
    * 提供一个基于 Flask 的 Web 界面，在 `http://127.0.0.1:5000` 运行。
    * 通过 Server-Sent Events (SSE) 实时更新系统状态（如是否正在处理、是否在播放音频、麦克风状态等）。
    * 展示存储在数据库中的聊天记录。
* **状态管理**: 使用 `common.py` 模块在不同组件间共享和管理状态。
* **配置**: 通过 `.env` 文件加载敏感信息（如 API 密钥）。

## 环境要求

* 此项目开发使用 Python 3.12.8
* 安装并运行 VTube Studio，并启用 API。
* 麦克风设备（用于语音输入）。
* (可选) 如果使用 YouTube 爬虫，需要有效的 YouTube Data API v3 密钥。
* (可选) 如果使用 Bilibili 爬虫，需要有效的 Bilibili 账户 Cookie (`SESSDATA`)。
* (可选) 一个 TTF 字体文件用于文本显示（代码中默认为 `ShanHaiNiuNaiBoBoW-2.ttf`）。
* 操作系统：大部分功能跨平台，但 `word.py` 中的窗口拖动功能 (`ctypes`) 是 Windows 特有的。

## 安装

1.  **安装 Python 依赖**
    ```bash
    pip install python-dotenv PyAudio pydub websocket-client requests rapidfuzz Flask pygame pyopengl numpy freetype-py noise
    ```

## 配置
1.  **添加配置信息**: 在 `.env` 文件中添加以下必要的配置 (根据需要添加可选配置):
    ```dotenv
    # 必要
    OPENAI_API_KEY="sk-YourOpenAISecretKey"
    
    # 如果使用 YouTube 爬取
    YOUTUBE_API_KEY="YourYouTubeDataAPIKey"

    # 如果使用 Bilibili 爬取
    SESSDATA="YourBilibiliSessDataCookie"
    ```
2.  **配置直播间 ID (如果使用爬虫)**:
    * 在 `crawler_bili.py` 文件中，修改 `room_id` 变量为你想要爬取的 Bilibili 直播间 ID。
    * 在 `crawler_yt.py` 文件中，修改 `live_chat_id` 变量为你想要爬取的 YouTube 直播视频 ID。
3.  **配置字体**: 确保 `word.py` 中指定的字体文件 (`ShanHaiNiuNaiBoBoW-2.ttf`) 存在于项目目录中，或者修改 `font_path` 变量指向你选择的字体文件。
4.  **VTube Studio 授权**: 首次运行 `vts.py` (或主程序 `main.py`) 时，VTube Studio 会弹窗请求 API 访问授权。请允许访问，程序会自动创建并保存 `token.json` 文件用于后续连接。

## 运行项目

1.  **确保 VTube Studio 正在运行** 并已启用 API。
2.  **启动主程序**:
    ```bash
    python main.py
    ```
    这将启动核心逻辑、Flask Web 服务器以及 `word.py` 文本显示窗口。
3.  **(可选) 访问 Web 界面**: 在浏览器中打开 `http://127.0.0.1:5000` 查看状态和聊天记录。
4.  **交互**:
    * 通过麦克风说话，AI 会进行响应。
    * 如果配置并启用了直播爬虫，Bilibili/YouTube 的弹幕也会被接收并可能触发 AI 回复。
    * AI 的文字回复会实时显示在独立的 Pygame 窗口中。
    * 观察 VTube Studio 中的模型，它应该会有随机的头部运动，并在特定情绪触发时播放动画。

## 模块概览

* `main.py`: 项目入口，启动各组件，管理主循环。
* `chat.py`: 处理与 OpenAI API 的 WebSocket 连接，负责 STT、LLM 对话、TTS 数据接收，并协调 VTube Studio 的情绪动画触发。
* `memory.py`: 管理 `chat_memory.db` 数据库，存储和检索聊天记录，处理相似问题。
* `play.py`: 实现音频播放队列，用于播放 OpenAI 返回的音频流。
* `vts.py`: 连接并控制 VTube Studio，处理模型运动和热键触发。
* `crawler_bili.py`: (可选) 爬取 Bilibili 直播间的弹幕和礼物信息。
* `crawler_yt.py`: (可选) 爬取 YouTube 直播间的聊天消息。
* `app.py`: Flask Web 应用，提供状态监控和聊天记录查看的 Web 界面。
* `word.py`: 使用 Pygame 和 OpenGL 创建一个独立的窗口，实时显示带打字效果的 AI 回复文本。
* `common.py`: 存储共享状态变量和辅助函数，连接各个模块。
* `roleplay.txt`: 包含 AI 的角色设定或系统提示词。
* `backup.txt`: 临时文件，`common.py` 写入 AI 文本流，`word.py` 读取并显示。
* `token.json`: (自动生成) 保存 VTube Studio 的 API 认证令牌。

## 使用教程

[YouTube](https://youtu.be/_9R8eSuDoQI) [Bilibili](https://www.bilibili.com/video/BV1ubLMz8EK3)