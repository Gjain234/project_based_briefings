from config import *
import os

def setup(internal=True):
    """
    Setup LLM client.
    
    Args:
        internal: If True, use internal World Bank Azure infrastructure with itsai authentication.
                  If False, use generic Anthropic Claude client via API key.
    
    Returns:
        LangChain-compatible LLM client
    """
    if internal:
        try:
            from langchain_openai import AzureChatOpenAI
            from itsai.platform.authentication import DesktopToken
            
            token_class = DesktopToken()
            token_provider = lambda: token_class.token_provider(env="DEV")
            
            client = AzureChatOpenAI(
                azure_endpoint="https://azapimdev.worldbank.org/conversationalai/v2",
                azure_ad_token_provider=token_provider,
                api_version=OPENAI_CHAT_API_VERSION,
                deployment_name=OPENAI_CHAT_MODEL,
                reasoning_effort='medium',
            )
            
            return client
            
        except ImportError as e:
            raise ImportError(
                f"Internal mode requires 'itsai' package. Install it or use internal=False.\nError: {e}"
            )
    
    else:
        try:
            from langchain_anthropic import ChatAnthropic
            
            # Get API key from environment variable
            anthropic_api_key = ANTHROPIC_API_KEY
            if not anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when internal=False. "
                    "Set it in config.py or as an environment variable."
                )
            
            # Create Claude client (compatible with LangChain's ChatPromptTemplate pattern)
            client = ChatAnthropic(
                model=ANTHROPIC_CHAT_MODEL,  # or use config.CHAT_MODEL if defined for external
                anthropic_api_key=anthropic_api_key,
                temperature=0,
                max_tokens=8192
            )
            
            return client
            
        except ImportError as e:
            raise ImportError(
                f"External mode requires 'langchain-anthropic' package. "
                f"Install it with: pip install langchain-anthropic\nError: {e}"
            )