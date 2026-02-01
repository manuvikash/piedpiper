from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Redis Cloud
    # Default uses your Redis Cloud instance (override in .env if needed)
    redis_url: str = "redis://default:gmdyd2O0VRi6bTfwPkiLB8laaEFAHOEb@redis-15166.c258.us-east-1-4.ec2.cloud.redislabs.com:15166"

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

    # W&B Weave
    wandb_api_key: str = ""
    weave_project_name: str = "focus-group-simulation"

    # Budget
    total_budget_usd: float = 50.00

    # App
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
