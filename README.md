# Web-LLM API

![alt text](https://img.shields.io/badge/Python-3.12+-blue.svg)
![alt text](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 项目概述

WebLLM API 通过浏览器自动化技术（DrissionPage），将各大网页版 LLM 服务封装为统一的 API。无需官方 API Key，直接复用浏览器登录态，支持 OpenAI SDK 无缝调用。

### 核心特性

| 特性 | 说明 |
|---|---|
| 🔌 OpenAI 兼容 | 100% 兼容 OpenAI API 格式，可直接使用官方 SDK |
| 🤖 多平台支持 | Kimi、LMArena、腾讯元宝、DeepSeek（持续扩展中） |
| 🚀 并行处理 | 多标签页池化管理，支持并发请求 |
| 🔄 超强模型 | LMArena 支持各种顶级模型的调用 |
| 📦 零成本 | 复用网页登录态，无需付费 API |


### 技术栈
| 组件 | 技术 | 说明 |
|---|---|---|
| Web 自动化 | DrissionPage | 基于 Chrome DevTools Protocol |
| API 框架 | FastAPI + Uvicorn | 高性能异步 Web 框架 |
| 数据验证 | Pydantic v2 | 类型安全的数据模型 |
| 并发管理 | ThreadPoolExecutor | 多标签页并行处理 |
| 运行环境 | Python 3.12+ | 最低版本要求 |

### 支持的模型标识
| 模型标识 | 平台 | 说明 |
| --- | --- | --- |
| kimi | Kimi | Kimi-K2 |
| deepseek | DeepSeek | DeepSeek，支持深度思考 |
| yuanbao  | 腾讯元宝 | 默认也是DeepSeek |
| lmarena:<name> | LMArena | 自行指定模型，如 gemini-3-pro、gpt-5.2等 |

---

## 快速开始

```
# 克隆项目
git clone <url>

# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
python main.py

# 第一次使用需要在网页端登录
```

---

## 🎯 扩展指南

### 添加新的 LLM 平台适配器

1. **创建文件**: `adapters/xxx_bot.py`
2. **继承基类**: BaseBot
3. **实现方法**: `activate()`, `ask()`, `new_chat()`
4. **注册路由**: 在 `main.py` 添加对应 API 路由
5. **更新导出**: 在 `adapters/__init__.py` 添加导出


## ⚠️ 注意事项

### 前置要求
1. **手动登录**: 启动服务前需在浏览器中登录对应平台
2. **配置修改**: 首次使用修改 `config.py` 中的路径配置
3. **默认配置**：部分网页存在默认配置（如深度思考、网页搜索选项），新标签页会继承

### 并发限制
- 每种模型默认最多 3 个并发标签页（可在 TabPoolManager 中调整）。
- 避免较多并发量，防止风控。
- 超过限制的请求会等待可用标签页。


## 🏗️ 项目架构

```
pantheon-api/
├── adapters/                 # 适配器层 - 各平台实现
│   ├── __init__.py          # 模块导出
│   ├── base_bot.py          # 抽象基类
│   ├── kimi_bot.py          # Kimi 适配器
│   ├── lmarena_bot.py       # LMArena 适配器
│   ├── yuanbao_bot.py       # 腾讯元宝适配器
│   └── deepseek_bot.py      # DeepSeek 适配器
├── core/                     # 核心层
│   ├── __init__.py          # 模块导出
│   └── tab_manager.py       # 标签页池管理器
├── tests/                    # 测试模块
├── config.py                 # 全局配置
├── main.py                   # API 服务入口
├── requirements.txt          # 依赖声明
└── README.md
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
定义所有 Bot 的标准接口，支持两种运行模式：
1. 单例模式: 传入 page，自动管理标签页
2. 多例模式: 传入 tab，使用外部提供的标签页（并发场景）

**核心接口**:
```python
activate() -> bool          # 激活/切换到对应标签页
ask(query: str) -> str      # 发送问题并获取回答
new_chat() -> bool          # 开启新对话
```
---

#### 各平台适配器
实现 各平台 网页版的交互逻辑，包含输入框定位和回复等待。

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


### 3️⃣ core/tab_manager.py - 标签页池管理器
管理多标签页并发，实现请求隔离。
- 为每个请求分配独立标签页
- 标签页复用，避免频繁创建
- 线程安全的资源管理
- 自动清理闲置标签页

---

## 🔄 核心工作流程

### 1. 服务启动流程
```
python main.py
       ↓
读取 config.py 配置
       ↓
连接 Chrome (端口 9222)
       ↓
初始化 TabPoolManager (每种 Bot 最多 3 个并发)
       ↓
启动 FastAPI (端口 8000)
```

### 2. API 调用流程（以 OpenAI API 为例）
```
请求1 ──┐
请求2 ──┼──→ TabPoolManager
请求3 ──┘         │
                  ↓
         ┌────────────────┐
         │  分配独立标签页 │
         └────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ↓             ↓             ↓
  Tab1          Tab2          Tab3
 (Bot1)        (Bot2)        (Bot3)
    │             │             │
    ↓             ↓             ↓
  响应1         响应2         响应3
    │             │             │
    └─────────────┼─────────────┘
                  ↓
         ┌─────────────────┐
         │  释放标签页回池  │
         └─────────────────┘
```

---

- **最后更新**: 2025-12-23
- **维护者**: kdy 