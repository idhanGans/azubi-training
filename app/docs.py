"""Blueprints + /docs registry. The doc entries live next to their routes
(list `DOCS`; for large modules in a `*_docs.py` beside them).

`tests/test_docs.py` checks the registry against the routing table — if a
route is missing (or one too many is listed), the test turns red.
"""
from app.routes import (activity, assessment_docs, assessment_templates, assessments, attendance, candidates,
                        candidates_docs, catalogs, courses, curriculum, curriculum_docs, dashboard, departments,
                        instructors, lesson_ratings, materials, me, modules, my_training, notifications, overall, pages,
                        portal, progress, report_views, reports, sessions, staff_docs, teaching, trainees, users)

BLUEPRINT_MODULES = (pages, me, my_training, notifications, dashboard, candidates, catalogs, curriculum, modules,
                     materials, instructors, courses, sessions, attendance, lesson_ratings, assessment_templates,
                     assessments, progress, portal, teaching, trainees, reports, report_views, overall, departments,
                     users, activity)

_DOC_SOURCES = (pages, me, my_training, notifications, dashboard, candidates_docs, catalogs, curriculum_docs,
                staff_docs, attendance, lesson_ratings, assessment_docs, progress, portal, trainees, reports,
                report_views, overall, departments, users, activity)

DOCS_ENDPOINTS = [entry for module in _DOC_SOURCES for entry in module.DOCS]
