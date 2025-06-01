# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

COPY . .

# Stage 2: Final minimal image
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local/
COPY --from=builder /app /app

EXPOSE 5051

CMD ["gunicorn", "-b", "0.0.0.0:5051", "main:app"]
