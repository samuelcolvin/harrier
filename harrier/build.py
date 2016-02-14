import os
import shutil
import sys
from itertools import chain
from operator import attrgetter

from importlib import import_module
from fnmatch import fnmatch

from .tools import find_all_files
from .common import logger
from .config import Config


def build(config: Config):
    tools = [import_string(t) for t in config.tools]
    all_files = find_all_files(config.root, './')
    logger.debug('{} files in root directory'.format(len(all_files)))

    tools = [t(config) for t in tools]
    tools.sort(key=attrgetter('ownership_priority'), reverse=True)

    extra_files = list(chain(*[t.extra_files for t in tools]))
    logger.debug('{} extra files generated'.format(len(extra_files)))
    all_files += extra_files

    def excluded(fn):
        return not any(fnmatch(fn, m) for m in config.exclude_patterns)

    before_exclude = len(all_files)
    all_files = list(filter(excluded, all_files))

    logger.debug('{} files excluded'.format(before_exclude - len(all_files)))
    logger.debug('{} files to build'.format(len(all_files)))

    for file_path in sorted(all_files):
        for tool in tools:
            if tool.check_ownership(file_path):
                tool.to_build.append(file_path)
                break

    if os.path.exists(config.target_dir):
        # TODO we can do this better, both with config and not remove everything
        shutil.rmtree(config.target_dir)
        logger.info('Deleting target directory {}'.format(config.target_dir))

    tools.sort(key=attrgetter('build_priority'), reverse=True)
    active_tools = [t for t in tools if t.to_build]

    file_count = sum([len(t.to_build) for t in tools])
    tool_str = 'tool' if len(active_tools) == 1 else 'tools'
    logger.info('Building {} files with {} {}'.format(file_count, len(active_tools), tool_str))
    for t in active_tools:
        build_count = t.build()
        logger.debug('built {} files with {}'.format(build_count, t.name))

    for t in active_tools:
        t.cleanup()


def import_string(dotted_path):
    """
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
