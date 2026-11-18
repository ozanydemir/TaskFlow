"""Supabase client checks against a fake HTTP backend. No network or real project is used."""
import io
import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path

from supabase_sync import SupabaseAuthError, SupabaseClient, SupabaseError
from task_manager import TaskManager
from task_sync import MemoryServer, SyncEngine

URL = 'https://demo-project.supabase.co'
KEY = 'sb_publishable_demo'


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeSupabase:
    """Routes RPC calls to MemoryServer and issues numbered sessions for one demo user."""

    def __init__(self):
        self.server = MemoryServer()
        self.requests = []
        self.issued = 0
        self.valid = set()
        self.reject_next_rpc = False

    def session(self):
        self.issued += 1
        token = 'access-{}'.format(self.issued)
        self.valid.add(token)
        return {'access_token': token, 'refresh_token': 'refresh-{}'.format(self.issued), 'expires_in': 3600}

    def __call__(self, request, timeout):
        body = json.loads(request.data)
        headers = {k.lower(): v for k, v in request.header_items()}
        self.requests.append((request.full_url, headers, body))
        assert request.full_url.startswith(URL) and headers['apikey'] == KEY and timeout
        path = request.full_url[len(URL):]
        if path == '/auth/v1/otp':
            return FakeResponse(b'{}')
        if path == '/auth/v1/verify':
            if body['token'] != '123456':
                raise self.error(403, {'msg': 'Token has expired or is invalid'})
            return FakeResponse(json.dumps(self.session()).encode())
        if path == '/auth/v1/token?grant_type=refresh_token':
            if body['refresh_token'] != 'refresh-{}'.format(self.issued):
                raise self.error(400, {'error_description': 'Invalid Refresh Token'})
            return FakeResponse(json.dumps(self.session()).encode())
        token = headers.get('authorization', '').removeprefix('Bearer ')
        if self.reject_next_rpc or token not in self.valid:
            self.reject_next_rpc = False
            raise self.error(401, {'message': 'JWT expired'})
        name = path.removeprefix('/rest/v1/rpc/')
        if name == 'taskflow_pull':
            result = self.server.pull(body['p_cursor'])
        elif name == 'taskflow_push_many':
            result = self.server.push_many(body['p_items'])
        elif name == 'taskflow_push_events':
            self.server.push_events(body['p_events'])
            return FakeResponse(b'')
        else:
            raise self.error(404, {'message': 'Could not find the function'})
        return FakeResponse(json.dumps(result).encode())

    def error(self, status, payload):
        return urllib.error.HTTPError(URL, status, 'error', {}, io.BytesIO(json.dumps(payload).encode()))


class TestSupabaseClient(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.backend = FakeSupabase()
        self.saved = []

    def tearDown(self):
        self.temp.cleanup()

    def client(self, session=None):
        return SupabaseClient(URL + '/', KEY, session=session, on_session=self.saved.append, opener=self.backend)

    def signed_in(self):
        client = self.client()
        client.request_code(' demo@example.test ')
        client.verify_code('demo@example.test', ' 123456 ')
        return client

    def test_rejects_insecure_url_and_secret_keys(self):
        with self.assertRaises(ValueError):
            SupabaseClient('http://demo-project.supabase.co', KEY)
        with self.assertRaises(ValueError):
            SupabaseClient(URL, 'sb_secret_demo')

    def test_email_code_sign_in_stores_session_without_bearer_on_auth_calls(self):
        client = self.signed_in()
        otp, verify = self.backend.requests
        self.assertEqual(otp[2], {'email': 'demo@example.test', 'create_user': True})
        self.assertEqual(verify[2], {'type': 'email', 'email': 'demo@example.test', 'token': '123456'})
        self.assertTrue(all('authorization' not in headers for _, headers, _ in self.backend.requests))
        self.assertEqual(self.saved[-1]['refresh_token'], 'refresh-1')
        self.assertEqual(client.session['access_token'], 'access-1')

    def test_wrong_code_is_an_auth_error_with_message(self):
        client = self.client()
        with self.assertRaises(SupabaseAuthError) as raised:
            client.verify_code('demo@example.test', '000000')
        self.assertIn('invalid', str(raised.exception))
        self.assertIsNone(client.session)

    def test_expired_or_revoked_tokens_refresh_once(self):
        client = self.signed_in()
        client.session['expires_at'] = time.time() - 1
        client.pull(0)
        self.assertEqual(client.session['access_token'], 'access-2')
        self.backend.reject_next_rpc = True
        client.pull(0)
        self.assertEqual(client.session['access_token'], 'access-3')
        self.assertEqual([s['refresh_token'] for s in self.saved], ['refresh-1', 'refresh-2', 'refresh-3'])
        rpc = [h for url, h, _ in self.backend.requests if '/rest/v1/rpc/' in url]
        self.assertTrue(all(h['authorization'].startswith('Bearer access-') for h in rpc))

    def test_restored_session_refreshes_without_access_token(self):
        client = self.client({'refresh_token': 'refresh-0'})
        self.backend.issued = 0
        client.pull(0)
        self.assertEqual(client.session['access_token'], 'access-1')

    def test_missing_session_and_server_errors_raise(self):
        with self.assertRaises(SupabaseAuthError):
            self.client().pull(0)
        client = self.signed_in()
        with self.assertRaises(SupabaseError) as raised:
            client._rpc('taskflow_missing', {})
        self.assertEqual(raised.exception.status, 404)

    def test_two_stores_sync_through_the_client(self):
        client = self.signed_in()
        a = TaskManager(self.root / 'a' / 'data.sqlite3')
        b = TaskManager(self.root / 'b' / 'data.sqlite3')
        sync_a, sync_b = SyncEngine(a, client), SyncEngine(b, client)
        task = a.add_task('Bulut görevi', 'Demo')
        a.toggle_task(task['id'])
        sync_a.sync()
        sync_b.sync()
        self.assertEqual([t['title'] for t in b.tasks], ['Bulut görevi'])
        self.assertTrue(b.tasks[0]['completed'])
        self.assertEqual([e['kind'] for e in b.get_history('Demo')], ['manual_completion'])
        names = {url.rsplit('/', 1)[1] for url, _, _ in self.backend.requests if '/rest/v1/rpc/' in url}
        self.assertEqual(names, {'taskflow_pull', 'taskflow_push_many', 'taskflow_push_events'})


if __name__ == '__main__':
    unittest.main()
