"""WSGI-Entry-Point — Gunicorn laedt `wsgi:app`."""
from app import create_app

app = create_app()
