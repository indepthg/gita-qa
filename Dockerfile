FROM python:3.11-slim

# 1/5: base ok
RUN echo "1/5 base image ok"

# Set workdir
WORKDIR /app

# Copy requirements first to leverage build cache (if any)
COPY requirements.txt /app/
RUN echo "2/5 installing deps" && pip install --no-cache-dir -r requirements.txt -v
RUN echo "3/5 deps installed"

# Copy the rest of your app
COPY . /app
RUN echo "4/5 source copied"

# Start your app (adjust if you use uvicorn/flask/etc.)
# Example for your FastAPI-like app:
# CMD ["python", "main.py"]
# or if you use uvicorn:
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

CMD ["python", "main.py"]
