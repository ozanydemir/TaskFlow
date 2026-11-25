"""Optional cloud sync for the desktop app and the agent bridge.

The Supabase address, publishable key and email live in this device's settings table,
which never syncs. The session (refresh token) lives in Windows Credential Manager,
never in the database or the repository. One sync runs at a time per store, across the
app and the bridge, so a rotated refresh token is never reused by a stale process.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import time
import urllib.parse
from contextlib import contextmanager
from pathlib import Path

from supabase_sync import SupabaseAuthError, SupabaseClient
from task_manager import TaskManager
from task_sync import SyncEngine

SETTING = 'cloud_sync'
BACKUP_SUFFIX = '.pre-sync.bak'


class MemoryCredentials:
    """In-process store for tests and non-Windows runs."""

    def __init__(self):
        self.values = {}

    def read(self, target):
        return self.values.get(target)

    def write(self, target, value):
        self.values[target] = value

    def delete(self, target):
        self.values.pop(target, None)


class WindowsCredentials:
    """Generic credentials of the current Windows user (Credential Manager)."""
    TYPE_GENERIC = 1
    PERSIST_LOCAL_MACHINE = 2
    NOT_FOUND = 1168
    MAX_BLOB = 2560

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR),
                        ('Comment', wintypes.LPWSTR), ('LastWritten', wintypes.FILETIME),
                        ('CredentialBlobSize', wintypes.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
                        ('Persist', wintypes.DWORD), ('AttributeCount', wintypes.DWORD),
                        ('Attributes', ctypes.c_void_p), ('TargetAlias', wintypes.LPWSTR),
                        ('UserName', wintypes.LPWSTR)]

        self.ctypes = ctypes
        self.CREDENTIAL = CREDENTIAL
        self.api = ctypes.WinDLL('advapi32', use_last_error=True)
        self.api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        self.api.CredReadW.restype = wintypes.BOOL
        self.api.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
        self.api.CredWriteW.restype = wintypes.BOOL
        self.api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.api.CredDeleteW.restype = wintypes.BOOL
        self.api.CredFree.argtypes = [ctypes.c_void_p]

    def _fail(self, action):
        code = self.ctypes.get_last_error()
        raise OSError(code, 'Windows Kimlik Bilgisi Yöneticisi {} başarısız ({}).'.format(action, code))

    def read(self, target):
        pointer = self.ctypes.POINTER(self.CREDENTIAL)()
        if not self.api.CredReadW(target, self.TYPE_GENERIC, 0, self.ctypes.byref(pointer)):
            if self.ctypes.get_last_error() == self.NOT_FOUND:
                return None
            self._fail('okuma')
        try:
            cred = pointer.contents
            return self.ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode('utf-8')
        finally:
            self.api.CredFree(pointer)

    def write(self, target, value):
        data = value.encode('utf-8')
        if len(data) > self.MAX_BLOB:
            raise ValueError('Oturum bilgisi Kimlik Bilgisi Yöneticisi için fazla büyük.')
        blob = (self.ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        cred = self.CREDENTIAL(Type=self.TYPE_GENERIC, TargetName=target, CredentialBlobSize=len(data),
                               CredentialBlob=blob, Persist=self.PERSIST_LOCAL_MACHINE, UserName='TaskFlow')
        if not self.api.CredWriteW(self.ctypes.byref(cred), 0):
            self._fail('yazma')

    def delete(self, target):
        if not self.api.CredDeleteW(target, self.TYPE_GENERIC, 0) and self.ctypes.get_last_error() != self.NOT_FOUND:
            self._fail('silme')


def default_credentials():
    return WindowsCredentials() if os.name == 'nt' else MemoryCredentials()


def get_config(manager):
    config = manager.settings.get(SETTING)
    return config if isinstance(config, dict) and config.get('url') and config.get('key') else None


def change_counter(db_file):
    """The store's change counter, read fresh; it moves on every write by any process."""
    conn = sqlite3.connect(db_file, timeout=5)
    try:
        return int(conn.execute("SELECT value FROM meta WHERE key='change'").fetchone()[0])
    finally:
        conn.close()


def credential_target(config):
    return 'TaskFlow Supabase ' + urllib.parse.urlparse(config['url']).netloc


@contextmanager
def store_lock(db_file, timeout=30):
    """Serialize syncs of one store across processes (desktop app and bridge)."""
    path = Path(db_file).with_name(Path(db_file).name + '.sync.lock')
    handle = open(path, 'a+b')
    deadline = time.time() + timeout
    try:
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError('Başka bir TaskFlow işlemi şu anda eşitliyor.')
                time.sleep(0.2)
        try:
            yield
        finally:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def backup_before_first_sync(manager):
    """Keep one consistent copy of the store from before it ever joined the cloud."""
    target = Path(manager.db_file + BACKUP_SUFFIX)
    if target.exists():
        return None
    with manager._connection() as conn:
        cursor = conn.execute("SELECT value FROM meta WHERE key='sync_cursor'").fetchone()
        has_base = conn.execute("SELECT name FROM sqlite_master WHERE name='sync_base'").fetchone()
        if has_base and conn.execute('SELECT 1 FROM sync_base LIMIT 1').fetchone():
            return None
    if cursor and cursor[0] != '0':
        return None
    handle, temp = tempfile.mkstemp(prefix='taskflow-backup-', dir=str(target.parent))
    os.close(handle)
    try:
        source, copy = sqlite3.connect(manager.db_file, timeout=5), sqlite3.connect(temp)
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
        # Exclusive creation: an earlier backup is never replaced.
        with open(temp, 'rb') as data, target.open('xb') as output:
            shutil.copyfileobj(data, output)
    finally:
        os.remove(temp)
    return str(target)


class CloudSync:
    """Signs in, stores the session and runs one sync of a TaskFlow store."""

    def __init__(self, db_file, credentials=None, opener=None):
        self.db_file = db_file
        self.credentials = credentials or default_credentials()
        self.opener = opener

    def client(self, config, session=None):
        target = credential_target(config)
        return SupabaseClient(config['url'], config['key'], session=session, opener=self.opener,
                              on_session=lambda value: self.credentials.write(target, json.dumps(value)))

    def session(self, config):
        value = self.credentials.read(credential_target(config))
        try:
            return json.loads(value) if value else None
        except ValueError:
            return None

    def sign_in(self, config, callback, on_sent=None, timeout=600):
        """Email a link and wait for it on this computer; the session goes to the credential store."""
        client = self.client(config)
        client.send_link(config['email'], callback.url)
        if on_sent:
            on_sent()
        client.finish_link(callback.wait(timeout))

    def signed_in(self, config):
        return bool(config and self.session(config))

    def sign_out(self, config):
        self.credentials.delete(credential_target(config))

    def run(self):
        """Return a status dict; never raises for network or session problems."""
        manager = TaskManager(self.db_file)
        config = get_config(manager)
        if not config or not config.get('enabled'):
            return {'state': 'off', 'message': 'Bulut senkronu kapalı.'}
        try:
            with store_lock(self.db_file):
                session = self.session(config)
                if not session:
                    return {'state': 'signed_out', 'message': 'Bulut senkronu için yeniden giriş yapın.'}
                backup = backup_before_first_sync(manager)
                changed = SyncEngine(manager, self.client(config, session)).sync()
        except SupabaseAuthError as exc:
            if exc.status in (400, 401):
                self.sign_out(config)
            return {'state': 'signed_out', 'message': 'Oturum sona erdi; yeniden giriş yapın. ({})'.format(exc)}
        except (OSError, ValueError, sqlite3.Error) as exc:
            return {'state': 'offline', 'message': 'Eşitlenemedi: {}'.format(exc)}
        status = {'state': 'ok', 'changed': changed, 'at': time.time(),
                  'message': 'Eşitlendi · ' + time.strftime('%H:%M')}
        if backup:
            status['backup'] = backup
        return status


def sync_if_enabled(db_file, credentials=None):
    """For the agent bridge: sync when this store has cloud sync on; otherwise do nothing."""
    manager = TaskManager(db_file)
    config = get_config(manager)
    if not config or not config.get('enabled'):
        return None
    return CloudSync(db_file, credentials).run()
