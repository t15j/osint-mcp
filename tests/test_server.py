import pytest
from app import server

def test_domain_validation():
    assert server._domain('EXAMPLE.COM.') == 'example.com'
    for x in ('localhost', 'example.com/path', '127.0.0.1', 'foo.local', 'https://example.com'):
        with pytest.raises(ValueError): server._domain(x)

def test_global_only():
    assert server._ip('8.8.8.8') == '8.8.8.8'
    for x in ('127.0.0.1', '10.0.0.1', '192.168.1.1', '::1', '169.254.169.254'):
        with pytest.raises(ValueError): server._ip(x)

def test_cert_filter(monkeypatch):
    monkeypatch.setattr(server, '_get_json', lambda url: {
        'hosts': [
            {'host': '*.example.com'}, {'host': 'api.example.com'},
            {'host': 'badexample.com'}, {'host': 'other.net'}
        ], 'has_next': False})
    result = server.cert_transparency('example.com')
    assert result['observations']['dns_names'] == ['api.example.com', 'example.com']
    assert result['observations']['truncated'] is False


def test_enumerate_sources_and_scope(monkeypatch):
    monkeypatch.setattr(server, '_get_json', lambda url: {
        'hosts': [{'host': 'api.example.com'}, {'host': 'badexample.com'}],
        'has_next': False})
    monkeypatch.setattr(server, '_archive_cdx', lambda domain, subdomains: (
        [{'timestamp': '20200101000000', 'url': 'https://docs.example.com/'}], False))
    result = server.domain_enumerate('example.com')
    assert result['observations']['subdomains'] == ['api.example.com', 'docs.example.com']


def test_enumerate_partial_failure(monkeypatch):
    def broken(_url):
        raise ValueError('provider unavailable')
    monkeypatch.setattr(server, '_get_json', broken)
    monkeypatch.setattr(server, '_archive_cdx', lambda domain, subdomains: (
        [{'timestamp': '20200101000000', 'url': 'https://docs.example.com/'}], False))
    result = server.domain_enumerate('example.com')
    assert 'ctlogs.dev' in result['observations']['source_errors']
    assert result['observations']['subdomains'] == ['docs.example.com']


def test_history(monkeypatch):
    monkeypatch.setattr(server, '_archive_cdx', lambda domain, subdomains: (
        [{'timestamp': '20190101000000', 'url': 'https://example.com/'}], False))
    result = server.website_history('example.com')
    assert result['observations']['snapshots'][0]['timestamp'] == '20190101000000'


def test_internetdb_rejects_private_ip():
    fn = server.internetdb_lookup.fn if hasattr(server.internetdb_lookup, 'fn') else server.internetdb_lookup
    with pytest.raises(ValueError): fn('10.0.0.1')


def test_wayback_timestamp_validation():
    from app.wayback import validate_stamp
    assert validate_stamp('20010228123456') == '20010228123456'
    for invalid in ('20010230abcdef', '20261301120000', '20260101', '../etc/passwd'):
        with pytest.raises(ValueError):
            validate_stamp(invalid)


def test_archive_html_extraction():
    from app.archive_html import TextExtractor
    parser = TextExtractor()
    parser.feed('<html><head><title>Alt</title><script>ignore me</script></head>'
                '<body><h1>Willkommen</h1><a href="https://example.com/impressum">Impressum</a></body></html>')
    data = parser.result()
    assert data['title'] == 'Alt'
    assert 'Willkommen' in data['text']
    assert 'ignore me' not in data['text']
    assert data['links'] == ['https://example.com/impressum']


def test_website_diff(monkeypatch):
    from app import wayback
    def fake(domain, timestamp, scheme='https', www=False):
        return {'requested_timestamp': timestamp, 'archive_url': 'https://web.archive.org/test',
                'title': 'New' if timestamp.startswith('2025') else 'Old',
                'text': 'hello new' if timestamp.startswith('2025') else 'hello old',
                'text_truncated': False}
    monkeypatch.setattr(wayback, 'fetch_snapshot', fake)
    result = server.website_diff('example.com', '20200101000000', '20250101000000')
    assert 'new' in result['observations']['added_terms_sample']
    assert 'old' in result['observations']['removed_terms_sample']


def test_timeline_partial_failure(monkeypatch):
    from app import wayback
    def fake(domain, timestamp, scheme='https', www=False):
        if timestamp.startswith('2025'):
            raise ValueError('archive missing')
        return {'requested_timestamp': timestamp, 'archive_url': 'https://web.archive.org/test',
                'title': 'Old', 'text': 'Old content', 'text_truncated': False}
    monkeypatch.setattr(wayback, 'fetch_snapshot', fake)
    result = server.website_timeline('example.com', '20200101000000,20250101000000')
    assert len(result['observations']['snapshots']) == 1
    assert len(result['observations']['errors']) == 1
    assert result['observations']['complete'] is False


def test_screenshot_rejects_invalid_domain():
    with pytest.raises(ValueError):
        server.website_screenshot('127.0.0.1', '20010228110223')


def test_screenshot_rejects_invalid_timestamp():
    with pytest.raises(ValueError):
        server.website_screenshot('example.com', 'invalid')


def test_screenshot_rejects_invalid_scheme():
    with pytest.raises(ValueError):
        server.website_screenshot('example.com', '20010228110223', scheme='file')
