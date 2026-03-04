"""测试第三方 API 连接"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 配置模型
llm = ChatOpenAI(
    model="gemini-2.5-flash",
    api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
    base_url="https://tb.api.mkeai.com",
)

# 测试简单调用
try:
    print("🔍 测试 API 连接...")
    response = llm.invoke([HumanMessage(content="你好，请回复'测试成功'")])
    print(f"✅ API 响应: {response.content}")
except Exception as e:
    print(f"❌ API 错误: {e}")
    print(f"错误类型: {type(e)}")
