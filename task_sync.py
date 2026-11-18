"""Optional multi-device sync. The local SQLite store stays primary; a server only relays versions.

Records travel in a cloud form: {'kind': 'project'|'task', 'id', 'revision', 'deleted', 'data'}.
Tasks refer to projects by stable id. Bindings and settings never leave the device.
"""
import copy
import json
from pathlib import Path


class MemoryServer:
    """Reference server contract. Tests use it; the Supabase backend implements the same calls."""

    def __init__(self):
        self.records = {}
        self.events = []
        self.seq = 0

    def pull(self, cursor, limit=500):
        changes = sorted([r for r in self.records.values() if r['seq'] > cursor] +
                         [e for e in self.events if e['seq'] > cursor], key=lambda item: item['seq'])
        upto = changes[limit - 1]['seq'] if len(changes) > limit else self.seq
        page = [item for item in changes if item['seq'] <= upto]
        return {'records': [self._public(r) for r in page if 'kind' in r],
                'events': [self._public(e) for e in page if 'kind' not in e],
                'cursor': upto, 'more': upto < self.seq}

    def push_many(self, items):
        # Accept only a change made on top of the current version; otherwise return that version.
        results = []
        for item in items:
            record = item['record']
            current = self.records.get((record['kind'], record['id']))
            if (current['revision'] if current else None) != item['base_revision']:
                results.append({'accepted': False, 'record': self._public(current) if current else None})
                continue
            self.seq += 1
            self.records[(record['kind'], record['id'])] = dict(copy.deepcopy(record), seq=self.seq)
            results.append({'accepted': True, 'record': copy.deepcopy(record)})
        return results

    def push_events(self, events):
        known = {e['id'] for e in self.events}
        for event in events:
            if event['id'] not in known:
                self.seq += 1
                self.events.append(dict(copy.deepcopy(event), seq=self.seq))
                known.add(event['id'])

    @staticmethod
    def _public(item):
        return {k: copy.deepcopy(v) for k, v in item.items() if k != 'seq'}


class SyncEngine:
    # Claim, completion and result fields change together; merging them one by one could mix two claims.
    TASK_STATE = ('status', 'completed', 'completed_at', 'owner', 'claim_token', 'result', 'delivery',
                  'publication_evidence')
    PUSH_ROUNDS = 3
    RECORD_BATCH = 200
    EVENT_BATCH = 500

    def __init__(self, manager, server):
        self.manager = manager
        self.server = server
        with manager._connection(write=True, bump=False) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS sync_base '
                         '(kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY (kind, id))')
            conn.execute('CREATE TABLE IF NOT EXISTS sync_events (id TEXT PRIMARY KEY)')
            conn.execute("INSERT OR IGNORE INTO meta VALUES ('sync_cursor','0')")

    def sync(self):
        """Pull, then push local changes. Server calls never run inside a local transaction."""
        changed = self._pull()
        for _ in range(self.PUSH_ROUNDS):
            pushed_changes, rejected = self._push()
            changed |= pushed_changes
            if not rejected:
                break
        self._push_events()
        if changed:
            self.manager._after_write()
        else:
            self.manager.load()
        return changed

    # Local state

    @staticmethod
    def _bump(conn):
        conn.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='change'")

    @staticmethod
    def _base(conn, kind, record_id):
        row = conn.execute('SELECT payload FROM sync_base WHERE kind=? AND id=?', (kind, record_id)).fetchone()
        return json.loads(row[0]) if row else None

    def _set_base(self, conn, record):
        conn.execute('INSERT OR REPLACE INTO sync_base VALUES (?,?,?)',
                     (record['kind'], record['id'], self.manager._json(record)))

    @staticmethod
    def _content(record):
        return None if not record or record['deleted'] else record['data']

    @staticmethod
    def _tombstone(base):
        return {'kind': base['kind'], 'id': base['id'], 'revision': base['revision'] + 1, 'deleted': True,
                'data': None}

    @staticmethod
    def _order(record):
        # Live projects first so tasks can resolve them; project deletions last.
        if record['kind'] == 'project':
            return 2 if record['deleted'] else 0
        return 1

    def _task_record(self, task, position, uids):
        data = {k: copy.deepcopy(v) for k, v in task.items() if k != 'project'}
        data.update(project_id=uids.get(task.get('project')), position=position)
        return {'kind': 'task', 'id': task['id'], 'revision': task['revision'], 'deleted': False, 'data': data}

    def _local_task(self, conn, task_id):
        row = conn.execute('SELECT position,payload FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            return None
        return self._task_record(json.loads(row[1]), row[0], dict(conn.execute('SELECT name,uid FROM project_ids')))

    def _local_records(self, conn):
        uids = dict(conn.execute('SELECT name,uid FROM project_ids'))
        records = {}
        for name, position in conn.execute('SELECT name,position FROM projects'):
            if uids.get(name):
                records[('project', uids[name])] = {'kind': 'project', 'id': uids[name], 'revision': None,
                                                    'deleted': False, 'data': {'name': name, 'position': position}}
        for task_id, position, payload in conn.execute('SELECT id,position,payload FROM tasks'):
            records[('task', task_id)] = self._task_record(json.loads(payload), position, uids)
        return records

    # Pull

    def _pull(self):
        changed, more = False, True
        while more:
            with self.manager._connection() as conn:
                cursor = int(conn.execute("SELECT value FROM meta WHERE key='sync_cursor'").fetchone()[0])
            batch = self.server.pull(cursor)
            changed |= self._apply_batch(batch)
            more = batch.get('more', False)
        return changed

    def _apply_batch(self, batch):
        with self.manager._connection(write=True, bump=False) as conn:
            changed = False
            for record in sorted(batch['records'], key=self._order):
                changed |= self._apply(conn, record)
            for event in batch['events']:
                changed |= conn.execute('INSERT OR IGNORE INTO task_events VALUES (?,?,?,?)',
                                        (event['id'], event['project_id'], event['task_id'],
                                         self.manager._json(event['payload']))).rowcount > 0
                conn.execute('INSERT OR IGNORE INTO sync_events VALUES (?)', (event['id'],))
            conn.execute("UPDATE meta SET value=? WHERE key='sync_cursor'", (str(batch['cursor']),))
            if changed:
                self._bump(conn)
        return changed

    def _apply(self, conn, remote):
        if self._base(conn, remote['kind'], remote['id']) == remote:
            return False
        if remote['kind'] == 'project':
            changed = self._apply_project(conn, remote)
        else:
            changed = self._apply_task(conn, remote)
        self._set_base(conn, remote)
        return changed

    def _apply_task(self, conn, remote):
        base = self._base(conn, 'task', remote['id'])
        local = self._local_task(conn, remote['id'])
        if self._content(local) == self._content(base):
            result = remote
        elif local is None:
            return False  # Deleted here; the deletion is pushed next.
        elif remote['deleted']:
            # Deletion wins; the local edit stays readable in the journal.
            self.manager._record_event(conn, self._from_cloud(conn, local['data']), 'sync_conflict')
            result = remote
        else:
            result = self._merge_task(conn, base, local, remote)
        if self._content(result) == self._content(local):
            return False
        if result['deleted']:
            conn.execute('DELETE FROM tasks WHERE id=?', (remote['id'],))
        else:
            conn.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?)',
                         (remote['id'], result['data']['position'],
                          self.manager._json(self._from_cloud(conn, result['data']))))
        return True

    def _from_cloud(self, conn, data):
        task = {k: copy.deepcopy(v) for k, v in data.items() if k not in {'project_id', 'position'}}
        row = conn.execute('SELECT name FROM project_ids WHERE uid=?', (data.get('project_id'),)).fetchone()
        task['project'] = row[0] if row else None
        return task

    def _merge_task(self, conn, base, local, remote):
        b, l, r = (self._content(x) or {} for x in (base, local, remote))
        merged, lost = copy.deepcopy(r), False
        keys = (set(b) | set(l) | set(r)) - set(self.TASK_STATE) - {'revision', 'history'}
        for group in [(key,) for key in sorted(keys)] + [self.TASK_STATE]:
            values = lambda side: [side.get(key) for key in group]
            if values(l) == values(b):
                continue
            if values(r) == values(b):
                for key in group:
                    if key in l:
                        merged[key] = copy.deepcopy(l[key])
                    else:
                        merged.pop(key, None)
            elif values(r) != values(l):
                # A lost claim is not content; a lost result or edit stays readable in the journal.
                lost |= group != self.TASK_STATE or l.get('result') != b.get('result')
        history = r.get('history', []) + [item for item in l.get('history', []) if item not in r.get('history', [])]
        if history:
            merged['history'] = history
        if lost:
            self.manager._record_event(conn, self._from_cloud(conn, l), 'sync_conflict')
        if {k: v for k, v in merged.items() if k != 'revision'} == {k: v for k, v in r.items() if k != 'revision'}:
            return remote
        # A merged version invalidates both claims, exactly like a local edit does.
        merged['revision'] = max(l['revision'], r['revision']) + 1
        if merged.get('status') == 'in_progress':
            merged['status'] = 'pending'
            merged.pop('owner', None)
            merged.pop('claim_token', None)
        return {'kind': 'task', 'id': remote['id'], 'revision': merged['revision'], 'deleted': False, 'data': merged}

    def _apply_project(self, conn, remote):
        base = self._base(conn, 'project', remote['id'])
        row = conn.execute('SELECT name FROM project_ids WHERE uid=?', (remote['id'],)).fetchone()
        name = row[0] if row else None
        if remote['deleted']:
            if not name:
                return False
            self.manager._delete_project(conn, name)
            return True
        wanted = remote['data']
        if name is None:
            if base:
                return False  # Deleted here; the deletion is pushed next.
            twin = conn.execute('SELECT p.binding, i.uid FROM projects p JOIN project_ids i ON i.name=p.name '
                                'WHERE p.name=?', (wanted['name'],)).fetchone()
            if twin and self._base(conn, 'project', twin[1]) is None:
                self._adopt(conn, wanted['name'], twin[1], remote['id'], twin[0])
            else:
                name = self._free_name(conn, wanted['name'])
                conn.execute('INSERT INTO projects VALUES (?,?,NULL)', (name, wanted['position']))
                conn.execute('INSERT INTO project_ids VALUES (?,?)', (name, remote['id']))
                return True
            name = wanted['name']
        else:
            position = conn.execute('SELECT position FROM projects WHERE name=?', (name,)).fetchone()[0]
            local, old = {'name': name, 'position': position}, self._content(base) or {}
            wanted = {key: local[key] if local[key] != old.get(key) and wanted[key] == old.get(key) else wanted[key]
                      for key in ('name', 'position')}
        if wanted['name'] != name:
            name = self._rename(conn, name, wanted['name'])
        conn.execute('UPDATE projects SET position=? WHERE name=?', (wanted['position'], name))
        return True

    def _adopt(self, conn, name, old, new, binding):
        # The same project created on two devices before they synced: keep the cloud id.
        conn.execute('UPDATE project_ids SET uid=? WHERE name=?', (new, name))
        conn.execute('UPDATE task_events SET project_id=? WHERE project_id=?', (new, old))
        if binding and json.loads(binding)['project_id'] == old:
            binding = json.loads(binding)
            self._rename_markers(binding, old, new)
            binding['project_id'] = new
            conn.execute('UPDATE projects SET binding=? WHERE name=?', (self.manager._json(binding), name))

    def _rename_markers(self, binding, old, new):
        if not binding.get('brain_dir'):
            return
        for filename, prefix in (('TODO.md', 'taskflow'), ('TASKFLOW_HISTORY.md', 'taskflow-history')):
            target = Path(binding['brain_dir']) / filename
            try:
                if not target.exists():
                    continue
                original = target.read_text(encoding='utf-8-sig')
                output = original
                for edge in ('begin', 'end'):
                    output = output.replace('<!-- {}:{} {} -->'.format(prefix, edge, old),
                                            '<!-- {}:{} {} -->'.format(prefix, edge, new))
                if output != original:
                    self.manager._atomic_text(target, output)
            except OSError as exc:
                self.manager.sync_errors.append(str(exc))

    @staticmethod
    def _free_name(conn, name, ignore=None):
        candidate, index = name, 2
        while candidate != ignore and conn.execute('SELECT 1 FROM projects WHERE name=?', (candidate,)).fetchone():
            candidate, index = '{} ({})'.format(name, index), index + 1
        return candidate

    def _rename(self, conn, old, new):
        new = self._free_name(conn, new, ignore=old)
        conn.execute('UPDATE projects SET name=? WHERE name=?', (new, old))
        conn.execute('UPDATE project_ids SET name=? WHERE name=?', (new, old))
        for payload, in conn.execute('SELECT payload FROM tasks').fetchall():
            task = json.loads(payload)
            if task.get('project') == old:
                task['project'] = new
                self.manager._write_task(conn, task)
        return new

    # Push

    def _push(self):
        with self.manager._connection() as conn:
            local = self._local_records(conn)
            bases = {(k, i): json.loads(p) for k, i, p in conn.execute('SELECT kind,id,payload FROM sync_base')}
        pending = []
        for key in local.keys() | bases.keys():
            record, base = local.get(key), bases.get(key)
            if self._content(record) == self._content(base):
                continue
            if record is None:
                record = self._tombstone(base)
            elif record['kind'] == 'project':
                record['revision'] = (base['revision'] if base else 0) + 1
            pending.append((record, base))
        pending.sort(key=lambda pair: self._order(pair[0]))
        changed, rejected = False, 0
        for start in range(0, len(pending), self.RECORD_BATCH):
            chunk = pending[start:start + self.RECORD_BATCH]
            responses = self.server.push_many([{'record': record, 'base_revision': base['revision'] if base else None}
                                               for record, base in chunk])
            with self.manager._connection(write=True, bump=False) as conn:
                applied = False
                for (record, _), response in zip(chunk, responses):
                    if response['accepted']:
                        self._set_base(conn, response['record'])
                        continue
                    rejected += 1
                    if response['record'] is None:
                        conn.execute('DELETE FROM sync_base WHERE kind=? AND id=?', (record['kind'], record['id']))
                    else:
                        applied |= self._apply(conn, response['record'])
                if applied:
                    changed = True
                    self._bump(conn)
        return changed, rejected

    def _push_events(self):
        with self.manager._connection() as conn:
            events = [{'id': i, 'project_id': p, 'task_id': t, 'payload': json.loads(payload)}
                      for i, p, t, payload in conn.execute(
                          'SELECT id,project_id,task_id,payload FROM task_events '
                          'WHERE id NOT IN (SELECT id FROM sync_events) ORDER BY rowid')]
        for start in range(0, len(events), self.EVENT_BATCH):
            chunk = events[start:start + self.EVENT_BATCH]
            self.server.push_events(chunk)
            with self.manager._connection(write=True, bump=False) as conn:
                conn.executemany('INSERT OR IGNORE INTO sync_events VALUES (?)', [(e['id'],) for e in chunk])
