from briefing_config import *
import os

def get_client_for_model(model_name, internal=True):
    """
    Create a client for a specific model name.
    
    Args:
        model_name: Name of the model (e.g., 'claude-sonnet-4-6', 'gpt-5.2')
        internal: If True, use internal Azure infrastructure. If False, use Anthropic API.
    
    Returns:
        LangChain chat client configured for the specified model
    """
    if internal:
        try:
            from langchain_openai import AzureChatOpenAI
            from itsai.platform.authentication import DesktopToken
            
            token_class = DesktopToken()
            token_provider = lambda: token_class.token_provider(env="DEV")
            
            # Determine reasoning effort based on model name or use default
            reasoning_effort = 'high' if 'reasoning' in model_name.lower() else 'medium'
            
            return AzureChatOpenAI(
                azure_endpoint="https://azapimdev.worldbank.org/conversationalai/v2",
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