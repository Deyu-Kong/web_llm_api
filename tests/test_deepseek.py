from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")

# 使用 DeepSeek
response = client.chat.completions.create(
    model="deepseek",
    messages=[{"role": "user", "content": "解释一下量子纠缠"}]
)
print(response.choices[0].message.content)