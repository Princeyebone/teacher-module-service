from pydantic_settings import BaseSettings
import secrets

class Settings(BaseSettings):
    APP_NAME:str = "keep"
    APP_VERSION:str = "This"
    DATABASE_URL:str = "a"
    CORE_SERVICE_URL:str = "Secret"
    SERVICE_JWT:str= "from"
    SECRET_KEY:str= "n"
    ALGORITHM:str= "like"
    ACCESS_TOKEN_EXPIRE_MINUTES:int= 0
    REFRESH_TOKEN_EXPIRE_MINUTES:int= 0
    API_KEY:str = "your_google_genai_api_key_here"  # Add your Google Gen AI API key to .env file
    
    # Google Cloud Storage settings
    GCS_BUCKET_NAME: str = "your-gcs-bucket-name"
    GCS_PROJECT_ID: str = "your-gcp-project-id"
    GCS_SERVICE_ACCOUNT_JSON: str = "g"  # Path to service account JSON file or JSON content
    GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI: str = "Google_GenAI_Service_Account"  # Path to service account JSON file or JSON content
    
    # Google Gemini API key for timetable processing
    GEMINI_API_KEY: str = ""  # Add your Google Gemini API key to .env file
    
    # Poppler path for PDF processing (optional, if not in system PATH)
    POPPLER_PATH: str = ""  # e.g., "C:/poppler/Library/bin" on Windows
    
    CELERY_BROKER_URL:str = "h"
    CELERY_RESULT_BACKEND:str = "a"

    class Config:
        env_file=".env"


settings = Settings()
print()