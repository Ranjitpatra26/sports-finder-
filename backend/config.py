import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret")
    
    # MongoDB Atlas connection URI
    # Set environment variable MONGO_URI or place your full Atlas connection string here:
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb+srv://mwarandekar_db_user:d6WvtsaMFD1Pvfly@cluster0.2ff9hoo.mongodb.net/sports_platform?retryWrites=true&w=majority&appName=Cluster0"
    )
    
    # SQL Fallback URI
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///sports_platform.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
