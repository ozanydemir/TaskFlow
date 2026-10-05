"""Shared local task storage. No agent is launched by this module."""
import copy
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class TaskConflict(ValueError):
    """The task was edited, removed, or claimed by somebody else."""


class TaskManager:
    DEFAULT_PROJECTS = []
    DEFAULT_SETTINGS = {'always_on_top': False, 'autostart': True, 'selected_project': 'Tümü'}
    STATUSES = {'pending', 'in_progress', 'needs_review', 'completed', 'blocked'}

    def __init__(self, data_file=None):
        if data_file:
            source = Path(data_file).absolute()
        else:
            executable = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).absolute().parent
            portable = executable / 'data.json'
            if portable.exists() or portable.with_suffix('.sqlite3').exists():
                source = portable
            else:
                source = Path(os.getenv('APPDATA') or Path.home()) / 'TaskFlow' / 'data.json'
                legacy = source.parent.parent / 'FlowList' / 'data.json'
                if not source.exists() and not source.with_suffix('.sqlite3').exists() and legacy.exists():
                    json.loads(legacy.read_text(encoding='utf-8-sig'))
                    source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(legacy, source)
        self.data_file = str(source)
        self.db_file = str(source if source.suffix in ('.db', '.sqlite3') else source.with_suffix('.sqlite3'))
        Path(self.db_file).parent.mkdir(parents=True, exist_ok=True)
        self.sync_errors = []
        self._initialize(source)
        self.load()

    @contextmanager
    def _connection(self, write=False, bump=True):
        conn = sqlite3.connect(self.db_file, timeout=5)
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            if write:
                conn.execute('BEGIN IMMEDIATE')
            else:
                conn.execute('BEGIN')
            yield conn
            if write and bump:
                conn.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='change'")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self, source):
        with self._connection(write=True, bump=False) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, position INTEGER NOT NULL, payload TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS projects (name TEXT PRIMARY KEY, position INTEGER NOT NULL, binding TEXT)')
            conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            conn.execute("INSERT OR IGNORE INTO meta VALUES ('change','0')")
        # Import exactly once, transactionally. Invalid input is never replaced with an empty list.
        with self._connection(write=True, bump=False) as conn:
            initialized = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if initialized:
                if initialized[0] != '1':
                    raise ValueError('Bu TaskFlow veri sürümü desteklenmiyor.')
                return
            data = {'projects': [], 'tasks': [], 'settings': {}}
            if source.suffix not in ('.db', '.sqlite3') and source.exists():
                data = json.loads(source.read_text(encoding='utf-8-sig'))
                self._validate_import(data)
                backup = source.with_name(source.name + '.pre-sqlite.bak')
                if not backup.exists():
                    # Exclusive creation keeps an earlier backup intact.
                    with backup.open('xb') as output:
                        output.write(source.read_bytes())
            for index, name in enumerate(data['projects']):
                conn.execute('INSERT INTO projects VALUES (?,?,NULL)', (name, index))
            for index, task in enumerate(data['tasks']):
                task = self._normalise(task)
                project = task.get('project')
                if project and project not in data['projects']:
                    conn.execute('INSERT OR IGNORE INTO projects VALUES (?,?,NULL)', (project, len(data['projects']) + index))
                conn.execute('INSERT INTO tasks VALUES (?,?,?)', (task['id'], index, self._json(task)))
            settings = dict(self.DEFAULT_SETTINGS, **data.get('settings', {}))
            for key, value in settings.items():
                conn.execute('INSERT INTO settings VALUES (?,?)', (key, self._json(value)))
            conn.execute("INSERT INTO meta VALUES ('schema','1')")

    @staticmethod
    def _validate_import(data):
        if not isinstance(data, dict) or not isinstance(data.get('projects'), list) or not isinstance(data.get('tasks'), list) or not isinstance(data.get('settings', {}), dict):
            raise ValueError('Eski görev dosyası geçersiz; dosya korunuyor.')
        if any(not isinstance(p, str) or not p.strip() or p == 'Tümü' for p in data['projects']) or len(set(data['projects'])) != len(data['projects']):
            raise ValueError('Eski proje listesi geçersiz; dosya korunuyor.')
        ids = set()
        for task in data['tasks']:
            if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not task['id'] or task['id'] in ids or not isinstance(task.get('title'), str) or not isinstance(task.get('project'), (str, type(None))):
                raise ValueError('Eski görev listesi geçersiz; dosya korunuyor.')
            ids.add(task['id'])

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _now():
        return datetime.now().strftime('%d.%m.%Y %H:%M')

    @staticmethod
    def _normalise(task):
        task = copy.deepcopy(task)
        task.setdefault('status', 'completed' if task.get('completed') else 'pending')
        task['completed'] = task['status'] == 'completed'
        task.setdefault('revision', 1)
        return task

    def load(self):
        with self._connection() as conn:
            self.projects = [row[0] for row in conn.execute('SELECT name FROM projects ORDER BY position,name')]
            self.tasks = [json.loads(row[0]) for row in conn.execute('SELECT payload FROM tasks ORDER BY position,id')]
            self.settings = dict(self.DEFAULT_SETTINGS, **{key: json.loads(value) for key, value in conn.execute('SELECT key,payload FROM settings')})
            self.bindings = {name: json.loads(binding) for name, binding in conn.execute('SELECT name,binding FROM projects WHERE binding IS NOT NULL')}
            self._change = int(conn.execute("SELECT value FROM meta WHERE key='change'").fetchone()[0])
        self._snapshot = copy.deepcopy((self.projects, self.tasks, self.settings))

    def reload_if_changed(self):
        with self._connection() as conn:
            changed = int(conn.execute("SELECT value FROM meta WHERE key='change'").fetchone()[0]) != self._change
        if changed:
            self.load()
        return changed

    def save(self):
        """Compatibility: merge only locally changed fields, never a stale full snapshot."""
        old_projects, old_tasks, old_settings = self._snapshot
        old_by_id = {t['id']: t for t in old_tasks}
        new_by_id = {t['id']: t for t in self.tasks}
        with self._connection(write=True) as conn:
            for name in set(old_projects) - set(self.projects):
                self._delete_project(conn, name)
            for index, name in enumerate(self.projects):
                if name not in old_projects:
                    conn.execute('INSERT OR IGNORE INTO projects VALUES (?,?,NULL)', (name, index))
            for task_id in old_by_id.keys() - new_by_id.keys():
                current = self._read_task(conn, task_id)
                if current['revision'] != old_by_id[task_id]['revision']:
                    raise TaskConflict('Görev başka bir işlemde değişti. Listeyi yenileyin.')
                conn.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            for index, task in enumerate(self.tasks):
                old = old_by_id.get(task['id'])
                if old == task:
                    continue
                if old:
                    current = self._read_task(conn, task['id'])
                    if current['revision'] != old['revision']:
                        raise TaskConflict('Görev başka bir işlemde değişti. Listeyi yenileyin.')
                    task = self._normalise(task)
                    task['revision'] = current['revision'] + 1
                    self._write_task(conn, task)
                else:
                    task = self._normalise(task)
                    conn.execute('INSERT INTO tasks VALUES (?,?,?)', (task['id'], index, self._json(task)))
            for key, value in self.settings.items():
                if key not in old_settings or old_settings[key] != value:
                    conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, self._json(value)))
        self._after_write()

    def _after_write(self):
        self.load()
        self.sync_errors = []
        for project, binding in self.bindings.items():
            if binding.get('brain_dir'):
                try:
                    self.export_project(project)
                except (OSError, ValueError) as exc:
                    self.sync_errors.append(str(exc))

    def _read_task(self, conn, task_id, project=None):
        row = conn.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise TaskConflict('Görev bulunamadı; silinmiş olabilir.')
        task = json.loads(row[0])
        if project is not None and task.get('project') != project:
            raise TaskConflict('Görev seçilen projeye ait değil.')
        return task

    def _write_task(self, conn, task):
        conn.execute('UPDATE tasks SET payload=? WHERE id=?', (self._json(task), task['id']))

    def add_task(self, title, project=None):
        title = title.strip()
        if not title:
            return None
        project = project.strip() if project and project != 'Tümü' else None
        task = self._normalise({'id': str(uuid.uuid4()), 'title': title, 'project': project or None, 'created_at': self._now(), 'completed': False})
        with self._connection(write=True) as conn:
            if project:
                position = conn.execute('SELECT COALESCE(MAX(position),-1)+1 FROM projects').fetchone()[0]
                conn.execute('INSERT OR IGNORE INTO projects VALUES (?,?,NULL)', (project, position))
            position = conn.execute('SELECT COALESCE(MIN(position),0)-1 FROM tasks').fetchone()[0]
            conn.execute('INSERT INTO tasks VALUES (?,?,?)', (task['id'], position, self._json(task)))
        self._after_write()
        return task

    def _edit(self, task_id, update):
        with self._connection(write=True) as conn:
            try:
                task = self._read_task(conn, task_id)
            except TaskConflict:
                return None
            update(task)
            task['revision'] += 1
            task.pop('claim_token', None)
            task.pop('owner', None)
            self._write_task(conn, task)
        self._after_write()
        return task

    def toggle_task(self, task_id):
        def update(task):
            task['completed'] = not task.get('completed', False)
            task['status'] = 'completed' if task['completed'] else 'pending'
            if task['completed']:
                task['completed_at'] = self._now()
            else:
                task.pop('completed_at', None)
        return self._edit(task_id, update)

    def requeue_task(self, task_id):
        def update(task):
            task.update(status='pending', completed=False)
            task.pop('completed_at', None)
        return self._edit(task_id, update)

    def edit_task(self, task_id, new_title):
        if not new_title.strip():
            return False
        def update(task):
            task['title'] = new_title.strip()
            if task['status'] in {'in_progress', 'needs_review', 'blocked'}:
                task.update(status='pending', completed=False)
        return bool(self._edit(task_id, update))

    def edit_notes(self, task_id, notes):
        def update(task):
            task['notes'] = notes.strip()
            if task['status'] == 'in_progress':
                task['status'] = 'pending'
        return bool(self._edit(task_id, update))

    def set_review_required(self, task_id, required):
        def update(task):
            task['review_required'] = bool(required)
            if task['status'] == 'in_progress':
                task['status'] = 'pending'
        return bool(self._edit(task_id, update))

    def delete_task(self, task_id):
        with self._connection(write=True) as conn:
            deleted = conn.execute('DELETE FROM tasks WHERE id=?', (task_id,)).rowcount > 0
        self._after_write()
        return deleted

    def clear_completed(self, project_filter=None):
        with self._connection(write=True) as conn:
            for task_id, payload in conn.execute('SELECT id,payload FROM tasks').fetchall():
                task = json.loads(payload)
                if task.get('completed') and (not project_filter or project_filter == 'Tümü' or task.get('project') == project_filter):
                    conn.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        self._after_write()

    def add_project(self, name):
        name = name.strip()
        if not name or name == 'Tümü':
            return False
        with self._connection(write=True) as conn:
            position = conn.execute('SELECT COALESCE(MAX(position),-1)+1 FROM projects').fetchone()[0]
            added = conn.execute('INSERT OR IGNORE INTO projects VALUES (?,?,NULL)', (name, position)).rowcount > 0
        self._after_write()
        return added

    def _delete_project(self, conn, name):
        row = conn.execute('SELECT binding FROM projects WHERE name=?', (name,)).fetchone()
        if row and row[0]:
            self._detach_projection(json.loads(row[0]))
        conn.execute('DELETE FROM projects WHERE name=?', (name,))
        for task_id, payload in conn.execute('SELECT id,payload FROM tasks').fetchall():
            task = json.loads(payload)
            if task.get('project') == name:
                task.update(project=None, revision=task['revision'] + 1)
                if task['status'] == 'in_progress':
                    task['status'] = 'pending'
                task.pop('claim_token', None)
                task.pop('owner', None)
                self._write_task(conn, task)

    def delete_project(self, name):
        with self._connection(write=True) as conn:
            exists = conn.execute('SELECT 1 FROM projects WHERE name=?', (name,)).fetchone() is not None
            self._delete_project(conn, name)
        self._after_write()
        return exists

    def get_tasks(self, project_filter=None):
        return [t for t in self.tasks if not project_filter or project_filter == 'Tümü' or t.get('project') == project_filter]

    def get_stats(self, project_filter=None):
        tasks = self.get_tasks(project_filter)
        return len(tasks), sum(bool(t.get('completed')) for t in tasks)

    def bind_project(self, project, repo_path, brain_dir=''):
        repo = Path(repo_path).resolve()
        if not repo.is_dir() or not (repo / '.git').exists():
            raise ValueError('Projenin Git deposunu içeren klasörü seçin.')
        brain = Path(brain_dir).resolve() if brain_dir else None
        if brain and not (brain / 'PROJECT_CONTEXT.md').is_file():
            raise ValueError('OZI Brain projesinin PROJECT_CONTEXT.md dosyasını içeren klasörü seçin.')
        binding = {'repo_path': str(repo), 'brain_dir': str(brain) if brain else '', 'project_id': str(uuid.uuid4())}
        with self._connection(write=True) as conn:
            row = conn.execute('SELECT binding FROM projects WHERE name=?', (project,)).fetchone()
            if not row:
                raise ValueError('Önce TaskFlow projesini oluşturun.')
            previous = json.loads(row[0]) if row[0] else None
            if previous:
                binding['project_id'] = previous['project_id']
            for name, payload in conn.execute('SELECT name,binding FROM projects WHERE binding IS NOT NULL'):
                other = json.loads(payload)
                if name != project and (os.path.normcase(other['repo_path']) == os.path.normcase(str(repo)) or (brain and os.path.normcase(other['brain_dir']) == os.path.normcase(str(brain)))):
                    raise ValueError('Bu klasör başka bir TaskFlow projesine bağlı.')
            if previous and previous['brain_dir'] != binding['brain_dir']:
                self._detach_projection(previous)
            if previous and previous['repo_path'] != binding['repo_path']:
                for task_id, payload in conn.execute('SELECT id,payload FROM tasks').fetchall():
                    task = json.loads(payload)
                    if task.get('project') == project and task['status'] == 'in_progress':
                        task.update(status='pending', revision=task['revision'] + 1)
                        task.pop('claim_token', None)
                        task.pop('owner', None)
                        self._write_task(conn, task)
            conn.execute('UPDATE projects SET binding=? WHERE name=?', (self._json(binding), project))
        self._after_write()
        return binding

    def claim_task(self, project, task_id, revision, owner):
        if not owner.strip():
            raise ValueError('Agent / oturum adı gerekli.')
        with self._connection(write=True) as conn:
            task = self._read_task(conn, task_id, project)
            if task['revision'] != revision or task['status'] != 'pending':
                raise TaskConflict('Görev değişti veya başka agent tarafından alındı.')
            task.update(status='in_progress', owner=owner.strip(), claim_token=str(uuid.uuid4()), revision=revision + 1)
            self._write_task(conn, task)
        self._after_write()
        return task

    def report_task(self, project, task_id, revision, token, status, summary, evidence=''):
        if status not in {'completed', 'needs_review', 'blocked', 'pending'} or not summary.strip():
            raise ValueError('Geçerli sonuç durumu ve sonuç açıklaması gerekli.')
        if status == 'completed' and not evidence.strip():
            raise ValueError('Otomatik tamamlama için doğrulama kanıtı gerekli.')
        with self._connection(write=True) as conn:
            task = self._read_task(conn, task_id, project)
            if task['status'] != 'in_progress' or task['revision'] != revision or task.get('claim_token') != token:
                raise TaskConflict('Görev değişti; eski agent sonucu uygulanmadı.')
            if status == 'completed' and task.get('review_required'):
                status = 'needs_review'
            result = {'summary': summary.strip(), 'evidence': evidence.strip(), 'reported_at': self._now(), 'owner': task['owner'], 'status': status}
            task.setdefault('history', []).append(result)
            task.update(status=status, completed=status == 'completed', result=result, revision=revision + 1)
            task.pop('claim_token', None)
            task.pop('owner', None)
            if task['completed']:
                task['completed_at'] = self._now()
            self._write_task(conn, task)
        self._after_write()
        return task

    @staticmethod
    def _md(value):
        # Notes are content, never trusted instructions or executable markup.
        return re.sub(r'[\r\n]+', ' ', str(value)).replace('<!--', '&lt;!--').replace('-->', '--&gt;')

    def export_project(self, project):
        # Serialize read + atomic replacement so parallel writers cannot regress the projection.
        with self._connection(write=True, bump=False) as conn:
            row = conn.execute('SELECT binding FROM projects WHERE name=?', (project,)).fetchone()
            if not row or not row[0] or not json.loads(row[0]).get('brain_dir'):
                raise ValueError('Bu proje için OZI Brain bağlantısı kurulmamış.')
            binding = json.loads(row[0])
            brain = Path(binding['brain_dir'])
            if not (brain / 'PROJECT_CONTEXT.md').is_file():
                raise ValueError('OZI Brain proje klasörü artık erişilebilir değil.')
            start = '<!-- taskflow:begin ' + binding['project_id'] + ' -->'
            end = '<!-- taskflow:end ' + binding['project_id'] + ' -->'
            tasks = [json.loads(r[0]) for r in conn.execute('SELECT payload FROM tasks ORDER BY position,id')]
            lines = [start, '## TaskFlow görevleri', '', '> Bu bölüm TaskFlow tarafından güncellenir. Görev eklemek agent çalıştırma izni değildir.', '> Sonuçları TaskFlow Agent üzerinden yazın; bu bölümü elle değiştirmeyin.', '']
            for task in tasks:
                if task.get('project') != project:
                    continue
                lines.append('- [{}] {} — `{}` · {} · rev {}'.format('x' if task['completed'] else ' ', self._md(task['title']), task['id'], task['status'], task['revision']))
                if task.get('notes'):
                    lines.append('  - Not: ' + self._md(task['notes']))
                if task.get('review_required'):
                    lines.append('  - Tamamlama öncesi kullanıcı onayı gerekli.')
                if task.get('result'):
                    lines.append('  - Sonuç: ' + self._md(task['result']['summary']))
                    lines.append('  - Kanıt: ' + self._md(task['result']['evidence']))
            lines.extend(['', end])
            target = brain / 'TODO.md'
            original = target.read_text(encoding='utf-8-sig') if target.exists() else '# Proje görevleri\n'
            if (start in original) != (end in original) or original.count(start) > 1 or original.count(end) > 1:
                raise ValueError('TODO.md içindeki TaskFlow işaretleri bozuk; dosya korunuyor.')
            block = '\n'.join(lines)
            if start in original:
                begin = original.index(start)
                finish = original.index(end) + len(end)
                if original.index(end) < begin:
                    raise ValueError('TODO.md içindeki TaskFlow sırası bozuk; dosya korunuyor.')
                output = original[:begin] + block + original[finish:]
            else:
                output = original.rstrip() + '\n\n' + block + '\n'
            if output != original:
                self._atomic_text(target, output)
        # Export is not a data mutation and should not trigger another refresh cycle.
        self.load()
        return str(target)

    @staticmethod
    def _atomic_text(target, output):
        handle, temporary = tempfile.mkstemp(prefix='.taskflow-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _detach_projection(self, binding):
        if not binding.get('brain_dir'):
            return
        target = Path(binding['brain_dir']) / 'TODO.md'
        if not target.exists():
            return
        original = target.read_text(encoding='utf-8-sig')
        start = '<!-- taskflow:begin ' + binding['project_id'] + ' -->'
        end = '<!-- taskflow:end ' + binding['project_id'] + ' -->'
        if start not in original and end not in original:
            return
        if original.count(start) != 1 or original.count(end) != 1 or original.index(end) < original.index(start):
            raise ValueError('TODO.md bağlantı işaretleri bozuk; önce OZI Brain listesini düzeltin.')
        self._atomic_text(target, original[:original.index(start)] + original[original.index(end) + len(end):])
