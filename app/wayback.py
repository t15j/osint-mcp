"""Retrieve exact Internet Archive replay captures, without following redirects."""
import re
from datetime import datetime
from urllib.parse import quote
import httpx
from app.archive_html import TextExtractor

STAMP = re.compile(r'^\d{14}$')
MAX_BYTES = 100_000

def validate_stamp(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ValueError('timestamp must be YYYYMMDDhhmmss')
    try:
        datetime.strptime(value, '%Y%m%d%H%M%S')
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    return value

def fetch_snapshot(domain, timestamp, scheme='https', www=False):
    stamp = validate_stamp(timestamp)
    if scheme not in ('https', 'http') or type(www) is not bool:
        raise ValueError('Invalid scheme or www option')
    original = scheme + '://' + ('www.' if www else '') + domain + '/'
    url = 'https://web.archive.org/web/' + stamp + 'id_/' + original
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=4.0),
                      follow_redirects=False, trust_env=False,
                      headers={'Accept': 'text/html', 'User-Agent': 'OSINT-MCP-POC/0.1'}) as client:
        with client.stream('GET', url) as response:
            if response.is_redirect:
                raise ValueError('Wayback redirected; exact capture unavailable')
            response.raise_for_status()
            if 'text/html' not in response.headers.get('content-type', '').lower():
                raise ValueError('Archive response is not HTML')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('Archive response exceeds 100 KB')
                chunks.append(chunk)
    parser = TextExtractor()
    parser.feed(b''.join(chunks).decode('utf-8', errors='replace'))
    return {'requested_timestamp': stamp, 'original_url': original,
            'archive_url': url, **parser.result()}
