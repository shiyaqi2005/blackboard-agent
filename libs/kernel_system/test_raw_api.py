"""测试第三方 API 原始响应"""
import requests

url = "https://tb.api.mkeai.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
    "Content-Type": "application/json"
}
data = {
    "model": "gemini-2.5-flash",
    "messages": [{"role": "user", "content": "你好"}]
}

print("🔍 测试原始 API 请求...")
try:
    response = requests.post(url, headers=headers, json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应头: {response.headers}")
    print(f"响应内容: {response.text[:500]}")  # 只显示前500字符
except Exception as e:
    print(f"❌ 请求错误: {e}")
