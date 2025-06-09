from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME:str = "keep"
    APP_VERSION:str = "This"
    DATABASE_URL:str = "a"
    CORE_SERVICE_URL:str = "Secret"
    SERVICE_JWT:str = "from"

    class Config:
        env_file=".env"
    
settings = Settings()
print(settings)
