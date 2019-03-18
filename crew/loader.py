import inspect
import sys
import os
import importlib.util
from crew import task
from crew.logger import logger


class NoTaskException(Exception):
    pass


class Package:
    def __init__(self, loader, context, name, base=None):
        self.loader = loader
        self.context = context
        self.name = name
        self.base = base

    def __getattr__(self, name):
        return Package(self.loader, self.context, name, base=self)

    async def __call__(self, *args, **kwargs):
        return await self.task().invoke(*args, **kwargs)

    def _prefix(self):
        if self.base is None:
            return [self.name]
        else:
            return self.base._prefix() + [self.name]

    def task(self):
        task_name = ".".join(self._prefix())
        task = self.loader.load(task_name, self.context)
        return task


class Loader:
    def __init__(self):
        self.tasks = {}

    def load(self, name, context):
        return self.create_task(name, context)

    def package(self, name, context):
        return Package(self, context, name)

    def has_package(self, name):
        for p in sys.path:
            if os.path.isfile(os.path.join(p, "crew", "tasks", name) + ".py"):
                return True
            elif os.path.isdir(os.path.join(p, "crew", "tasks", name)):
                return True
        return False

    def create_task(self, task_name, context):
        self.populate_task(task_name)
        task = self.tasks[task_name]()
        task.context = context
        task.name = task_name
        return task

    def each_task(self, prefix=[]):
        for p in sys.path:
            task_path = os.path.join(p, "tasks", *prefix)
            dir_path = os.path.join(p, "tasks", *prefix)

            if os.path.isfile(task_path) and task_path.endswith(".py"):
                if prefix[-1] == "__init__.py":
                    prefix.pop()
                else:
                    prefix[-1] = os.path.splitext(prefix[-1])[0]
                yield self.populate_task(".".join(prefix))
            elif os.path.isdir(dir_path):
                paths = os.listdir(dir_path)
                paths.sort()
                for p in paths:
                    if p == "__pycache__":
                        continue
                    new_prefix = prefix + [p]
                    for t in self.each_task(new_prefix):
                        yield t

    def populate_task(self, task_name):
        try:
            if task_name not in self.tasks:
                pkg = importlib.import_module(f"crew.tasks.{task_name}")
                c = None
                tests = []
                for name, val in pkg.__dict__.items():
                    if inspect.isclass(val):
                        if issubclass(val, task.BaseTask):
                            task_cls = getattr(pkg, name)
                            task_cls._args()
                            c = task_cls
                            c.task_name = task_name
                        elif issubclass(val, task.TaskTest):
                            tests.append(getattr(pkg, name))
                c.tests = tests
                self.tasks[task_name] = c
        except Exception:
            logger.info(f"error loading {task_name}")
            raise
        return self.tasks[task_name]
