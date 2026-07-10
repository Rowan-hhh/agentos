from agentos.llm.interface import LLMClient
from openai import OpenAI


class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self._api_key = api_key
        self._model = model
        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    def __repr__(self) -> str:
        return f"RealLLMClient(model={self._model})"

    def __str__(self) -> str:
        return f"RealLLMClient(model={self._model})"

    def __del__(self):
        self._api_key = "INVALIDATED"
