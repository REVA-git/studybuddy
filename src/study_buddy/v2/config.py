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
    provider: ModelProvider = ModelProvider.OLLAMA


# tool models
QWEN_3_4b = ModelConfig("qwen3:4b", 0.7)
STUDY_BUDDY = ModelConfig("reva-studybuddy:latest", 0.7)
LLAMA_3_2_3b = ModelConfig("llama3.2:3b", 0.7)
QWEN_2_5_0_5b = ModelConfig("qwen2.5:0.5b", 0.7)

# models
GEMMA_3_1b = ModelConfig("gemma3:1b", 0.7)
GEMMA_3_4b = ModelConfig("gemma3:4b", 0.7)


class Config:
    SEED = 42
    CHAT_MODEL = STUDY_BUDDY
    TOOL_MODEL = STUDY_BUDDY

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
