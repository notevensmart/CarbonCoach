# Use a slim official Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /carboncoach

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY app/ ./app/

# Start Uvicorn server on port 8080
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8080"]