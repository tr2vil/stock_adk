"""
Model factory - 에이전트 모델 문자열을 ADK 모델 객체로 변환.

지원 형태:
- Gemini (Vertex AI / Google GenAI): "gemini-2.5-flash", "gemini-2.5-pro"
    → 문자열 그대로 반환 (ADK가 직접 처리)
- Anthropic Claude (LiteLLM 경유, ANTHROPIC_API_KEY 사용):
    "claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5",
    또는 명시적 "anthropic/claude-..." 형식
    → LiteLlm 래퍼 반환

환경변수 <AGENT>_MODEL 값만 바꾸면 Gemini ↔ Claude 전환이 됩니다.
예: NEWS_AGENT_MODEL=claude-sonnet-4-6
"""
import logging

logger = logging.getLogger(__name__)


def resolve_model(model_str: str):
    """모델 문자열을 ADK가 사용할 모델 값으로 변환.

    Args:
        model_str: 모델 식별자 (예: "gemini-2.5-flash", "claude-opus-4-8")

    Returns:
        Gemini 계열이면 문자열 그대로, Claude 계열이면 LiteLlm 인스턴스.
    """
    if not model_str:
        return model_str

    lowered = model_str.lower()
    is_anthropic = lowered.startswith("anthropic/") or lowered.startswith("claude")

    if not is_anthropic:
        # Gemini 등은 ADK가 문자열로 직접 처리
        return model_str

    # Claude 모델 → LiteLLM 경유. import는 필요할 때만 (litellm 미설치 환경 보호)
    try:
        from google.adk.models.lite_llm import LiteLlm
    except ImportError as e:
        raise ImportError(
            "Claude 모델을 사용하려면 litellm이 필요합니다. "
            "`pip install litellm` 또는 requirements.txt 설치 후 재시도하세요."
        ) from e

    # LiteLLM은 'provider/model' 형식을 요구. 접두어가 없으면 anthropic/ 부여.
    litellm_model = model_str if "/" in model_str else f"anthropic/{model_str}"
    logger.info(f"Using Anthropic model via LiteLLM: {litellm_model}")
    return LiteLlm(model=litellm_model)
