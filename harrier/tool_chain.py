import sys
from itertools import chain
from operator import attrgetter
from importlib import import_module

from .common import logger


class _ToolList(list):
    def prioritise(self, attr):
        super().sort(key=attrgetter(attr), reverse=True)


class ToolChain(_ToolList):
    files_built, tools_run, source_map = 0, 0, None

    def __init__(self, tool_classes, config, partial):
        super().__init__(t(config, partial) for t in tool_classes)

    def get_extra_files(self) -> set:
        return set(chain(*[t.extra_files for t in self if t.active]))

    def sort_on(self, attr, reverse=False):
        super().sort(key=attrgetter(attr), reverse=reverse)

    def assign_file(self, file_path, changed):
        for t in self:
            if t.assign_file(file_path, changed):
                break

    def build(self):
        self.prioritise('build_priority')
        self.source_map = {}
        for t in self:
            if not t.active:
                continue
            files_built, source_map = t.build()
            logger.debug('built %s files with %s', files_built, t.name)
            self.files_built += files_built
            self.source_map.update(source_map)
            self.tools_run += 1

    @property
    def status(self):
        return {
            'tools': len(self),
            'tools_run': self.tools_run,
            'files_built': self.files_built
        }

    def get_tool(self, tool_name):
        return next((t for t in self if t.name.lower() == tool_name.lower()), None)

    def __str__(self):
        return '{tools} tools of which {tools_run} run, {files_built} files built'.format(**self.status)


class ToolChainFactory(_ToolList):
    def __init__(self, config):
        self._config = config
        super().__init__(import_string(t) for t in config.tools)
        self.prioritise('ownership_priority')

    def __call__(self, partial) -> ToolChain:
        return ToolChain(self, self._config, partial)


def import_string(dotted_path):
    """
    Stolen verbatim from django.

    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:  # pragma: no cover
        e = ImportError("{} doesn't look like a module path".format(dotted_path))
        raise e.with_traceback(sys.exc_info()[2])

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:  # pragma: no cover
        e = ImportError('Module "{}" does not define a "{}" attribute/class'.format(module_path, class_name))
        raise e.with_traceback(sys.exc_info()[2])
