import os
import shutil
import sys

from importlib import import_module
from fnmatch import fnmatch

from .common import logger
from .config import Config


def _get_all_files(root):
    for d, _, files in os.walk(root):
        for f in files:
            yield './' + os.path.relpath(os.path.join(d, f), root)


def build(config: Config):
    tools = [import_string(t) for t in config.tools]
    tools.reverse()
    all_files = list(_get_all_files(config.root))
    logger.debug('{} files in root directory'.format(len(all_files)))
    excluded_patterns = config.exclude_patterns

    def excluded(fn):
        return not any(fnmatch(fn, m) for m in excluded_patterns)

    all_files = list(filter(excluded, all_files))
    logger.debug('{} files to build after initial exclusion'.format(len(all_files)))

    tools = [t(config) for t in tools]

    for file_path in sorted(all_files):
        for tool in tools:
            if tool.check_ownership(file_path):
                tool.to_build.append(file_path)
                break

    if os.path.exists(config.output_dir):
        # TODO we can do this better, both with config and not remove everything
        shutil.rmtree(config.output_dir)
        logger.info('Deleting output directory {}'.format(config.output_dir))

    tools.reverse()
    file_count = sum([len(t.to_build) for t in tools])
    active_tools = [t for t in tools if t.to_build]
    tool_str = 'tool' if len(active_tools) == 1 else 'tools'
    logger.info('Building {} files with {} {}'.format(file_count, len(active_tools), tool_str))
    for t in active_tools:
        logger.debug('building {} files with {}...{}'.format(len(t.to_build), t.name, t.to_build))
        t.build()


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        e = ImportError("{} doesn't look like a module path".format(dotted_path))
        raise e.with_traceback(sys.exc_info()[2])

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        e = ImportError('Module "{}" does not define a "{}" attribute/class'.format(module_path, class_name))
        raise e.with_traceback(sys.exc_info()[2])
