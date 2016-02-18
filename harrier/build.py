import os
import shutil
from copy import copy
from fnmatch import fnmatch

from .common import logger, HarrierKnownProblem
from .config import Config
from .tool_chain import ToolChainFactory, ToolChain
from .tools import find_all_files


def build(config, partial=False) -> (int, int):
    return Builder(config).build(partial)


class Builder:
    _future_hash_dict = _extra_files = None

    def __init__(self, config: Config):
        self._config = config
        self._gear_box_creator = ToolChainFactory(config)
        self._gear_box_creator.prioritise('ownership_priority')
        self._exclude_patterns = self._config.exclude_patterns
        self._hash_dict = {}
        self._already_built = False
        self._previous_full_build = False

    def build(self, partial=False) -> ToolChain:
        if not partial:
            self._previous_full_build = True
        elif self._previous_full_build:
            raise HarrierKnownProblem('Partial builds are not allowed following full builds with the same builder')

        self._delete(partial)
        self._already_built = True

        tools = self._gear_box_creator(partial)
        all_files = self._file_list()

        self._extra_files = tools.get_extra_files()
        logger.debug('%s extra files will be generated', len(self._extra_files))
        all_files.extend(self._extra_files)

        logger.debug('%s files to build', len(all_files))

        self._future_hash_dict = {}
        files_changed = 0

        for file_path in sorted(all_files):
            changed = self._file_changed(file_path) if partial else True
            files_changed += changed
            for tool in tools:
                if tool.assign_file(file_path, changed):
                    break

        if partial:
            logger.info('%s files changed or associated with changed files', files_changed)

        tools.prioritise('build_priority')
        # TODO possible extra step to remove files from _changed where the tool is not active
        for t in tools:
            tools.run_tool(t)

        tool_str = 'tool' if tools.tools_run == 1 else 'tools'
        file_str = 'file' if tools.files_built == 1 else 'files'
        logger.info('Built %s %s with %s %s', tools.files_built, file_str, tools.tools_run, tool_str)

        for t in tools:
            t.cleanup()  # TODO active

        if partial:
            # TODO delete stale files here, low priority
            self._hash_dict = copy(self._future_hash_dict)
        logger.debug('-' * 20)
        return tools

    def _file_changed(self, file_path):
        if file_path in self._extra_files:
            return True

        with open(os.path.join(self._config.root, file_path), 'rb') as f:
            file_hash = hash(f.read())

        # add hash to _future so it can be used on next build
        self._future_hash_dict[file_path] = file_hash

        # check if the file_hash exists in and matches _hash_dict
        return self._hash_dict.get(file_path) != file_hash

    def _file_list(self):
        all_files = find_all_files(self._config.root, './')
        logger.debug('%s files in root directory', len(all_files))

        before_exclude = len(all_files)
        all_files = list(filter(self._excluded, all_files))
        logger.debug('%s files excluded', before_exclude - len(all_files))
        return all_files

    def _excluded(self, fn):
        return not any(fnmatch(fn, m) for m in self._exclude_patterns)

    def _delete(self, partial):
        if not os.path.exists(self._config.target_dir):
            return

        reason = None
        if not partial:
            reason = 'Full'
        elif not self._already_built:
            reason = 'First'

        if reason:
            logger.info('%s build, deleting target directory %s', reason, self._config.target_dir)
            shutil.rmtree(self._config.target_dir)
