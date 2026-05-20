# Use a slim official Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /carboncoach

ENV HF_HUB_DISABLE_XET=1
ENV HF_HOME=/carboncoach/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/carboncoach/.cache/sentence-transformers

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Cache the public embedding model at build time so Cloud Run cold starts do not
# depend on live Hugging Face downloads.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy the rest of your code
COPY app/ ./app/

# Start Uvicorn server on port 8080
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8080"]
