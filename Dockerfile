FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY ./src /app
# Copy the application into the container.
COPY ./pyproject.toml /app/pyproject.toml
COPY ./uv.lock /app/uv.lock


# Install the application dependencies.
WORKDIR /app
# Install the application dependencies.
RUN uv sync --frozen --no-cache

