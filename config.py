"""Configuration from ENV. No secrets in code, no default for secrets."""
import os


class Config:
    # Postgres from the MSH shared resource — DATABASE_URL is injected by the handler
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    # pool_size is the BASE, not the upper limit: the QueuePool grows
    # lazily up to the observed concurrency and never shrinks back below it —
    # every service pays this base permanently into the SHARED Postgres.
    # The burst is carried by max_overflow (these connections are closed
    # after being returned). Hence 2 instead of 5; fleet default since ADR 0003
    # (main repo, infrastructure/decisions/0003-shared-pg-connection-pooling.md,
    # binding per .claude/rules/coding-standards.md). Whoever needs a bigger
    # base justifies it in the service — not here.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 2,
        'max_overflow': 10,
        'pool_recycle': 300,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MSH-injected auth URLs — only for fallback verification, normally
    # msh_base uses the Ed25519 public key offline.
    MSH_AUTH_URL = os.environ.get('MSH_AUTH_URL')
    MSH_LOGIN_URL = os.environ.get('MSH_LOGIN_URL')
    MSH_VERIFY_KEY_URL = os.environ.get('MSH_VERIFY_KEY_URL')
    # Logout: central logout from user-handling (deletes the auth_token cookie) next to /login.
    LOGOUT_URL = (MSH_LOGIN_URL[:-len('/login')] + '/logout') if (MSH_LOGIN_URL or '').endswith('/login') else None

    # Who is ALWAYS super admin (comma-separated MSH logins, from msh_config.json).
    # Further roles are granted by a super admin in user management (table
    # user_role) — the ENV is only the entry point so there is a super admin at all.
    SUPER_ADMINS = frozenset(
        u.strip().lower() for u in os.environ.get('SUPER_ADMINS', '').split(',') if u.strip()
    )

    # Storage for uploaded learning materials (persistent volume, msh_config.json).
    UPLOAD_DIR = os.environ['UPLOAD_DIR']
    # Largest allowed file; the request may be a bit larger (form fields).
    MAX_UPLOAD_BYTES = int(os.environ.get('MAX_UPLOAD_MB', '50')) * 1024 * 1024
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + 1024 * 1024

    # Platform domain (injected by MSH): the Dev-Desk loader in base.html and the CSP allow
    # coding-platform.<domain>; without it the loader stays out (local, tests).
    PLATFORM_DOMAIN = os.environ.get('MSH_PLATFORM_DOMAIN', '')

    # Cache busting for CSS/JS — the handler injects GIT_COMMIT.
    ASSET_VERSION = os.environ.get('GIT_COMMIT', 'lokal')[:12]

    # Auto-migration at app start (k3s pattern). Multi-replica: set to False
    # and run the migration in an InitContainer/job instead.
    MSH_AUTO_MIGRATE = os.environ.get('MSH_AUTO_MIGRATE', 'True') == 'True'
