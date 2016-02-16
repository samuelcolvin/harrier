import os
import shutil
import sys
from copy import copy
from itertools import chain
from operator import attrgetter
from importlib import import_module
from fnmatch import fnmatch

from .common import logger
from .config import Config
from .tools import find_all_files


F_NEW = 10
F_UNCHANGED = 20
F_CHANGED = 40


def build(config, full=True):
    Builder(config).build(full)


class Builder:
    _full = _changed = _future_hash_dict = _extra_files = None

    def __init__(self, config: Config):
        self._config = config
        self._tool_classes = [import_string(t) for t in config.tools]
        self._tool_classes.sort(key=attrgetter('ownership_priority'), reverse=True)
        self._exclude_patterns = self._config.exclude_patterns
        self._hash_dict = {}

    def build(self, full):
        self._full = full
        tools = [t(self._config) for t in self._tool_classes]
        all_files = self._file_list()

        self._extra_files = set(chain(*[t.extra_files for t in tools]))
        logger.debug('{} extra files will be generated'.format(len(self._extra_files)))
        all_files.extend(self._extra_files)

        logger.debug('{} files to build'.format(len(all_files)))

        self._changed = set()
        self._future_hash_dict = {}

        for file_path in sorted(all_files):
            if not self._full and self._file_changed(file_path):
                self._changed.add(file_path)
            for tool in tools:
                if tool.check_ownership(file_path):
                    tool.to_build.append(file_path)
                    break

        if not self._full:
            logger.info('{} files changed or associated with changed files'.format(len(self._changed)))

        tools.sort(key=attrgetter('build_priority'), reverse=True)
        active_tools = [t for t in tools if self._tool_active(t)]
        # TODO possible extra step to remove files from _changed where the tool is not active

        file_count = sum([len(t.to_build) for t in tools])
        tool_str = 'tool' if len(active_tools) == 1 else 'tools'
        logger.info('Building {} files with {} {}'.format(file_count, len(active_tools), tool_str))

        self._delete()

        for t in active_tools:
            if self._full or t.change_sensitive:
                file_paths = t.to_build
            else:
                file_paths = filter(lambda f: f in self._changed, t.to_build)
            build_count = t.build(file_paths)
            logger.debug('built {} files with {}'.format(build_count, t.name))

        for t in active_tools:
            t.cleanup()

        if not self._full:
            # TODO delete stale files here, low priority
            self._hash_dict = copy(self._future_hash_dict)

    def _tool_active(self, tool):
        if self._full:
            return bool(tool.to_build)
        else:
            return any(f in self._changed for f in tool.to_build)

    def _file_changed(self, file_path):
        if file_path in self._extra_files:
            return True

        with open(os.path.join(self._config.root, file_path), 'rb') as f:
            file_hash = hash(f.read())

        # add hash to _future so it can be used on next build
        self._future_hash_dict[file_path] = file_hash

        # check if the file_hash exists in and matches _hash_dict
        return self._hash_dict.get(file_path) == file_hash

    def _file_list(self):
        all_files = find_all_files(self._config.root, './')
        logger.debug('{} files in root directory'.format(len(all_files)))

        before_exclude = len(all_files)
        all_files = list(filter(self._excluded, all_files))
        logger.debug('{} files excluded'.format(before_exclude - len(all_files)))
        return all_files

    def _excluded(self, fn):
        return not any(fnmatch(fn, m) for m in self._exclude_patterns)

    def _delete(self):
        if not os.path.exists(self._config.target_dir):
            return

        if self._full:
            logger.info('Full build, deleting target directory {}'.format(self._config.target_dir))
            shutil.rmtree(self._config.target_dir)


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
