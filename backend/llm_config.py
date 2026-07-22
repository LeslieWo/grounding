"""统一的模型配置。想换供应商（OpenAI / z.ai GLM / 其它 OpenAI 兼容接口），
只改 .env 里的三个值就行：OPENAI_API_KEY、OPENAI_BASE_URL、GROUNDING_MODEL。
"""
import os
from langchain_openai import ChatOpenAI


def get_model_name() -> str:
    return os.environ.get("GROUNDING_MODEL", "gpt-4o")


def struct_method() -> str:
    """结构化输出用哪种方式，因后端而异：
    - 本地 Ollama 视觉模型 → json_schema（不支持 tools）
    - z.ai GLM / OpenAI → function_calling（原生 tool use，最稳）
    改 .env 的 STRUCT_METHOD 即可。"""
    return os.environ.get("STRUCT_METHOD", "json_schema")


def make_chat(temperature: float = 0.5, model: str = None,
              disable_thinking: bool = None) -> ChatOpenAI:
    """按 .env 配置造一个聊天模型。
    - OPENAI_API_KEY：你的 key（OpenAI 的，或 z.ai 的，都放这里）
    - OPENAI_BASE_URL：留空=用 OpenAI 官方；填 z.ai 的地址=用 GLM
    - GROUNDING_MODEL：模型名（gpt-4o / glm-4.6 …）
    - model：临时覆盖模型名（比如建库用视觉模型，对话用文本大模型）
    - disable_thinking：是否关掉"深度思考"模式（GLM-4.6 默认开着，一句话要 20-35s，
      关掉只要 ~2s）。None=跟随 .env 的 DISABLE_THINKING；True/False=显式指定。
      视觉建库那步传 False，避免视觉模型不认这个参数而报错。
    """
    kwargs = {"model": model or get_model_name(), "temperature": temperature}
    base = os.environ.get("OPENAI_BASE_URL", "").strip()
    if base:
        kwargs["base_url"] = base
    if disable_thinking is None:
        disable_thinking = os.environ.get("DISABLE_THINKING", "").strip() in ("1", "true", "True", "yes")
    if disable_thinking:
        # z.ai GLM 的关思考开关，走 extra_body 塞进请求体（OpenAI client 不认它做顶层参数）
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    # api_key 会自动从环境变量 OPENAI_API_KEY 读取
    return ChatOpenAI(**kwargs)
