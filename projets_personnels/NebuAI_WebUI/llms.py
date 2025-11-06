from enum import Enum
from typing import Optional
from doc_llm.engines.engine import Engine


class EngineType(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    MOCK = "mock"


def initialize(
    inference_mode: str, default_model: Optional[str] = None
) -> tuple[Engine, list[str]]:
    """
    This function loads the DocLLM Engine according to the inference mode (OpenAI API or Ollama)
    and returns the list of available models
    """
    match inference_mode:
        case EngineType.OPENAI:
            from doc_llm.engines.openai import OpenAIEngine

            model = "gpt-3.5-turbo"
            if default_model:
                model = default_model

            engine = OpenAIEngine(model)
            available_models = ["gpt-3.5-turbo", "gpt-4-turbo"]
        case EngineType.OLLAMA:
            import ollama

            models = ollama.list()
            available_models = [model["name"] for model in models["models"]]
            if not len(available_models):
                raise ValueError("You have no Ollama model downloaded.")

            model = available_models[0]
            if default_model:
                model = default_model
            from doc_llm.engines.ollama import OllamaEngine

            engine = OllamaEngine(model)
        case EngineType.MOCK:
            from doc_llm.engines.mock import MockEngine

            available_models = ["Mock"]
            engine = MockEngine()
    return engine, available_models
