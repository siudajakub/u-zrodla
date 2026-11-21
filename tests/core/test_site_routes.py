"""Exercise real slash-bearing capture IDs over HTTP with a private database."""
import json
from pathlib import Path
import socket
import threading
import time
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from analysis.engine import analyze
from api import server, store
import uvicorn


class SiteRoutes(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(store, 'STATE', Path(self.temp)))
        store.init()
        self.cap = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/validation/bossa-discovery-2026-11-21.json').read_text())['capture']
        self.simple = dict(self.cap, id='simple-id')
        with store.connection(True) as db:
            store.apply_scan(db, [(c, analyze(c)) for c in (self.cap, self.simple)], [], [], 'live')
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        sock.listen(128)
        self.enterContext(sock)
        self.base = 'http://127.0.0.1:' + str(sock.getsockname()[1])
        self.web = uvicorn.Server(uvicorn.Config(server.app, log_level='error', lifespan='off'))
        self.thread = threading.Thread(target=self.web.run, kwargs={'sockets': [sock]}, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.web.started:
                break
            time.sleep(.02)
        self.assertTrue(self.web.started)
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.web.should_exit = True
        self.thread.join(5)

    def request(self, method, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self.base + path, data=body, method=method, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_slash_id_full_flow_and_legacy(self):
        for key in (self.cap['id'], self.simple['id']):
            path = '/v1/cases/' + quote(key, safe='')
            status, finding = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertEqual(finding['registryStatus'], 'zgodność w stanie archiwalnym')
            status, version = self.request('GET', path + '/versions/1')
            self.assertEqual((status, version['capture']['url']), (200, self.cap['url']))
            status, updated = self.request('PATCH', path, {'status':'reviewing','expectedRevision':1,'note':'Sprawdzić stan zezwolenia.'})
            self.assertEqual((status, updated['revision']), (200, 2))
            self.assertEqual(self.request('PATCH', path, {'status':'closed','expectedRevision':1,'note':'Stara rewizja'})[0], 409)
            self.assertEqual(self.request('POST', path + '/inquiry', {'action':'draft','expectedRevision':2})[0], 422)
            self.assertEqual(self.request('POST', path + '/contract', {'endDate':'2026-11-21','label':'test','expectedRevision':2})[0], 422)

    def test_conflicting_identifier_does_not_attach_registry(self):
        cap = {**self.cap, 'identityEvidence': {**self.cap['identityEvidence'], 'krsCandidates':['0000048901','0000099999']}}
        found = analyze(cap)
        self.assertEqual(found['registryStatus'], 'do wyjaśnienia')
        self.assertNotIn('registry', found)
        self.assertFalse(any(e['kind'] == 'registry' for e in found['evidence']))
