from agentos.llm.interface import LLMClient
from openai import OpenAI


class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str = "qwen-turbo"):
        self._api_key = api_key
        self._model = model
        self._client = OpenAI(api_key=api_key,base_url="https://njusehub.info/v1")

    def generate(self, prompt: str) -> str:
        system_prompt = (
            "You are an advanced AI Agent with access to local file system and execution tools. "
            "NEVER say you cannot access files or the local environment. "
            "You MUST use the provided tools to interact with the workspace. "
            "STRICTLY follow the output format requested in the prompt."
        )
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
        )
        return resp.choices[0].message.content

    def __repr__(self) -> str:
        return f"RealLLMClient(model={self._model})"

    def __str__(self) -> str:
        return f"RealLLMClient(model={self._model})"

    def __del__(self):
        self._api_key = "INVALIDATED"
