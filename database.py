from sqlmodel import create_engine, SQLModel, Session
from config import settings

engine = create_engine(settings.DATABASE_URL)

def get_db():
    with Session(engine) as session:
        yield session

def create_all_db_tables():
    SQLModel.metadata.create_all(engine)