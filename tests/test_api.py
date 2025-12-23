# test_openai.py
"""
测试 OpenAI 兼容 API
使用官方 OpenAI Python SDK 进行调用
"""

from openai import OpenAI

# 配置客户端
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="not-needed"  # 本地服务不需要真实的 API key
)

def test_list_models():
    """测试获取模型列表"""
    print("=" * 50)
    print("测试 1: 获取模型列表")
    print("=" * 50)
    
    try:
        models = client.models.list()
        print("可用模型:")
        for model in models.data:
            print(f"  - {model.id} (owned by: {model.owned_by})")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_kimi():
    """测试 Kimi 模型"""
    print("\n" + "=" * 50)
    print("测试 2: Kimi 模型")
    print("=" * 50)
    
    try:
        response = client.chat.completions.create(
            model="kimi",
            messages=[
                {"role": "user", "content": "你好，请用一句话介绍你自己"}
            ]
        )
        
        print(f"模型: {response.model}")
        print(f"回复: {response.choices[0].message.content}")
        print(f"Token 使用: {response.usage.total_tokens}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_lmarena_default():
    """测试 LMArena 默认模型"""
    print("\n" + "=" * 50)
    print("测试 3: LMArena 默认模型")
    print("=" * 50)
    
    try:
        response = client.chat.completions.create(
            model="lmarena",
            messages=[
                {"role": "user", "content": "你好，请用一句话介绍你自己"}
            ]
        )
        
        print(f"模型: {response.model}")
        print(f"回复: {response.choices[0].message.content}")
        print(f"Token 使用: {response.usage.total_tokens}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_lmarena_specific_model(model_name: str = "claude-opus-4-5-20251101-thinking-32k"):
    """测试 LMArena 指定模型"""
    print("\n" + "=" * 50)
    print(f"测试 4: LMArena 指定模型 ({model_name})")
    print("=" * 50)
    
    try:
        response = client.chat.completions.create(
            model=f"lmarena:{model_name}",
            messages=[
                {"role": "system", "content": "你是一个友好的助手"},
                {"role": "user", "content": "你好，请用一句话介绍你自己"}
            ]
        )
        
        print(f"模型: {response.model}")
        print(f"回复: {response.choices[0].message.content}")
        print(f"Token 使用: {response.usage.total_tokens}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def test_multi_turn_conversation():
    """测试多轮对话（注意：当前实现每次都是新对话）"""
    print("\n" + "=" * 50)
    print("测试 5: 多轮对话格式")
    print("=" * 50)
    
    try:
        response = client.chat.completions.create(
            model="lmarena",
            messages=[
                {"role": "system", "content": "你是一个数学老师"},
                {"role": "user", "content": "1+1等于多少？"},
                {"role": "assistant", "content": "1+1=2"},
                {"role": "user", "content": "那再加1呢？"}
            ]
        )
        
        print(f"模型: {response.model}")
        print(f"回复: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def interactive_chat():
    """交互式对话"""
    print("\n" + "=" * 50)
    print("交互式对话模式")
    print("输入 'quit' 退出, 'model:xxx' 切换模型")
    print("=" * 50)
    
    current_model = "lmarena"
    
    while True:
        user_input = input(f"\n[{current_model}] 你: ").strip()
        
        if user_input.lower() == 'quit':
            print("再见！")
            break
        
        if user_input.lower().startswith('model:'):
            current_model = user_input[6:].strip()
            print(f"已切换到模型: {current_model}")
            continue
        
        if not user_input:
            continue
        
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": user_input}]
            )
            print(f"\n助手: {response.choices[0].message.content}")
        except Exception as e:
            print(f"\n错误: {e}")

if __name__ == "__main__":
    print("\n🧪 开始测试 OpenAI 兼容 API\n")
    
    # 运行测试
    test_list_models()
    
    # 可以选择性运行以下测试
    # test_kimi()
    test_lmarena_default()
    # test_lmarena_specific_model()
    # test_multi_turn_conversation()
    
    # 交互式对话
    # interactive_chat()
    
    print("\n✅ 测试完成!")