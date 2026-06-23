import os
import secrets
from dotenv import load_dotenv

# Load .env file (pastikan path benar di PythonAnywhere)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Generate secure SECRET_KEY jika tidak ada environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or ''

    
    # Configure MySQL Database (Replace 'root' and '' if you have a password)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///sqlite.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for Excel files
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    
    # Session Cookie Security
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'  # Hanya HTTPS di production
    SESSION_COOKIE_HTTPONLY = True  # Cookie tidak bisa diakses via JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Cegah CSRF
    PERMANENT_SESSION_LIFETIME = 3600  # Session kadaluarsa dalam 1 jam
    
    # CSRF Token Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # Token kadaluarsa dalam 1 jam