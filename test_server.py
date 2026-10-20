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
    monkeypatch.setattr(server, '_get_json', lambda url: [
        {'name_value':'*.example.com\napi.example.com\nother.net'},
        {'name_value':'EXAMPLE.COM'}])
    fn = server.cert_transparency.fn if hasattr(server.cert_transparency, 'fn') else server.cert_transparency
    result = fn('example.com')
    assert result['observations']['dns_names'] == ['api.example.com', 'example.com']

def test_internetdb_rejects_private_ip():
    fn = server.internetdb_lookup.fn if hasattr(server.internetdb_lookup, 'fn') else server.internetdb_lookup
    with pytest.raises(ValueError): fn('10.0.0.1')
