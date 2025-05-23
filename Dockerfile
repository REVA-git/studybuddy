FROM python:3.12-slim

# Set environment variable to allow print statements to be displayed immediately
ENV PYTHONUNBUFFERED=1

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


# Expose the port the app runs on
EXPOSE 8000

# Command to run the app
CMD ["sh", "-c", "uv run granian --interface asgi asgi.py --host 0.0.0.0 --port 8000"]

