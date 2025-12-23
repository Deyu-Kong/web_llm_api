# main.py
"""
Pantheon API v0.1
通过 DrissionPage 控制浏览器，将网页版 LLM 封装为 API
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from DrissionPage import ChromiumPage, ChromiumOptions
import sys
import os

from config import CHROME_PORT, CHROME_USER_DATA_DIR, DEFAULT_LMARENA_MODEL
from adapters import KimiBot, LMArenaBot

# ============== FastAPI 初始化 ==============
app = FastAPI(
    title="Pantheon API",
    description="将网页版 LLM 封装为本地 API",
    version="0.1.0"
)

# ============== 全局变量 ==============
browser = None
kimi_bot = None
lmarena_bot = None  # 新增

# ============== 数据模型 ==============
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

# ============== 启动事件 ==============
@app.on_event("startup")
def startup_event():
    """服务启动时连接浏览器"""
    global browser, kimi_bot, lmarena_bot
    
    print("=" * 50)
    print("🚀 Pantheon API v0.1 启动中...")
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
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n" + "=" * 50)
        print("📌 解决方法：")
        print("=" * 50)
        print("\n方案 1: 修改 config.py 中的 CHROME_USER_DATA_DIR")
        print(f"   当前配置: {CHROME_USER_DATA_DIR}")
        print("   改为你的 Chrome 用户数据目录路径\n")
        print("方案 2: 手动启动 Chrome 后再运行程序")
        print("   Windows:")
        print(f'   chrome.exe --remote-debugging-port={CHROME_PORT} --user-data-dir="{CHROME_USER_DATA_DIR}"\n')
        print("   macOS:")
        print(f'   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={CHROME_PORT} --user-data-dir="{CHROME_USER_DATA_DIR}"\n')
        print("=" * 50 + "\n")
        sys.exit(1)

# ============== API 路由 ==============
@app.get("/")
def root():
    """根路径 - 状态检查"""
    return {
        "status": "running",
        "version": "0.1.0",
        "available_models": ["kimi", "lmarena"]  # 更新
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
    print("=" * 50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)