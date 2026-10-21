"""Restricted screenshot worker for Internet Archive captures only."""
import base64
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

DOMAIN = re.compile(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$')
STAMP = re.compile(r'^\d{14}$')

def capture(req):
    domain, stamp = req.get('domain'), req.get('timestamp')
    if not isinstance(domain, str) or not DOMAIN.fullmatch(domain):
        raise ValueError('Invalid domain')
    if not isinstance(stamp, str) or not STAMP.fullmatch(stamp):
        raise ValueError('Invalid timestamp')
    if req.get('scheme', 'https') not in ('http', 'https') or type(req.get('www', False)) is not bool:
        raise ValueError('Invalid URL options')
    original = req.get('scheme', 'https') + '://' + ('www.' if req.get('www', False) else '') + domain + '/'
    archive = 'https://web.archive.org/web/' + stamp + '/' + original
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        try:
            context = browser.new_context(viewport={'width': 1200, 'height': 800}, device_scale_factor=1,
                                          java_script_enabled=False, service_workers='block')
            page = context.new_page()
            def restrict(route):
                u = urlsplit(route.request.url)
                if u.scheme == 'https' and u.hostname == 'web.archive.org':
                    route.continue_()
                else:
                    route.abort()
            page.route('**/*', restrict)
            response = page.goto(archive, wait_until='domcontentloaded', timeout=18000)
            page.wait_for_timeout(1500)
            if not response or response.status >= 400:
                raise ValueError('Archive returned an unsuccessful response')
            current = urlsplit(page.url)
            if current.hostname != 'web.archive.org' or '/web/' not in current.path:
                raise ValueError('Unexpected archive navigation')
            data = page.screenshot(type='png', full_page=False, timeout=8000)
            if len(data) > 1_000_000:
                raise ValueError('Screenshot exceeds 1 MB')
            return {'archive_url': page.url, 'requested_url': archive,
                    'width': 1200, 'height': 800, 'mime_type': 'image/png',
                    'png_base64': base64.b64encode(data).decode('ascii'),
                    'note': 'Archived external resources may be missing; JavaScript is disabled.'}
        finally:
            browser.close()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/capture':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError('Invalid request size')
            req = json.loads(self.rfile.read(length))
            result = capture(req)
            status = 200
        except Exception as exc:
            result = {'error': type(exc).__name__, 'detail': str(exc)[:160]}
            status = 422
        payload = json.dumps(result).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

ThreadingHTTPServer(('0.0.0.0', 8765), Handler).serve_forever()
