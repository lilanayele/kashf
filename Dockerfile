FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . && kashf generate --seed 7 --out /app/data/demo
EXPOSE 8800
CMD ["python", "-c", "import uvicorn; from kashf.api import create_app; uvicorn.run(create_app('/app/data/demo'), host='0.0.0.0', port=8800)"]
