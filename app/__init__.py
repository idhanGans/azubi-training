"""App factory: bind extensions, register auth + blueprints, migrate.

No business logic here — routes in routes/, rules in services/,
access check (Zugriffspruefung) centrally in auth.py.
"""
import logging

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from msh_base import create_health_blueprint

from app import auth, errors, navigation, security
from app.docs import BLUEPRINT_MODULES, DOCS_ENDPOINTS
from app.extensions import db, file_store, migrate
from app.services import local_time

__all__ = ['create_app', 'DOCS_ENDPOINTS']


def create_app(config_object='config.Config'):
    app = Flask(__name__)
    # Behind the MSH ingress (Traefik, TLS terminates there): take scheme/host from
    # X-Forwarded-Proto/-Host so self-built URLs (e.g. logout redirect) are https:// too.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.from_object(config_object)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    db.init_app(app)
    migrate.init_app(app, db)
    file_store.init_app(app)
    auth.init_app(app)
    security.init_app(app)
    for module in BLUEPRINT_MODULES:
        app.register_blueprint(module.bp)
    app.register_blueprint(create_health_blueprint(
        description='azubi-training — Trainings-Monitoring und Sprachkurs-Verwaltung der Azubi-Kandidaten',
        endpoints=DOCS_ENDPOINTS, db=db))

    app.context_processor(navigation.template_context)
    app.context_processor(lambda: {'platform_domain': app.config.get('PLATFORM_DOMAIN')})   # Dev-Desk loader
    app.jinja_env.globals['asset_version'] = app.config['ASSET_VERSION']
    app.jinja_env.globals['tz_name'] = local_time.TZ_NAME       # display timezone for core.js
    app.jinja_env.globals['tz_label'] = local_time.tz_label     # short name for hint texts ("WIB")

    errors.register(app)

    if app.config.get('MSH_AUTO_MIGRATE'):
        from app.startup import auto_migrate
        auto_migrate(app)
    return app
