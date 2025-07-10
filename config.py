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

    class Config:
        env_file=".env"
    


settings = Settings()
print()
