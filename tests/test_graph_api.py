"""Public graph transport and native scope fidelity, with no engine/provider use."""
import json
from pathlib import Path
import shutil
import threading
from http.client import HTTPConnection
from unittest.mock import patch

import pytest

from zenith.api import GraphAPI, create_server, openapi, validate_origins
from zenith import runtime
from zenith.cli import parser
from zenith.public_graph import SOURCE_AUTHORITIES, build

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def api():
    return GraphAPI(ROOT)


def payload(result):
    assert result.status == 200
    return json.loads(result.body)


def test_graph_and_each_mission_are_exact_native_projections(api):
    graph = build(ROOT)
    assert payload(api.get('/api/v1/graph')) == graph
    index = payload(api.get('/api/v1/missions'))
    assert index['missions'] == graph['missions']
    for mission in graph['missions']:
        view = payload(api.get('/api/v1/missions/' + mission['id']))
        scope = set(mission['node_ids'])
        assert view['mission'] == mission
        assert view['nodes'] == [n for n in graph['nodes'] if n['id'] in scope]
        assert view['edges'] == [e for e in graph['edges'] if e['source'] in scope and e['target'] in scope]
        assert view['counts'] == {'nodes': len(scope), 'edges': len(view['edges'])}
        assert view['provenance'] == graph['provenance']


def test_node_neighbors_follow_scope_and_preserve_injected_context_boundary(api):
    graph = build(ROOT)
    for mission in graph['missions']:
        scope = set(mission['node_ids'])
        for node_id in scope:
            view = payload(api.get(f'/api/v1/nodes/{node_id}?mission={mission["id"]}'))
            assert view['incoming'] == [e['source'] for e in graph['edges'] if e['target'] == node_id and e['source'] in scope]
            assert view['outgoing'] == [e['target'] for e in graph['edges'] if e['source'] == node_id and e['target'] in scope]
            assert view['mission'] == mission['id']
    view = payload(api.get('/api/v1/nodes/delta_analyzer'))
    assert view['incoming'] == []
    assert 'injected Oracle feedback' in view['additional_context']
    assert 'separate route' in view['additional_context']
    assert view['mission'] is None


@pytest.mark.parametrize('target,status,code', [
    ('/api/v1/nodes/missing', 404, 'unknown_node'),
    ('/api/v1/missions/missing', 404, 'unknown_mission'),
    ('/api/v1/nodes/oracle_cp2_emitter?mission=lab', 404, 'node_outside_mission'),
    ('/api/v1/nodes/lab_director?mission=', 400, 'invalid_query'),
    ('/api/v1/nodes/lab_director?mission=lab&mission=oracle', 400, 'invalid_query'),
    ('/api/v1/graph?root=/private', 400, 'invalid_query'),
    ('/api/v1/graph?mission=lab', 400, 'invalid_query'),
    ('/../../private.env', 404, 'unknown_route'),
    ('/api/v1/nodes/%2e%2e%2fprivate.env', 404, 'unknown_node'),
    ('/api/v1/nodes/%FF', 400, 'invalid_target'),
    ('https://example.test/api/v1/graph', 400, 'invalid_target'),
])
def test_bad_requests_fail_without_echoing_user_input(api, target, status, code):
    result = api.get(target)
    assert result.status == status
    body = json.loads(result.body)
    assert body['error']['code'] == code
    assert '/private' not in result.body.decode()


def test_server_builds_no_engine_or_runtime_state(tmp_path):
    shutil.copytree(ROOT / 'codex', tmp_path / 'codex')
    for name in SOURCE_AUTHORITIES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    with patch.object(runtime.GodModeEngine, '__init__', side_effect=AssertionError('no execution')):
        with create_server(tmp_path, port=0) as server:
            assert server.server_address[1] > 0
    assert not (tmp_path / 'state').exists()
    assert not (tmp_path / 'work').exists()


def test_http_json_head_cache_cors_and_write_rejection():
    server = create_server(ROOT, port=0, allow_origins=['http://localhost:5173'])
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def request(method, target='/api/v1/graph', headers=None):
        connection = HTTPConnection(*server.server_address, timeout=5)
        try:
            connection.request(method, target, headers=headers or {})
            result = connection.getresponse()
            return result.status, dict(result.getheaders()), result.read()
        finally:
            connection.close()

    try:
        status, headers, body = request('GET', headers={'Origin': 'http://localhost:5173'})
        assert status == 200
        assert json.loads(body)['counts'] == {'nodes': 71, 'edges': 205}
        assert headers['Content-Type'] == 'application/json; charset=utf-8'
        assert headers['Access-Control-Allow-Origin'] == 'http://localhost:5173'
        assert headers['X-Content-Type-Options'] == 'nosniff'
        status, cached, empty = request('GET', headers={'If-None-Match': 'W/' + headers['ETag']})
        assert status == 304 and empty == b'' and cached['ETag'] == headers['ETag']
        status, head, empty = request('HEAD')
        assert status == 200 and empty == b'' and int(head['Content-Length']) == len(body)
        assert 'Access-Control-Allow-Origin' not in head
        assert 'Access-Control-Allow-Origin' not in request('GET', headers={'Origin': 'https://other.test'})[1]
        status, allowed, empty = request('OPTIONS', headers={'Origin': 'http://localhost:5173'})
        assert status == 204 and empty == b''
        assert allowed['Access-Control-Allow-Methods'] == 'GET, HEAD, OPTIONS'
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            status, rejected, body = request(method)
            assert status == 405
            assert json.loads(body)['error']['code'] == 'read_only'
            assert rejected['Allow'] == 'GET, HEAD, OPTIONS'
        assert request('GET', '/')[0] == 404  # There is deliberately no frontend/file server.
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_openapi_routes_match_live_shapes_and_cli_defaults(api):
    spec = payload(api.get('/api/v1/openapi.json'))
    assert spec == openapi()
    assert spec['openapi'] == '3.1.0'
    cases = {'/api/v1/graph': '/api/v1/graph', '/api/v1/health': '/api/v1/health',
             '/api/v1/missions': '/api/v1/missions', '/api/v1/missions/{mission_id}': '/api/v1/missions/lab',
             '/api/v1/nodes/{node_id}': '/api/v1/nodes/lab_director'}
    # Validate real payloads against the published contract, including references.
    from jsonschema import Draft202012Validator
    for template, path in cases.items():
        schema = spec['paths'][template]['get']['responses']['200']['content']['application/json']['schema']
        Draft202012Validator({**schema, 'components': spec['components']}).validate(payload(api.get(path)))
    args = parser().parse_args(['serve'])
    assert (args.host, args.port, args.allow_origin) == ('127.0.0.1', 8765, [])


@pytest.mark.parametrize('origin', ['*', 'null', 'file:///tmp', 'http://user:pass@localhost:5173', 'http://localhost:5173/', 'http://localhost:5173?x=1', 'http://localhost:bad'])
def test_cors_requires_an_exact_origin(origin):
    with pytest.raises(ValueError):
        validate_origins([origin])
