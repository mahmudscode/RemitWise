FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY start.sh .
RUN chmod +x start.sh
# Build time: generate data, train, evaluate (SQLite). Used when DATABASE_URL is not set.
RUN python -m app.pipeline  # also bakes the trained model and evaluation.json into the image
ENV PORT=8000
CMD ["./start.sh"]
