import os
import json
import google.auth.transport.requests
from google.oauth2 import service_account
from vertexai.preview import generative_models
import vertexai

# Import your settings if available
from config import settings  # assuming you already load this globally

# 1️⃣ Import required modules
from vertexai.language_models import TextEmbeddingModel

# 2️⃣ Load the embedding model (using the newer text-embedding-005 model)
model = TextEmbeddingModel.from_pretrained("text-embedding-005")

# 3️⃣ Generate embedding for a sample text
text = "Education is the most powerful weapon which you can use to change the world."
embeddings = model.get_embeddings([text])

# 4️⃣ Print results
print("✅ Embedding length:", len(embeddings[0].values))
print("🔢 Sample of embedding vector:", embeddings[0].values[:10])

# 1️⃣ Load service account credentials directly from settings
if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith("{"):
    # JSON content directly stored in environment/settings
    credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
else:
    # Path to a JSON file
    credentials = service_account.Credentials.from_service_account_file(
        settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
    )

# 2️⃣ Add the correct scopes for Vertex AI
scoped_credentials = credentials.with_scopes([
    "https://www.googleapis.com/auth/cloud-platform"
])

# 3️⃣ Initialize Vertex AI client with the credentials
vertexai.init(project=settings.GCS_PROJECT_ID, location="us-central1", credentials=scoped_credentials)

# 4️⃣ Test embedding generation using Gemini Embeddings
