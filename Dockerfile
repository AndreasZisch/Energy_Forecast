# 1. Use Python 3.12 to match your local environment
# FROM python:3.12-slim
FROM python:3.12

# 2. Install essential build tools (often needed for XGBoost/SciPy)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /app

# 4. Copy and install requirements
COPY requirements_deployment.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements_deployment.txt

# 5. Copy the rest of your project
COPY . .

# 6. Expose ports
EXPOSE 8000
EXPOSE 8001
EXPOSE 8002

# 7. Default command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]