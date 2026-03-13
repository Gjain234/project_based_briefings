import os


def get_document_df_path(internal=True):
    """
    Get the path to the document dataframe based on internal/external usage.
    
    Args:
        internal: If True, use public_documents_filtered.csv (World Bank internal)
                 If False, use joined_df_filtered.csv (external users)
    
    Returns:
        Path to the appropriate CSV file
    """
    if not internal:
        return "./public_documents_filtered.csv"
    else:
        return "./joined_df_filtered.csv"

# Model configurations
OPENAI_CHAT_MODEL = "gpt-5.2"
ANTHROPIC_CHAT_MODEL = "claude-haiku-4-5"  # Fast model for general tasks
ANTHROPIC_REASONING_MODEL = "claude-sonnet-4-6"  # Reasoning model for complex tasks

# Task-specific model assignments (external mode only - internal uses OPENAI_CHAT_MODEL for all)
ANTHROPIC_COUNTRY_RISK_MODEL = "claude-sonnet-4-6"  # Country risk extraction with web search (complex)
ANTHROPIC_PAD_PREPROCESSING_MODEL = "claude-haiku-4-5"  # PAD preprocessing (faster extraction)
ANTHROPIC_PAD_STRESS_TEST_MODEL = "claude-haiku-4-5"  # PAD stress testing (simple matching)
ANTHROPIC_IMPLEMENTATION_RISK_MODEL = "claude-haiku-4-5"  # Implementation risk extraction (straightforward)
ANTHROPIC_RISK_MAPPING_MODEL = "claude-haiku-4-5"  # Risk mapping (simple matching)
ANTHROPIC_FINAL_BRIEFING_MODEL = "claude-sonnet-4-6"  # Final briefing synthesis (complex)

ANTHROPIC_RISK_BRIEFING_MODEL = "claude-haiku-4-5"  # Model for legacy risk scan

# Final briefing context management
MAX_BRIEFING_INPUT_LENGTH = 200000  # Maximum total characters for final briefing input
MAX_PROJECTS_FOR_BRIEFING = 15  # Maximum number of projects to include in final briefing (prioritized by risk count)
# API configurations
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_CHAT_API_VERSION = "2025-01-01-preview"
EMBEDDINGS_MODEL = "text-embedding-3-small"
EMBEDDINGS_API_VERSION = "2024-10-01-preview"