import os


DOCUMENT_DF_PATH = "C:/Users/wb649538/projects/project_based_briefings/public_documents.csv"
OPENAI_CHAT_MODEL = "gpt-5.2"
ANTHROPIC_CHAT_MODEL = "claude-sonnet-4-6"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_CHAT_API_VERSION = "2025-01-01-preview"
EMBEDDINGS_MODEL = "text-embedding-3-small"
EMBEDDINGS_API_VERSION = "2024-10-01-preview"