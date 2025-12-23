from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")

# 使用腾讯元宝
response = client.chat.completions.create(
    model="kimi",
    messages=[{"role": "user", "content": "你好！详细介绍你自己"}]
)
print(response.choices[0].message.content)

