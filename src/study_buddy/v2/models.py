from functools import lru_cache

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from study_buddy.v2.config import Config, ModelConfig, ModelProvider


@lru_cache(maxsize=1)
def create_embeddings() -> FastEmbedEmbeddings:
    return FastEmbedEmbeddings(model_name=Config.Memory.EMBEDDING_MODEL)


def create_llm(model_config: ModelConfig) -> BaseChatModel:
    if model_config.provider == ModelProvider.OLLAMA:
        return ChatOllama(
            model=model_config.name,
            temperature=model_config.temperature,
            verbose=False,
            keep_alive=1,
        )
    else:
        raise ValueError(f"Unsupported model provider: {model_config.provider}")
