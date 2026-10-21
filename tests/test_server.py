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
