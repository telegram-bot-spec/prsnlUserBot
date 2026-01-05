FROM python:3.10-slim

WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Expose port for web service
EXPOSE 10000

# Run with gunicorn
CMD ["python", "main.py"]
