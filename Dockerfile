FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY app/frontend/package*.json ./
RUN npm ci

COPY app/frontend/ ./
RUN npm run build

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

# Copy the built React app into the FastAPI app so Cloud Run serves the same UI
# users open at the service root.
COPY --from=frontend-build /frontend/build ./app/frontend/build/

# Start Uvicorn server on port 8080
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8080"]
