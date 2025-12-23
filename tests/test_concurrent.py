import concurrent.futures
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="x")

def ask(question):
    return client.chat.completions.create(
        model="kimi",
        messages=[{"role": "user", "content": question}]
    )

# 并行发送 3 个请求
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(ask, "1+1等于几？"),
        executor.submit(ask, "2+2等于几？"),
        executor.submit(ask, "3+3等于几？"),
    ]
    
    for f in concurrent.futures.as_completed(futures):
        print(f.result().choices[0].message.content[:50])