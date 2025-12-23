# main.py
"""
Pantheon API v0.1
通过 DrissionPage 控制浏览器，将网页版 LLM 封装为 API
支持 OpenAI 兼容格式
"""

import uvicorn
import time
import uuid
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Literal
from DrissionPage import ChromiumPage, ChromiumOptions
import sys

from config import CHROME_PORT, CHROME_USER_DATA_DIR, DEFAULT_LMARENA_MODEL
from adapters import KimiBot, LMArenaBot

# ============== FastAPI 初始化 ==============
app = FastAPI(
    title="Pantheon API",
    description="将网页版 LLM 封装为本地 API（支持 OpenAI 兼容格式）",
    version="0.1.0"
)

# ============== 全局变量 ==============
browser = None
kimi_bot = None
lmarena_bot = None

# ============== OpenAI 兼容数据模型 ==============

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    top_p: Optional[float] = Field(default=1.0, ge=0, le=1)
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=0, ge=-2, le=2)
    user: Optional[str] = None

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "content_filter", "null"]

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage

class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str

class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[ModelInfo]

# ============== 原有数据模型 ==============

class ChatRequest(BaseModel):
    query: str
    new_chat: Optional[bool] = False  # 是否开启新对话

class LMArenaRequest(BaseModel):
    query: str
    model: Optional[str] = None  # 指定模型（可选）
    new_chat: Optional[bool] = False

class ChatResponse(BaseModel):
    model: str
    answer: str
    status: str
    
class LMArenaResponse(BaseModel):
    model: str
    thought: str  # 思考过程
    answer: str   # 实际回答
    status: str

# ============== 模型路由逻辑 ==============

def parse_model_name(model: str) -> tuple:
    """
    解析模型名称，返回 (bot_type, specific_model)
    
    支持的格式:
    - "kimi" -> ("kimi", None)
    - "lmarena" -> ("lmarena", None)
    - "lmarena:claude-opus-4" -> ("lmarena", "claude-opus-4")
    - "lmarena:gemini-3-pro" -> ("lmarena", "gemini-3-pro")
    """
    model = model.lower().strip()
    
    if model.startswith("lmarena:"):
        parts = model.split(":", 1)
        return ("lmarena", parts[1] if len(parts) > 1 else None)
    elif model.startswith("lmarena"):
        return ("lmarena", None)
    elif model.startswith("kimi"):
        return ("kimi", None)
    else:
        # 默认尝试作为 lmarena 的模型名
        return ("lmarena", model)

def route_to_bot(model: str, query: str, new_chat: bool = False) -> dict:
    """
    根据模型名称路由到对应的 bot
    返回: {"model": str, "thought": str, "answer": str}
    """
    global kimi_bot, lmarena_bot
    
    bot_type, specific_model = parse_model_name(model)
    print(f"[Router] 解析模型: {model} -> bot_type={bot_type}, specific_model={specific_model}")
    
    if bot_type == "kimi":
        if kimi_bot is None:
            raise HTTPException(status_code=503, detail="Kimi 机器人未初始化")
        
        if new_chat:
            kimi_bot.new_chat()
        
        kimi_bot.activate()
        answer = kimi_bot.ask(query)
        
        if answer.startswith("Error:"):
            raise HTTPException(status_code=500, detail=answer)
        
        return {
            "model": "kimi",
            "thought": "",
            "answer": answer
        }
    
    elif bot_type == "lmarena":
        if lmarena_bot is None:
            raise HTTPException(status_code=503, detail="LMArena 机器人未初始化")
        
        if new_chat:
            lmarena_bot.new_chat()
        
        lmarena_bot.activate()
        result = lmarena_bot.ask(query, model_name=specific_model)
        
        if result["answer"].startswith("Error:"):
            raise HTTPException(status_code=500, detail=result["answer"])
        
        return {
            "model": f"lmarena:{specific_model}" if specific_model else "lmarena",
            "thought": result.get("thought", ""),
            "answer": result["answer"]
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"不支持的模型: {model}")

# ============== 启动事件 ==============
@app.on_event("startup")
def startup_event():
    """服务启动时连接浏览器"""
    global browser, kimi_bot, lmarena_bot
    
    print("=" * 50)
    print("🚀 Pantheon API v0.1 启动中...")
    print("   支持 OpenAI 兼容格式")
    print("=" * 50)
    
    try:
        # 配置 Chrome 选项
        co = ChromiumOptions()
        
        # 设置远程调试端口
        co.set_local_port(CHROME_PORT)
                
        # 其他有用的配置
        co.set_argument('--no-sandbox')  # 禁用沙盒模式
        co.set_argument('--disable-gpu')  # 禁用 GPU 加速（可选）
        # co.headless(False)  # 显示浏览器窗口（默认）
        
        # 连接或启动浏览器
        print(f"🔌 尝试连接到端口 {CHROME_PORT}...")
        browser = ChromiumPage(addr_or_opts=co)
        
        print(f"✅ 成功连接到 Chrome (端口: {CHROME_PORT})")
        
        # 初始化 Kimi 机器人
        kimi_bot = KimiBot(browser)
        print("✅ Kimi 机器人初始化完成")
        
        # 初始化 LMArena 机器人
        lmarena_bot = LMArenaBot(browser, model_name=DEFAULT_LMARENA_MODEL)
        print("✅ LMArena 机器人初始化完成")
        
        print("\n" + "=" * 50)
        print("✅ 服务启动成功！")
        print("=" * 50)
        print("\n📌 OpenAI 兼容端点:")
        print("   POST /v1/chat/completions")
        print("   GET  /v1/models")
        print("\n📌 模型名称格式:")
        print("   - kimi")
        print("   - lmarena")
        print("   - lmarena:claude-opus-4-5-20251101-thinking-32k")
        print("   - lmarena:gemini-3-pro")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n" + "=" * 50)
        print("📌 解决方法：")
        print("=" * 50)
        print(f"\n方案: 手动启动 Chrome 后再运行程序")
        print(f'   chrome.exe --remote-debugging-port={CHROME_PORT} --user-data-dir="{CHROME_USER_DATA_DIR}"')
        print("=" * 50 + "\n")
        sys.exit(1)

# ============== OpenAI 兼容 API ==============

@app.get("/v1/models", response_model=ModelListResponse)
def list_models():
    """
    列出可用的模型（OpenAI 兼容）
    """
    current_time = int(time.time())
    
    models = [
        ModelInfo(id="kimi", created=current_time, owned_by="moonshot"),
        ModelInfo(id="lmarena", created=current_time, owned_by="lmarena"),
        ModelInfo(id="lmarena:claude-opus-4-5-20251101-thinking-32k", created=current_time, owned_by="lmarena"),
        ModelInfo(id="lmarena:gpt-4o", created=current_time, owned_by="lmarena"),
        ModelInfo(id="lmarena:gemini-2.5-pro", created=current_time, owned_by="lmarena"),
    ]
    
    return ModelListResponse(data=models)

@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    创建聊天补全（OpenAI 兼容）
    
    支持的模型格式:
    - kimi: 使用 Kimi
    - lmarena: 使用 LMArena（默认模型）
    - lmarena:模型名: 使用 LMArena 指定模型
    
    示例:
    - model: "kimi"
    - model: "lmarena"
    - model: "lmarena:claude-opus-4-5-20251101-thinking-32k"
    - model: "lmarena:gemini-3-pro"
    """
    
    # 检查是否请求流式输出（当前不支持）
    if request.stream:
        raise HTTPException(
            status_code=400, 
            detail="当前版本不支持流式输出，请设置 stream=false"
        )
    
    # 提取用户消息
    # 合并所有消息为一个查询（简化处理）
    messages = request.messages
    
    # 构建查询文本
    query_parts = []
    for msg in messages:
        if msg.role == "system":
            query_parts.append(f"[系统指令] {msg.content}")
        elif msg.role == "user":
            query_parts.append(msg.content)
        elif msg.role == "assistant":
            # 助手消息可以作为上下文（但当前实现是新对话，所以跳过）
            pass
    
    query = "\n".join(query_parts)
    
    if not query.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    
    print(f"[OpenAI API] 收到请求:")
    print(f"  模型: {request.model}")
    print(f"  消息数: {len(messages)}")
    print(f"  查询: {query[:100]}...")
    
    # 路由到对应的 bot
    # 注意：这里每次请求都开启新对话，因为 OpenAI API 是无状态的
    # 如果需要支持多轮对话，需要额外的会话管理
    result = route_to_bot(request.model, query, new_chat=True)
    
    # 构建回复内容
    # 如果有思考过程，可以选择性地包含在回复中
    answer_content = result["answer"]
    if result.get("thought"):
        # 可选：将思考过程作为注释包含
        # answer_content = f"<思考>\n{result['thought']}\n</思考>\n\n{result['answer']}"
        pass
    
    # 估算 token 数（简单按字符估算，实际应该用 tiktoken）
    prompt_tokens = len(query) // 2  # 粗略估计
    completion_tokens = len(answer_content) // 2
    
    # 构建响应
    response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=result["model"],
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=answer_content
                ),
                finish_reason="stop"
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
    )
    
    print(f"[OpenAI API] 响应完成，回复长度: {len(answer_content)} 字符")
    
    return response

# ============== 原有 API（保留兼容） ==============

@app.get("/")
def root():
    """根路径 - 状态检查"""
    return {
        "status": "running",
        "version": "0.1.0",
        "available_models": ["kimi", "lmarena", "lmarena:<model_name>"],
        "openai_compatible": True,
        "endpoints": {
            "openai": "/v1/chat/completions",
            "models": "/v1/models",
            "kimi": "/v1/chat/kimi",
            "lmarena": "/v1/chat/lmarena"
        }
    }

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "browser_connected": browser is not None}

@app.post("/v1/chat/kimi", response_model=ChatResponse)
def chat_with_kimi(request: ChatRequest):
    """
    与 Kimi 对话
    
    - **query**: 用户问题
    - **new_chat**: 是否开启新对话 (可选，默认 False)
    """
    global kimi_bot
    
    if kimi_bot is None:
        raise HTTPException(status_code=503, detail="Kimi 机器人未初始化")
    
    try:
        # 是否需要开启新对话
        if request.new_chat:
            kimi_bot.new_chat()
        
        # 激活标签页
        kimi_bot.activate()
        
        # 发送问题并获取回答
        answer = kimi_bot.ask(request.query)
        
        # 检查是否有错误
        if answer.startswith("Error:"):
            raise HTTPException(status_code=500, detail=answer)
        
        return ChatResponse(
            model="kimi-web",
            answer=answer,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 修改 LMArena 路由
@app.post("/v1/chat/lmarena", response_model=LMArenaResponse)
def chat_with_lmarena(request: LMArenaRequest):
    """
    与 LMArena 对话
    
    - **query**: 用户问题
    - **model**: 指定模型名称 (可选)
    - **new_chat**: 是否开启新对话 (可选，默认 False)
    """
    global lmarena_bot
    
    if lmarena_bot is None:
        raise HTTPException(status_code=503, detail="LMArena 机器人未初始化")
    
    try:
        # 是否需要开启新对话
        if request.new_chat:
            lmarena_bot.new_chat()
        
        # 激活标签页
        lmarena_bot.activate()
        
        # 发送问题并获取回答（可指定模型）
        result = lmarena_bot.ask(request.query, model_name=request.model)
        
        # 检查是否有错误
        if result["answer"].startswith("Error:"):
            raise HTTPException(status_code=500, detail=result["answer"])
        
        # 获取当前使用的模型
        current_model = lmarena_bot.current_model or "default"
        
        return LMArenaResponse(
            model=f"lmarena-{current_model}",
            thought=result["thought"],
            answer=result["answer"],
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============== 主入口 ==============
if __name__ == "__main__":
    print("\n📌 使用说明:")
    print("=" * 50)
    print("1. 首次使用请先修改 config.py 中的用户数据目录")
    print(f"   当前: {CHROME_USER_DATA_DIR}")
    print("2. 确保已在浏览器中登录对应平台")
    print("3. API 文档: http://127.0.0.1:8000/docs")
    print("\n📌 OpenAI 兼容调用示例:")
    print('   from openai import OpenAI')
    print('   client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")')
    print('   response = client.chat.completions.create(')
    print('       model="lmarena:claude-opus-4",')
    print('       messages=[{"role": "user", "content": "Hello!"}]')
    print('   )')
    print("=" * 50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)