from briefing_config import *
import os

_IS_POSIT = os.environ.get("POSIT_PRODUCT") == "CONNECT"

# MAI API (internal World Bank Azure OpenAI) settings — override via env vars if needed
_MAI_FAST_MODEL   = os.environ.get("MAI_FAST_MODEL",   "gpt-5.4-mini")
_MAI_SMART_MODEL  = os.environ.get("MAI_SMART_MODEL",  "gpt-5.5")
_MAI_API_BASE_URL = os.environ.get("MAI_API_BASE_URL", "")
_MAI_OAUTH_GUID   = os.environ.get("CONNECT_OAUTH_INTEGRATION_GUID", "00000000-0000-0000-0000-000000000000")  # Placeholder GUID for Posit OAuth integration

# Map Anthropic model names → MAI API (OpenAI) model IDs
_MAI_MODEL_MAP = {
    ANTHROPIC_CHAT_MODEL:                _MAI_FAST_MODEL,
    ANTHROPIC_REASONING_MODEL:           _MAI_SMART_MODEL,
    ANTHROPIC_PAD_PREPROCESSING_MODEL:   _MAI_FAST_MODEL,
    ANTHROPIC_PAD_STRESS_TEST_MODEL:     _MAI_FAST_MODEL,
    ANTHROPIC_IMPLEMENTATION_RISK_MODEL: _MAI_FAST_MODEL,
    ANTHROPIC_RISK_MAPPING_MODEL:        _MAI_FAST_MODEL,
    ANTHROPIC_FINAL_BRIEFING_MODEL:      _MAI_SMART_MODEL,
}


def _get_posit_azure_token():
    """Retrieve Azure AD access token via Posit Connect OAuth integration."""
    import requests as _requests
    connect_server = os.environ.get("CONNECT_SERVER", "").rstrip("/")
    connect_api_key = os.environ.get("CONNECT_API_KEY", "")
    session_token = os.environ.get("CONNECT_CONTENT_SESSION_TOKEN", "")
    guid = _MAI_OAUTH_GUID

    resp = _requests.post(
        f"{connect_server}/__api__/v1/oauth/integrations/credentials",
        headers={"Authorization": f"Key {connect_api_key}"},
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token_type": "urn:posit:connect:content-session-token",
            "subject_token": session_token,
            "audience": guid,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def get_client_for_model(model_name, internal=True):
    """
    Create a client for a specific model name.
    
    Args:
        model_name: Name of the model (e.g., 'claude-sonnet-4-6', 'gpt-5.2')
        internal: If True, use internal Azure infrastructure. If False, use Anthropic API.
    
    Returns:
        LangChain chat client configured for the specified model
    """
    if _IS_POSIT:
        from langchain_openai import AzureChatOpenAI
        # Map Anthropic model names to MAI API model IDs; OpenAI model names pass through as-is
        mai_model_id = _MAI_MODEL_MAP.get(model_name, model_name)
        return AzureChatOpenAI(
            azure_endpoint=_MAI_API_BASE_URL,
            azure_ad_token_provider=_get_posit_azure_token,
            api_version=OPENAI_CHAT_API_VERSION,
            deployment_name=mai_model_id,
            default_headers={
                "x-source-type": "interactive",
                "x-team-name": "fcv-briefings",
            },
        )

    if internal:
        try:
            from langchain_openai import AzureChatOpenAI
            from itsai.platform.authentication import DesktopToken
            
            token_class = DesktopToken()
            token_provider = lambda: token_class.token_provider(env="DEV")
            
            # Determine reasoning effort based on model name or use default
            reasoning_effort = 'high' if 'reasoning' in model_name.lower() else 'medium'
            
            return AzureChatOpenAI(
                azure_endpoint=_MAI_API_BASE_URL,
                azure_ad_token_provider=token_provider,
                api_version=OPENAI_CHAT_API_VERSION,
                deployment_name=model_name,
                reasoning_effort=reasoning_effort,
            )
            
        except ImportError as e:
            raise ImportError(
                f"Internal mode requires 'itsai' package. Install it or use internal=False.\nError: {e}"
            )
    
    else:
        # Use Anthropic via langchain (required for LangChain compatibility)
        from langchain_anthropic import ChatAnthropic
        
        # Get API key from environment variable
        anthropic_api_key = ANTHROPIC_API_KEY
        if not anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when internal=False. "
                "Set it in config.py or as an environment variable."
            )
        
        # Determine max_tokens based on model
        max_tokens = 20000 if 'sonnet' in model_name.lower() else 20000
        
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=anthropic_api_key,
            temperature=0,
            max_tokens=max_tokens
        )

def setup(internal=True):
    """
    Setup LLM clients.
    
    Args:
        internal: If True, use internal World Bank Azure infrastructure with itsai authentication.
                  If False, use generic Anthropic Claude client via API key.
    
    Returns:
        tuple: (standard_client, reasoning_client)
            - standard_client: Fast, lower-latency model for general tasks (Haiku for external, GPT for internal)
            - reasoning_client: Higher reasoning model for complex analysis (Sonnet for external, GPT for internal)
    """
    if internal:
        # Internal uses GPT-5.2 for both, but with different reasoning efforts
        standard_client = get_client_for_model(OPENAI_CHAT_MODEL, internal=True)
        reasoning_client = get_client_for_model(OPENAI_CHAT_MODEL, internal=True)
        # Note: Both use same model but get_client_for_model will set different reasoning_effort
    else:
        # External uses Haiku for speed and Sonnet for reasoning
        standard_client = get_client_for_model(ANTHROPIC_CHAT_MODEL, internal=False)
        reasoning_client = get_client_for_model(ANTHROPIC_REASONING_MODEL, internal=False)
    
    return standard_client, reasoning_client