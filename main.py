# main.py
"""
WebLLM API v0.5
通过 DrissionPage 控制浏览器，将网页版 LLM 封装为 OpenAI 兼容 API
"""

import uvicorn
import time
import uuid
import sys
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from DrissionPage import ChromiumPage, ChromiumOptions

from config import CHROME_PORT, CHROME_USER_DATA_DIR, DEFAULT_LMARENA_MODEL
from adapters import KimiBot, LMArenaBot, YuanbaoBot, DeepSeekBot

# ============== FastAPI 初始化 ==============
app = FastAPI(
    title="WebLLM API",
    description="将网页版 LLM 封装为 OpenAI 兼容 API",
    version="0.3.0"
)

# ============== 全局变量 ==============
browser = None
bots = {}  # 统一管理所有 Bot 实例

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
    "元宝": ("yuanbao", None),
    "lmarena": ("lmarena", None),
}

def parse_model_name(model: str) -> tuple:
    """
    解析模型名称
    返回: (bot_type, specific_model)
    """
    model = model.lower().strip()
    
    # 检查 lmarena:xxx 格式
    if model.startswith("lmarena:"):
        return ("lmarena", model.split(":", 1)[1])
    
    # 查找别名
    if model in MODEL_ALIASES:
        return MODEL_ALIASES[model]
    
    # 默认作为 lmarena 模型
    return ("lmarena", model)


def call_bot(bot_type: str, query: str, specific_model: str = None) -> dict:
    """
    调用指定的 Bot
    返回: {"model": str, "thought": str, "answer": str}
    """
    if bot_type not in bots or bots[bot_type] is None:
        raise HTTPException(status_code=503, detail=f"{bot_type} 机器人未初始化")
    
    bot = bots[bot_type]
    bot.activate()
    
    # 根据 Bot 类型调用
    if bot_type == "kimi":
        answer = bot.ask(query)
        if isinstance(answer, str) and answer.startswith("Error:"):
            raise HTTPException(status_code=500, detail=answer)
        return {"model": "kimi", "thought": "", "answer": answer}
    
    elif bot_type == "lmarena":
        result = bot.ask(query, model_name=specific_model)
        if result["answer"].startswith("Error:"):
            raise HTTPException(status_code=500, detail=result["answer"])
        model_name = f"lmarena:{specific_model}" if specific_model else "lmarena"
        return {"model": model_name, "thought": result.get("thought", ""), "answer": result["answer"]}
    
    else:  # deepseek, yuanbao
        result = bot.ask(query)
        if result["answer"].startswith("Error:"):
            raise HTTPException(status_code=500, detail=result["answer"])
        return {"model": bot_type, "thought": result.get("thought", ""), "answer": result["answer"]}



# ============== 启动事件 ==============
@app.on_event("startup")
def startup_event():
    """服务启动时连接浏览器并初始化所有 Bot"""
    global browser, bots
    
    print("=" * 50)
    print("🚀 Web-LLM API v0.3.0 启动中...")
    print("=" * 50)
    
    try:
        # 配置并连接 Chrome
        co = ChromiumOptions()
        
        # 设置远程调试端口
        co.set_local_port(CHROME_PORT)
                
        # 其他有用的配置
        co.set_argument('--no-sandbox')  # 禁用沙盒模式
        # co.set_argument('--disable-gpu')  # 禁用 GPU 加速（可选）
        # co.headless(False)  # 显示浏览器窗口（默认）
        
        # 连接或启动浏览器
        print(f"🔌 尝试连接到端口 {CHROME_PORT}...")
        browser = ChromiumPage(addr_or_opts=co)
        
        print(f"✅ 成功连接到 Chrome (端口: {CHROME_PORT})")
        
        # 初始化所有 Bot
        bots["kimi"] = KimiBot(browser)
        bots["lmarena"] = LMArenaBot(browser, model_name=DEFAULT_LMARENA_MODEL)
        bots["yuanbao"] = YuanbaoBot(browser)
        bots["deepseek"] = DeepSeekBot(browser)
        
        print("✅ 所有机器人初始化完成")
        print("\n" + "=" * 50)
        print("📌 支持的模型: kimi, deepseek, yuanbao, lmarena:<model>")
        print("📌 API 文档: http://127.0.0.1:8000/docs")
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print(f"\n请先启动 Chrome 调试模式:")
        print(f'  chrome --remote-debugging-port={CHROME_PORT} --user-data-dir="{CHROME_USER_DATA_DIR}"')
        sys.exit(1)


def build_query(messages: List[ChatMessage]) -> str:
    """将消息列表构建为查询文本"""
    parts = []
    for msg in messages:
        if msg.role == "system":
            parts.append(f"[系统指令] {msg.content}")
        elif msg.role == "user":
            parts.append(msg.content)
    return "\n".join(parts)


def build_response(result: dict, request_model: str) -> ChatCompletionResponse:
    """构建 OpenAI 格式的响应"""
    answer = result["answer"]
    
    # 估算 token（粗略）
    prompt_tokens = len(result.get("query", "")) // 2
    completion_tokens = len(answer) // 2
    
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
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
    )

# ============== API 路由 ==============

@app.get("/")
def root():
    """服务状态"""
    return {
        "status": "running",
        "version": "0.3.0",
        "models": ["kimi", "deepseek", "yuanbao", "lmarena"],
        "docs": "/docs"
    }


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "healthy", "browser": browser is not None}


@app.get("/v1/models", response_model=ModelListResponse)
def list_models():
    """获取可用模型列表"""
    now = int(time.time())
    models = [
        ModelInfo(id="kimi", created=now, owned_by="moonshot"),
        ModelInfo(id="deepseek", created=now, owned_by="deepseek"),
        ModelInfo(id="yuanbao", created=now, owned_by="tencent"),
        ModelInfo(id="lmarena", created=now, owned_by="lmarena"),
        ModelInfo(id="lmarena:gpt-4o", created=now, owned_by="lmarena"),
        ModelInfo(id="lmarena:claude-opus-4", created=now, owned_by="lmarena"),
        ModelInfo(id="lmarena:gemini-2.5-pro", created=now, owned_by="lmarena"),
    ]
    return ModelListResponse(data=models)


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(
    request: ChatCompletionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    OpenAI 兼容的对话接口
    
    支持的模型:
    - kimi: Kimi
    - deepseek / ds: DeepSeek
    - yuanbao / tencent: 腾讯元宝
    - lmarena: LMArena 默认模型
    - lmarena:<model>: LMArena 指定模型
    """
    if request.stream:
        raise HTTPException(status_code=400, detail="暂不支持流式输出")
    
    # 构建查询
    query = build_query(request.messages)
    if not query.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    
    # 解析模型并路由
    bot_type, specific_model = parse_model_name(request.model)
    print(f"[API] 模型: {request.model} -> {bot_type}, 查询: {query[:50]}...")
    
    # 调用 Bot（每次开新对话，保持无状态）
    bot = bots.get(bot_type)
    if bot:
        bot.new_chat()
    
    result = call_bot(bot_type, query, specific_model)
    result["query"] = query
    
    print(f"[API] 完成，回复长度: {len(result['answer'])} 字符")
    
    return build_response(result, request.model)


# ============== 主入口 ==============

if __name__ == "__main__":
    print("\n📌 使用方法:")
    print("=" * 50)
    print("1. 启动 Chrome 调试模式")
    print("2. 在浏览器中登录各 LLM 平台")
    print("3. 运行本程序")
    print("\n示例调用:")
    print('  from openai import OpenAI')
    print('  client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="x")')
    print('  client.chat.completions.create(model="kimi", messages=[...])')
    print("=" * 50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)