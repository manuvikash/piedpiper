from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # W&B Inference (OpenAI-compatible API for all LLM calls)
    wandb_api_key: str = ""
    wandb_base_url: str = "https://api.inference.wandb.ai/v1"
    wandb_project: str = "focus-group-simulation"

    # Embeddings (local sentence-transformers, no external API needed)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # Redis Cloud
    # Set REDIS_URL in .env file (see .env.example)
    redis_url: str = "redis://localhost:6379"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://piedpiper:piedpiper@localhost:5432/piedpiper"
    learning_database_url: str = (
        "postgresql+asyncpg://piedpiper:piedpiper@localhost:5432/piedpiper_learning"
    )

    # Daytona
    daytona_api_key: str = ""
    daytona_base_url: str = ""

    # Browserbase
    browserbase_api_key: str = ""
    browserbase_project_id: str = ""

    # Budget
    total_budget_usd: float = 50.00

    # App
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ["../.env", ".env"], "env_file_encoding": "utf-8"}


settings = Settings()
