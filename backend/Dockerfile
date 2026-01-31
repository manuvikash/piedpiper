FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "piedpiper.main:app", "--host", "0.0.0.0", "--port", "8000"]
