# main.py
"""
WebLLM API v0.5
通过 DrissionPage 控制浏览器，将网页版 LLM 封装为 OpenAI 兼容 API
支持多标签页并行处理请求
"""

import uvicorn
import time
import uuid
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from DrissionPage import ChromiumPage, ChromiumOptions

from config import CHROME_PORT, CHROME_USER_DATA_DIR, DEFAULT_LMARENA_MODEL
from adapters import KimiBot, LMArenaBot, YuanbaoBot, DeepSeekBot, BaseBot
from core import TabPoolManager

# ============== FastAPI 初始化 ==============
app = FastAPI(
    title="WebLLM API",
    description="将网页版 LLM 封装为 OpenAI 兼容 API",
    version="0.5.0"
)

# ============== 全局变量 ==============
browser = None
tab_pool: TabPoolManager = None
executor = ThreadPoolExecutor(max_workers=10)

# Bot 类映射
BOT_CLASSES = {
    "kimi": KimiBot,
    "deepseek": DeepSeekBot,
    "yuanbao": YuanbaoBot,
    "lmarena": LMArenaBot,
}

# ============== 数据模型 ==============

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0, le=2)
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length"]

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

# ============== 模型路由 ==============

# 支持的模型映射
MODEL_ALIASES = {
    "kimi": ("kimi", None),
    "deepseek": ("deepseek", None),
    "ds": ("deepseek", None),
    "yuanbao": ("yuanbao", None),
    "tencent": ("yuanbao", None),
    "lmarena": ("lmarena", None),
}

def parse_model_name(model: str) -> tuple:
    """解析模型名称 -> (bot_type, specific_model)"""
    model = model.lower().strip()
    
    # 检查 lmarena:xxx 格式
    if model.startswith("lmarena:"):
        return ("lmarena", model.split(":", 1)[1])
    
    # 查找别名
    if model in MODEL_ALIASES:
        return MODEL_ALIASES[model]
    
    # 默认作为 lmarena 模型
    return ("lmarena", model)


def create_bot_instance(bot_type: str, tab) -> BaseBot:
    """为指定标签页创建 Bot 实例"""
    bot_class = BOT_CLASSES.get(bot_type)
    if not bot_class:
        raise ValueError(f"未知的 Bot 类型: {bot_type}")
    
    # 创建 Bot 实例，传入 tab
    if bot_type == "lmarena":
        bot = bot_class(page=None, tab=tab, model_name=DEFAULT_LMARENA_MODEL)
    else:
        bot = bot_class(page=None, tab=tab)
    
    return bot


def execute_chat(bot_type: str, query: str, specific_model: str = None) -> dict:
    """
    在独立标签页中执行对话
    
    这是核心函数：从标签页池获取标签页，创建 Bot，执行对话
    """
    global tab_pool
    
    request_id = uuid.uuid4().hex[:8]
    print(f"[{request_id}] 开始处理: {bot_type}, 查询: {query[:30]}...")
    
    # 从池中获取标签页
    with tab_pool.get_tab(bot_type) as tab_info:
        try:
            # 创建 Bot 实例
            bot = create_bot_instance(bot_type, tab_info.tab)
            
            # 激活并开新对话
            bot.activate()
            bot.new_chat()
            
            # 执行对话
            if bot_type == "kimi":
                answer = bot.ask(query)
                result = {"thought": "", "answer": answer}
            elif bot_type == "lmarena":
                result = bot.ask(query, model_name=specific_model)
            else:
                result = bot.ask(query)
            
            # 检查错误
            answer = result if isinstance(result, str) else result.get("answer", "")
            if answer.startswith("Error:"):
                raise Exception(answer)
            
            print(f"[{request_id}] ✅ 完成")
            
            return {
                "model": f"{bot_type}:{specific_model}" if specific_model else bot_type,
                "thought": result.get("thought", "") if isinstance(result, dict) else "",
                "answer": answer if isinstance(result, str) else result.get("answer", ""),
                "query": query
            }
            
        except Exception as e:
            print(f"[{request_id}] ❌ 失败: {e}")
            raise


def build_query(messages: List[ChatMessage]) -> str:
    """构建查询文本"""
    parts = []
    for msg in messages:
        if msg.role == "system":
            parts.append(f"[系统指令] {msg.content}")
        elif msg.role == "user":
            parts.append(msg.content)
    return "\n".join(parts)


def build_response(result: dict) -> ChatCompletionResponse:
    """构建 OpenAI 格式响应"""
    answer = result["answer"]
    query = result.get("query", "")
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=result["model"],
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=answer),
                finish_reason="stop"
            )
        ],
        usage=Usage(
            prompt_tokens=len(query) // 2,
            completion_tokens=len(answer) // 2,
            total_tokens=(len(query) + len(answer)) // 2
        )
    )

# ============== 启动事件 ==============

@app.on_event("startup")
def startup_event():
    """启动时初始化浏览器和标签页池"""
    global browser, tab_pool
    
    print("=" * 50)
    print("🚀 Pantheon API v0.4.0 (多标签页并行版)")
    print("=" * 50)
    
    try:
        co = ChromiumOptions()
        co.set_local_port(CHROME_PORT)
        co.set_argument('--no-sandbox')
        
        print(f"🔌 连接 Chrome (端口 {CHROME_PORT})...")
        browser = ChromiumPage(addr_or_opts=co)
        print("✅ 浏览器连接成功")
        
        # 初始化标签页池
        tab_pool = TabPoolManager(
            browser=browser,
            max_tabs_per_bot=3,  # 每种 Bot 最多 3 个并行标签页
            tab_timeout=300      # 闲置 5 分钟后清理
        )
        
        print("\n" + "=" * 50)
        print("📌 支持并行请求，每种模型最多 3 个并发")
        print("📌 模型: kimi, deepseek, yuanbao, lmarena:<model>")
        print("📌 API: http://127.0.0.1:8000/docs")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print(f'请先启动 Chrome: chrome --remote-debugging-port={CHROME_PORT}')
        sys.exit(1)


@app.on_event("shutdown")
def shutdown_event():
    """关闭时清理资源"""
    global executor
    executor.shutdown(wait=False)
    print("👋 服务已关闭")

# ============== API 路由 ==============

@app.get("/")
def root():
    """服务状态"""
    stats = tab_pool.get_stats() if tab_pool else {}
    return {
        "status": "running",
        "version": "0.4.0",
        "parallel": True,
        "tab_stats": stats,
        "models": ["kimi", "deepseek", "yuanbao", "lmarena"],
        "docs": "/docs"
    }


@app.get("/health")
def health():
    """健康检查"""
    return {
        "status": "healthy",
        "browser": browser is not None,
        "tab_pool": tab_pool is not None
    }


@app.get("/v1/models", response_model=ModelListResponse)
def list_models():
    """获取可用模型"""
    now = int(time.time())
    return ModelListResponse(data=[
        ModelInfo(id="kimi", created=now, owned_by="moonshot"),
        ModelInfo(id="deepseek", created=now, owned_by="deepseek"),
        ModelInfo(id="yuanbao", created=now, owned_by="tencent"),
        ModelInfo(id="lmarena", created=now, owned_by="lmarena"),
        ModelInfo(id="lmarena:gpt-4o", created=now, owned_by="lmarena"),
        ModelInfo(id="lmarena:claude-opus-4", created=now, owned_by="lmarena"),
    ])


@app.get("/v1/pool/stats")
def pool_stats():
    """获取标签页池状态"""
    if not tab_pool:
        return {"error": "标签页池未初始化"}
    return tab_pool.get_stats()


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    OpenAI 兼容对话接口（支持并行）
    
    每个请求使用独立标签页，支持多请求并行处理
    """
    if request.stream:
        raise HTTPException(status_code=400, detail="暂不支持流式输出")
    
    # 构建查询
    query = build_query(request.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    
    # 解析模型并路由
    bot_type, specific_model = parse_model_name(request.model)
    
    if bot_type not in BOT_CLASSES:
        raise HTTPException(status_code=400, detail=f"不支持的模型: {request.model}")
    
    print(f"[API] 收到请求: {request.model} -> {bot_type}")
    
    try:
        # 在标签页池中执行（自动分配标签页）
        result = execute_chat(bot_type, query, specific_model)
        return build_response(result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/pool/cleanup")
def cleanup_pool(background_tasks: BackgroundTasks):
    """手动清理闲置标签页"""
    if tab_pool:
        background_tasks.add_task(tab_pool.cleanup_idle_tabs)
        return {"message": "清理任务已提交"}
    return {"error": "标签页池未初始化"}


# ============== 主入口 ==============

if __name__ == "__main__":
    print("\n📌 Pantheon API v0.4.0 - 多标签页并行版")
    print("=" * 50)
    print("特性: 每个请求使用独立标签页，支持并行处理")
    print("=" * 50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)