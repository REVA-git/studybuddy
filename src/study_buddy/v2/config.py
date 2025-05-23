from dataclasses import dataclass
from pathlib import Path
import os
import random
import sys
from enum import StrEnum
from loguru import logger


class ModelProvider(StrEnum):
    OLLAMA = "ollama"


@dataclass
class ModelConfig:
    name: str
    temperature: float
    provider: ModelProvider


GEMMA_3 = ModelConfig("gemma3:1b", 0.7, ModelProvider.OLLAMA)
QWEN = ModelConfig("qwen2.5:0.5b", 0.7, ModelProvider.OLLAMA)


class Config:
    SEED = 42
    CHAT_MODEL = GEMMA_3
    TOOL_MODEL = QWEN

    class Path:
        APP_HOME = Path(os.getenv("APP_HOME", Path(__file__).parent.parent.parent))
        DATA_DIR = APP_HOME / "data"
        print(f"{DATA_DIR=}")
        DATABASE_PATH = DATA_DIR / "studybuddy.sqlite3"

    class Memory:
        EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
        MAX_RECALL_COUNT = 5


def seed_everything(seed: int = Config.SEED):
    random.seed(seed)
