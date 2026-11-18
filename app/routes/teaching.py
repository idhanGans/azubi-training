"""Dozent: „Mein Unterricht" — Termine, Unterrichtszeit, offene Anwesenheit/Bewertungen, Kurse, Teilnehmer.
Die Zusammenstellung (Kennzahlen, Zeitfenster) steht in services/teaching.py."""
from flask import Blueprint, jsonify

from app import auth
from app.extensions import db
from app.models.instructor import Instructor
from app.services import teaching

bp = Blueprint('teaching', __name__, url_prefix='/api/my-teaching')


@bp.route('', methods=['GET'])
@auth.instructor_only
def overview():
    instructor = db.session.get(Instructor, auth.current_identity().instructor_id)
    return jsonify(teaching.overview(instructor))
