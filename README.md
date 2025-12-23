# Context.md

## 📋 项目概述

**项目名称**: WebLLM / Pantheon API  
**版本**: v0.3.0  
**核心功能**: 通过浏览器自动化技术（DrissionPage）将网页版 LLM 封装为本地 RESTful API，并支持 **OpenAI 兼容协议**。

### 技术栈
- **Web 自动化**: DrissionPage (Chrome DevTools Protocol)
- **API 框架**: FastAPI + Uvicorn
- **数据验证**: Pydantic
- **语言版本**: Python 3.12+
- **兼容协议**: OpenAI API Standard

---

## 🏗️ 项目架构

```
WebLLM/
├── adapters/           # 适配器层 - 各 LLM 平台的具体实现
│   ├── base_bot.py     # 抽象基类
│   ├── kimi_bot.py     # Kimi 适配器
│   ├── lmarena_bot.py  # LMArena 适配器 (支持多模型)
│   └── __init__.py
├── core/               # 核心层 - 公共逻辑（预留扩展）
├── tests/              # 测试模块
│   ├── test_kimi.py    # Kimi 接口测试
│   ├── test_lmarena.py # LMArena 接口测试
│   └── test_openai.py  # OpenAI SDK 兼容性测试
├── config.py           # 配置管理
├── main.py             # API 服务入口
└── requirements.txt    # 依赖声明
```

---

## 📁 文件功能职责

### 1️⃣ **根目录文件**

#### `main.py` - API 服务主程序
**职责**:
- FastAPI 应用初始化和配置
- 浏览器连接管理（启动时连接 Chrome 调试端口）
- Bot 实例化和生命周期管理 (KimiBot, LMArenaBot)
- **路由分发**: 根据模型名称将请求路由到对应的 Bot
- **API 定义**: 提供原生接口和 OpenAI 兼容接口

**关键路由**:
- `GET /v1/models` - 获取可用模型列表 (OpenAI 格式)
- `POST /v1/chat/completions` - **OpenAI 兼容对话接口**
- `POST /v1/chat/kimi` - Kimi 原生接口
- `POST /v1/chat/lmarena` - LMArena 原生接口

**启动流程**:
1. 读取配置
2. 连接 Chrome 调试端口 (9222)
3. 初始化所有 Bot 实例
4. 启动 uvicorn 服务

---

#### `config.py` - 全局配置文件
**职责**: 集中管理所有配置项

---

#### `requirements.txt` - Python 依赖
**核心依赖**:
- `DrissionPage>=4.0.0` - 浏览器自动化库
- `fastapi>=0.110.0` - Web 框架
- `uvicorn>=0.27.0` - ASGI 服务器
- `pydantic>=2.7.0` - 数据验证
- `openai>=1.0.0` - 用于测试 SDK 兼容性

---

### 2️⃣ **adapters/ - 适配器模块**

#### `base_bot.py` - 抽象基类
**职责**: 定义所有 Bot 必须实现的接口规范

**核心接口**:
```python
activate() -> bool           # 激活/跳转到对应标签页
ask(query: str) -> str      # 发送问题并获取回答
new_chat() -> bool          # 开启新对话（清除上下文）
```

**设计模式**: 抽象基类（ABC），强制子类实现核心方法

---

#### `kimi_bot.py` - Kimi 平台适配器
实现 Kimi 网页版的交互逻辑，包含输入框定位和回复等待。

#### `lmarena_bot.py` - LMArena 适配器 (✨新增)
**职责**: 实现 lmarena.ai 的交互，支持动态切换模型。
**核心功能**:
- **模型选择 (`_select_model`)**: 
  - 使用多种策略 (XPath, CSS, 文本匹配) 精确定位 Combobox 按钮。
  - 支持 JS 点击和模拟操作，解决元素遮挡问题。
- **回复解析 (`_get_last_answer`)**: 
  - 同时提取 **思考过程 (Thought)** 和 **最终回答 (Answer)**。
  - 返回结构化字典 `{"thought": "...", "answer": "..."}`。
- **多模型支持**: 允许在运行时通过下拉菜单切换模型。


### 3️⃣ **core/ - 核心模块（预留）**

**当前状态**: 所有文件为空，仅作为占位符  
**未来规划**:
- `browser.py` - 浏览器连接池管理、多标签页协调
- `manager.py` - Bot 管理器、负载均衡、任务队列
- `utils.py` - 公共工具函数（日志、重试机制等）

---

## 🔄 核心工作流程

### 1. 服务启动流程
```
启动 main.py
  ↓
读取 config.py 配置
  ↓
连接 Chrome 调试端口（9222）
  ↓
初始化 KimiBot 实例
  ↓
启动 FastAPI 服务（8000 端口）
```

### 2. API 调用流程（以 OpenAI API 为例）
```
客户端 (OpenAI SDK)
  ↓
POST /v1/chat/completions
  ↓
main.py: parse_model_name() 解析模型前缀
  ↓
main.py: route_to_bot() 分发请求
  ├─ case "kimi": 调用 KimiBot.ask()
  └─ case "lmarena": 调用 LMArenaBot.ask(model_name="...")
       ↓
     LMArenaBot: 检查当前模型 -> 下拉切换模型 (如果需要) -> 提问 -> 获取(思考+回答)
       ↓
     封装为 OpenAI ChatCompletionChunk 格式
  ↓
返回 JSON 响应
```

---

## 🎯 扩展指南

### 添加新的 LLM 平台适配器

1. **创建文件**: `adapters/xxx_bot.py`
2. **继承基类**: 
   ```python
   from .base_bot import BaseBot
   
   class XxxBot(BaseBot):
       def __init__(self, page):
           super().__init__(page)
           self.name = "Xxx"
           self.url = "https://..."
   ```
3. **实现方法**: `activate()`, `ask()`, `new_chat()`
4. **注册路由**: 在 `main.py` 添加对应 API 路由
5. **更新导出**: 在 `adapters/__init__.py` 添加导出


## ⚠️ 注意事项

### 前置要求
1. **手动登录**: 启动服务前需在浏览器中登录对应平台
2. **配置修改**: 首次使用修改 `config.py` 中的路径配置
3. **默认配置**：部分网页存在默认配置，例如DeepSeek、Yuanbao打开新页面时会自动集成之前的**深度思考**与**网页搜索**选项

### 常见问题
- **回复超时**: 调整 `MAX_WAIT_TIME` 或检查网络

---

- **最后更新**: 2025-12-23

- **维护者**: kdy 