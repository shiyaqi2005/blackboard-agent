"""测试结构化输出"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

class TestOutput(BaseModel):
    """测试输出结构"""
    name: str = Field(description="名字")
    age: int = Field(description="年龄")

# 配置模型
llm = ChatOpenAI(
    model="gemini-2.5-flash",
    api_key="sk-2OsXSnW0fVfpFVnT4HeOkGDue8bxgRflUSc9KqCx7mnNOTgb",
    base_url="https://tb.api.mkeai.com",
)

print("🔍 测试结构化输出...")
try:
    chain = llm.with_structured_output(TestOutput)
    result = chain.invoke([HumanMessage(content="我叫张三，今年25岁")])
    print(f"✅ 结构化输出成功: {result}")
    print(f"类型: {type(result)}")
except Exception as e:
    print(f"❌ 结构化输出错误: {e}")
    import traceback
    traceback.print_exc()
