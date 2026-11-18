"""Geteilte Extension-Instanzen — `init_app(app)` ruft die Factory."""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.services.file_store import FileStore

db = SQLAlchemy()
migrate = Migrate()
file_store = FileStore()
