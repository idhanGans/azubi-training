"""Security headers for every response.

- HTML pages: Content-Security-Policy — scripts only from the own server (there are
  no inline scripts or onclick attributes), no embedding in other sites,
  no plugins. `style-src 'unsafe-inline'` only because of style attributes (bar widths).
  With the platform domain configured, the Dev-Desk recorder of `coding-platform.<domain>` may load and
  connect (loader `static/js/cp-devdesk.js`, it only activates in sandboxes or via the CP mode link) and the
  page may ask for the microphone (voice notes of the Dev-Desk).
- All responses: no MIME sniffing, no framing, short referrer.
- API: `Cache-Control: no-store` — personal data ends up in no intermediate cache.
- CSS/JS with `?v=<commit>` (that is how `base.html` links them): one year in the browser cache — a new
  deploy changes the URL. Without a matching version (or locally without GIT_COMMIT) revalidate as before.
Whatever a route sets itself (e.g. file downloads with their own CSP sandbox) stays untouched.
"""
from flask import request

def csp(domain):
    """Content-Security-Policy for HTML pages; `domain` = platform domain (Dev-Desk) or empty."""
    devdesk = f'https://coding-platform.{domain}' if domain else ''
    connect = f' {devdesk} wss://coding-platform.{domain}' if domain else ''
    return (f"default-src 'self'; script-src 'self'{' ' + devdesk if devdesk else ''}; style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; connect-src 'self'{connect}; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'")


def init_app(app):
    CSP = csp(app.config.get('PLATFORM_DOMAIN'))
    microphone = 'microphone=(self)' if app.config.get('PLATFORM_DOMAIN') else 'microphone=()'

    @app.after_request
    def _headers(response):
        headers = response.headers
        if response.mimetype == 'text/html':
            headers.setdefault('Content-Security-Policy', CSP)
        headers.setdefault('X-Content-Type-Options', 'nosniff')
        headers.setdefault('X-Frame-Options', 'DENY')
        headers.setdefault('Referrer-Policy', 'same-origin')
        headers.setdefault('Permissions-Policy', f'camera=(), {microphone}, geolocation=()')
        if request.path.startswith('/api/'):
            headers.setdefault('Cache-Control', 'no-store')
        elif request.endpoint == 'static' and response.status_code == 200 and _versioned(app):
            headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


def _versioned(app):
    version = app.config['ASSET_VERSION']
    return version != 'lokal' and request.args.get('v') == version
