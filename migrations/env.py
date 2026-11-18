import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# ⚠️ `disable_existing_loggers=False` ist Pflicht, nicht Kosmetik (#11924).
# Der Default ist True: jeder Logger, der beim Aufruf schon existiert und nicht
# in der alembic.ini steht, wird auf `disabled = True` gesetzt und schweigt
# danach fuer die restliche Lebenszeit des Prozesses. Weil `_auto_migrate()`
# (app/__init__.py) `flask db upgrade` IN-PROCESS beim App-Start faehrt, traefe
# das genau die Logger, die vorher entstehen: `app` (= `app.logger`, also der
# Traceback jeder unbehandelten Exception) sowie `gunicorn.error` und
# `gunicorn.access` im Worker. Der Service liefert danach in Produktion weder
# Access-Logs noch Tracebacks — und `msh logs <slug>` sieht aus, als sei nie
# etwas passiert. Kinder-Logger retten das nicht: `Logger.disabled` wird nur im
# emittierenden Logger geprueft, nicht in den Vorfahren.
#
# ⚠️ Diese Zeile ist nur die ERSTE von zwei Stufen (#12226). Sie verhindert das
# ABSCHALTEN der Logger — nicht mehr. `fileConfig()` konfiguriert daneben IMMER
# auch den Root-Logger neu (setLevel + Handler ersetzen), und zwar auf den Wert
# aus `[logger_root]` der alembic.ini. Steht dort der alembic-Standard `WARN`,
# ueberschreibt das den `logging.basicConfig(level=INFO)` der App, und jede
# INFO-Zeile bleibt stumm — obwohl `disabled=False` ist. Deshalb steht in der
# alembic.ini dieser Vorlage `[logger_root] level = INFO`. Wer nur diese Zeile
# hier kopiert, bekommt Tracebacks und Access-Logs zurueck, aber weiterhin
# keine INFO-Betriebsbilanz (genau der Erbfall #12206).
fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger('alembic.env')


def get_engine():
    # Flask-SQLAlchemy 3.x: `db.engine` (das alte `get_engine()` faellt in 3.2 weg).
    return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
