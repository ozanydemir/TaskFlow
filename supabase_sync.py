"""Supabase transport and email-code sign-in for TaskFlow sync. Standard library only.

The client implements the SyncEngine server contract through the functions in
supabase/taskflow_schema.sql. Only the project URL and the publishable key are needed;
a secret or service_role key must never be used here.
"""
import argparse
import json
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class SupabaseError(OSError):
    def __init__(self, status, message):
        super().__init__('Supabase {}: {}'.format(status, message))
        self.status = status


class SupabaseAuthError(SupabaseError):
    """The session is missing or was rejected; the user must sign in again."""


class SupabaseClient:
    TIMEOUT = 20

    def __init__(self, url, publishable_key, session=None, on_session=None, opener=None):
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError('Supabase proje adresi https:// ile başlamalı.')
        if not publishable_key.strip() or publishable_key.strip().startswith('sb_secret_'):
            raise ValueError('Yalnızca Supabase publishable (herkese açık) anahtarı kullanılabilir.')
        self.url = '{}://{}'.format(parsed.scheme, parsed.netloc)
        self.key = publishable_key.strip()
        self.session = session
        self.on_session = on_session
        self.opener = opener or urllib.request.urlopen

    # HTTP

    def _request(self, path, body, token=None):
        headers = {'apikey': self.key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode('utf-8'),
                                         headers=headers, method='POST')
        try:
            with self.opener(request, timeout=self.TIMEOUT) as response:
                content = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')
            try:
                payload = json.loads(detail)
                detail = payload.get('msg') or payload.get('message') or payload.get('error_description') or detail
            except (ValueError, AttributeError):
                pass
            error = SupabaseAuthError if exc.code in (401, 403) else SupabaseError
            raise error(exc.code, detail) from None
        return json.loads(content) if content.strip() else None

    # Sign-in

    def request_code(self, email):
        self._request('/auth/v1/otp', {'email': email.strip(), 'create_user': True})

    def verify_code(self, email, code):
        self._store(self._request('/auth/v1/verify', {'type': 'email', 'email': email.strip(), 'token': code.strip()}))

    def refresh(self):
        if not self.session or not self.session.get('refresh_token'):
            raise SupabaseAuthError(401, 'Oturum yok; yeniden giriş yapın.')
        self._store(self._request('/auth/v1/token?grant_type=refresh_token',
                                  {'refresh_token': self.session['refresh_token']}))

    def _store(self, response):
        if not response or not response.get('access_token') or not response.get('refresh_token'):
            raise SupabaseAuthError(401, 'Supabase oturum bilgisi döndürmedi.')
        expires_at = response.get('expires_at') or time.time() + int(response.get('expires_in', 3600))
        self.session = {'access_token': response['access_token'], 'refresh_token': response['refresh_token'],
                        'expires_at': int(expires_at)}
        if self.on_session:
            self.on_session(dict(self.session))

    def _token(self):
        if not self.session:
            raise SupabaseAuthError(401, 'Oturum yok; yeniden giriş yapın.')
        if not self.session.get('access_token') or self.session.get('expires_at', 0) - 60 < time.time():
            self.refresh()
        return self.session['access_token']

    def _rpc(self, name, args):
        try:
            return self._request('/rest/v1/rpc/' + name, args, self._token())
        except SupabaseAuthError:
            # An access token can be revoked before it expires; refresh once and retry.
            self.refresh()
            return self._request('/rest/v1/rpc/' + name, args, self._token())

    # SyncEngine server contract

    def pull(self, cursor):
        return self._rpc('taskflow_pull', {'p_cursor': cursor})

    def push_many(self, items):
        return self._rpc('taskflow_push_many', {'p_items': items})

    def push_events(self, events):
        self._rpc('taskflow_push_events', {'p_events': events})


def _check(args):
    """Round trip through the real project with two disposable stores; test records end deleted."""
    from task_manager import TaskManager
    from task_sync import SyncEngine

    client = SupabaseClient(args.url, args.key)
    client.request_code(args.email)
    client.verify_code(args.email, input('E-postadaki 6 haneli kod: '))
    project = 'TaskFlow senkron testi'
    with tempfile.TemporaryDirectory() as directory:
        a = TaskManager(Path(directory) / 'a' / 'data.sqlite3')
        b = TaskManager(Path(directory) / 'b' / 'data.sqlite3')
        sync_a, sync_b = SyncEngine(a, client), SyncEngine(b, client)
        sync_a.sync()
        sync_b.sync()
        task = a.add_task('Senkron deneme görevi', project)
        sync_a.sync()
        sync_b.sync()
        copy = next(t for t in b.tasks if t['id'] == task['id'])
        b.edit_notes(copy['id'], 'B cihazından not')
        a.edit_task(task['id'], 'Senkron deneme görevi (A)')
        for _ in range(2):
            sync_b.sync()
            sync_a.sync()
        merged = next(t for t in a.tasks if t['id'] == task['id'])
        assert merged['notes'] == 'B cihazından not' and merged['title'].endswith('(A)'), merged
        a.delete_task(task['id'])
        a.delete_project(project)
        sync_a.sync()
        sync_b.sync()
        assert all(t['id'] != task['id'] for t in b.tasks) and project not in b.projects
    print('Supabase senkron denemesi başarılı: gönderme, alma, birleştirme ve silme çalıştı.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='TaskFlow Supabase sync check')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Sign in by email code and run a disposable two-store round trip')
    check.add_argument('--url', required=True, help='https://<project>.supabase.co')
    check.add_argument('--key', required=True, help='Publishable key (sb_publishable_...)')
    check.add_argument('--email', required=True)
    args = parser.parse_args(argv)
    try:
        _check(args)
    except (SupabaseError, ValueError, AssertionError) as exc:
        print('Supabase senkron denemesi başarısız: {}'.format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
