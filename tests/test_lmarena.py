# test.py
"""
测试脚本 - 验证 WebLLM API 是否正常工作
"""

import requests

API_URL = "http://127.0.0.1:8000"

def test_health():
    """测试健康检查接口"""
    print("=" * 40)
    print("测试 1: 健康检查")
    print("=" * 40)
    
    try:
        resp = requests.get(f"{API_URL}/health")
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")
        return resp.status_code == 200
    except Exception as e:
        print(f"错误: {e}")
        return False
    
    
def test_lmarena_chat(query: str = "你好，请用一句话介绍你自己", model: str = None):
    """测试 LMArena 对话接口"""
    print("\n" + "=" * 40)
    print("测试 2: LMArena 对话")
    print("=" * 40)
    
    try:
        print(f"问题: {query}")
        if model:
            print(f"指定模型: {model}")
        print("等待回答中...\n")
        
        payload = {"query": query, "new_chat": True}
        if model:
            payload["model"] = model
        
        resp = requests.post(
            f"{API_URL}/v1/chat/lmarena",
            json=payload,
            timeout=180  # 增加超时时间
        )
        
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"模型: {data['model']}")
            if data.get('thought'):
                print(f"思考过程: {data['thought']}")
            print(f"回答: {data['answer']}")
            return True
        else:
            print(f"错误: {resp.text}")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        return False
    
    
if __name__ == "__main__":
    print("\n🧪 开始测试 WebLLM API\n")
    
    # 测试健康检查
    if not test_health():
        print("\n❌ 健康检查失败，请确保 API 服务已启动")
        exit(1)
        
    # 测试 LMArena 对话（不指定模型）
    test_lmarena_chat(
        query="解释一下量子纠缠", 
        model="gemini-3-pro"
    )
    
    # 测试 LMArena 对话（指定模型）
    # test_lmarena_chat(model="claude-opus-4-5-20251101-thinking-32k")
    
    print("\n✅ 所有测试完成!")