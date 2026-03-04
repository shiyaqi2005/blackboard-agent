"""
简单的 LLM 包装器，直接使用 openai 库调用第三方 API。
兼容 langchain 的 BaseChatModel 接口。
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from openai import OpenAI


class SimpleChatModel(BaseChatModel):
    """
    简单的聊天模型包装器，使用 openai 库直接调用 API。
    避免 langchain-openai 的兼容性问题。
    """

    client: Any = None
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 转换消息格式
        openai_messages = []
        for msg in messages:
            if hasattr(msg, "role"):
                role = msg.role
            else:
                role = msg.__class__.__name__.replace("Message", "").lower()
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"

            openai_messages.append({"role": role, "content": msg.content})

        # 调用 API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            stop=stop,
            **kwargs,
        )

        # 转换响应
        content = response.choices[0].message.content
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "simple_chat_model"
