import os
import getpass
from pathlib import Path


def load_api_key() -> str:
    env_path = Path(".env")
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        key = os.environ.get("LLM_API_KEY")
        if key:
            return key
    return getpass.getpass("Enter LLM API Key: ")
