# tests/test_real_llm.py
import pytest


pytestmark = pytest.mark.skip(reason="integration test — requires API key and network")


def test_real_llm_requires_api_key():
    from agentos.llm.real import RealLLMClient
    client = RealLLMClient(api_key="sk-test")
    assert client is not None
