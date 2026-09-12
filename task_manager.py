import json
import os
import sys
import uuid
from datetime import datetime

class TaskManager:
    DEFAULT_PROJECTS = ['Genel', 'İş', 'Kişisel', 'Acil']
    
    def __init__(self, data_file=None):
        if data_file:
            self.data_file = os.path.abspath(data_file)
        else:
            # Portable check: if data.json exists in executable directory, use it
            exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
            local_file = os.path.join(exe_dir, 'data.json')
            if os.path.exists(local_file):
                self.data_file = local_file
            else:
                appdata = os.getenv('APPDATA') or os.path.expanduser('~')
                save_dir = os.path.join(appdata, 'FlowList')
                os.makedirs(save_dir, exist_ok=True)
                self.data_file = os.path.join(save_dir, 'data.json')

        self.projects = list(self.DEFAULT_PROJECTS)
        self.tasks = []
        self.settings = {
            'always_on_top': False,
            'autostart': False,
            'selected_project': 'Tümü'
        }
        self.load()

    def load(self):
        if not os.path.exists(self.data_file):
            # First time load with sample starter tasks
            self._init_defaults()
            self.save()
            return

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.projects = data.get('projects', self.DEFAULT_PROJECTS)
                if 'Genel' not in self.projects:
                    self.projects.insert(0, 'Genel')
                self.tasks = data.get('tasks', [])
                self.settings.update(data.get('settings', {}))
        except Exception as e:
            print(f'Error loading tasks: {e}')
            self._init_defaults()

    def _init_defaults(self):
        self.projects = list(self.DEFAULT_PROJECTS)
        self.tasks = [
            {
                'id': str(uuid.uuid4())[:8],
                'title': 'FlowList To-Do uygulamasına hoş geldiniz!',
                'project': 'Genel',
                'completed': False,
                'created_at': datetime.now().strftime('%d.%m.%Y %H:%M')
            },
            {
                'id': str(uuid.uuid4())[:8],
                'title': 'Üstteki butonla pencereyi sistem tepsisine gizleyebilirsiniz',
                'project': 'Genel',
                'completed': False,
                'created_at': datetime.now().strftime('%d.%m.%Y %H:%M')
            }
        ]

    def save(self):
        try:
            dirname = os.path.dirname(os.path.abspath(self.data_file))
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            data = {
                'projects': self.projects,
                'tasks': self.tasks,
                'settings': self.settings
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'Error saving tasks: {e}')

    def add_task(self, title, project='Genel'):
        title = title.strip()
        if not title:
            return None
        if project not in self.projects and project != 'Tümü':
            self.projects.append(project)

        task = {
            'id': str(uuid.uuid4())[:8],
            'title': title,
            'project': project if project != 'Tümü' else 'Genel',
            'completed': False,
            'created_at': datetime.now().strftime('%d.%m.%Y %H:%M')
        }
        self.tasks.insert(0, task)
        self.save()
        return task

    def toggle_task(self, task_id):
        for task in self.tasks:
            if task['id'] == task_id:
                task['completed'] = not task.get('completed', False)
                self.save()
                return task
        return None

    def delete_task(self, task_id):
        initial_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t['id'] != task_id]
        if len(self.tasks) != initial_len:
            self.save()
            return True
        return False

    def edit_task(self, task_id, new_title):
        new_title = new_title.strip()
        if not new_title:
            return False
        for task in self.tasks:
            if task['id'] == task_id:
                task['title'] = new_title
                self.save()
                return True
        return False

    def clear_completed(self, project_filter=None):
        if project_filter and project_filter != 'Tümü':
            self.tasks = [t for t in self.tasks if not (t.get('completed') and t.get('project') == project_filter)]
        else:
            self.tasks = [t for t in self.tasks if not t.get('completed')]
        self.save()

    def add_project(self, name):
        name = name.strip()
        if name and name not in self.projects and name != 'Tümü':
            self.projects.append(name)
            self.save()
            return True
        return False

    def delete_project(self, name):
        if name in self.projects and name != 'Genel':
            self.projects.remove(name)
            # Reassign deleted project tasks to Genel
            for task in self.tasks:
                if task.get('project') == name:
                    task['project'] = 'Genel'
            self.save()
            return True
        return False

    def get_tasks(self, project_filter=None):
        if not project_filter or project_filter == 'Tümü':
            return self.tasks
        return [t for t in self.tasks if t.get('project') == project_filter]

    def get_stats(self, project_filter=None):
        tasks = self.get_tasks(project_filter)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get('completed'))
        return total, completed
