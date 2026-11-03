
from app.database import Base, engine
from app.models.order import Order


def create_database_tables():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
