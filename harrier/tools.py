import os
import re
import subprocess
import shlex
from copy import deepcopy
from fnmatch import fnmatch
from itertools import chain

import yaml
import sass
from jinja2 import Environment, FileSystemLoader, contextfilter

from .config import Config
from .common import logger, HarrierProblem


def find_all_files(root, prefix=''):

    def gen():
        for d, _, files in os.walk(root):
            for f in files:
                yield prefix + os.path.relpath(os.path.join(d, f), root)
    return list(gen())


def clean_path(p):
    p = re.sub('/\./(\./)+', '/', p)
    return re.sub('//+', '/', p)


def hash_file(path):
    with open(path, 'rb') as f:
        return hash(f.read())

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)


def parse_front_matter(s):
    m = re.match(FRONT_MATTER_REGEX, s)
    if not m:
        return None, s
    data = yaml.load(m.groups()[0]) or {}
    return data, s[m.end():]


def underscore_prefix(file_path):
    return file_path.lstrip('./').startswith('_')


class Tool:
    ownership_regex = None
    # priorities are used to sort tools before ownership check and build, highest comes first.
    ownership_priority = 0
    build_priority = 0
    extra_files = []
    # whether or not one file changing requires a complete rebuild
    change_sensitive = True
    single_call = False

    def __init__(self, config: Config, partial_build: bool):
        self._config = config
        self._partial = partial_build
        self.to_build = []
        self.active = False

    def assign_file(self, file_path: str, changed: bool) -> bool:
        owned = self._check_ownership(file_path)
        if owned and (not self._partial or self.change_sensitive or changed):
            self.active |= changed
            self.to_build.append(file_path)
        return owned

    def _check_ownership(self, file_path):
        """
        Return true if this converter takes care of the given file_name, else false.

        The convert might also want to record the file to process it later.
        """
        return re.match(self.ownership_regex, file_path)

    def map_path(self, fp):
        for pattern, replace in self._config.path_mapping:
            fp = re.sub(pattern, replace, fp)
        return fp

    def build(self):
        files_built = 0
        source_map = {}
        for file_path in self.to_build:
            source_files = set()
            for new_file_path, file_content in self.convert_file(file_path):
                new_file_path = new_file_path or self.map_path(file_path)
                source_files.add(new_file_path)

                target_file = os.path.join(self._config.target_dir, new_file_path)

                if os.path.exists(target_file) and hash(file_content) == hash_file(target_file):
                    continue

                target_dir = os.path.dirname(target_file)
                os.makedirs(target_dir, exist_ok=True)
                with open(target_file, 'wb') as f:
                    f.write(file_content)
                files_built += 1
            source_map[file_path] = source_files
            if self.single_call:
                break
        return files_built, source_map

    def convert_file(self, file_path) -> dict:
        """
        generate files this converter is responsible for in the target directory.
        """
        raise NotImplementedError()

    def cleanup(self):
        pass

    @property
    def name(self):
        return self.__class__.__name__

    def __str__(self):
        return '<{} tool>'.format(self.name)


class Execute(Tool):
    ownership_priority = 10  # should go first
    build_priority = 10  # should go first
    single_call = True  # should be configurable in case command should be run for every file

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._commands = self._config.execute_commands
        self.ownership_patterns = self._config.execute_patterns
        self._extra_files = None

    def _check_ownership(self, file_path):
        if not self._commands or file_path.lstrip('./') in self.extra_files:
            return False
        return any(fnmatch(file_path, m) for m in self.ownership_patterns)

    def build(self):
        super().build()
        return len(self.extra_files), {}

    def convert_file(self, file_path):
        for raw_command in self._commands:
            if isinstance(raw_command, dict):
                generates = raw_command.get('generates', [])
                raw_command = raw_command['command']
            else:
                generates = []
            # TODO do we need any other transforms?
            command = raw_command.format(ROOT=self._config.root)
            args = shlex.split(command)
            # TODO env variables eg. NODE_ENV
            try:
                cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            except FileNotFoundError as e:  # TODO any other exceptions?
                logger.error('%s: %s', e.__class__.__name__, e)
                raise HarrierProblem('problem executing "{}"'.format(command)) from e

            if cp.returncode != 0:
                logger.error('"%s" -> %s', command, cp.stdout.decode('utf8'))
                raise HarrierProblem('command "{}" returned non-zero exit status 1'.format(command))

            for path in generates:
                full_path = os.path.join(self._config.root, path)
                if not os.path.exists(full_path):
                    logger.error('"%s" -> %s', command, cp.stdout.decode('utf8'))
                    raise HarrierProblem('command "{}" failed to generate {}'.format(raw_command, path))

            logger.debug('"%s" -> "%s" ✓', command, cp.stdout.decode('utf8'))
        return
        # noinspection PyUnreachableCode
        yield  # we want an empty generator

    def cleanup(self):
        if not self.active or not self._config.execute_cleanup:
            return

        for fp in self.extra_files:
            d = os.path.join(self._config.root, fp)
            os.remove(d)

    @property
    def extra_files(self):
        if self._extra_files is None:
            generates = [c.get('generates', []) for c in self._commands if isinstance(c, dict)]
            self._extra_files = list(chain(*generates))
        return self._extra_files


class Copy(Tool):
    ownership_regex = r'.*'
    ownership_priority = -10  # should go last
    change_sensitive = False

    def convert_file(self, file_path):
        full_path = os.path.join(self._config.root, file_path)
        if not os.path.isfile(full_path):
            raise HarrierProblem('"{}" does not exist'.format(clean_path(full_path)))
        with open(full_path, 'rb') as f:
            yield None, f.read()


class Sass(Tool):
    ownership_regex = r'.*\.s(a|c)ss$'
    ownership_priority = 1  # should go early

    def convert_file(self, file_path):
        full_path = os.path.join(self._config.root, file_path)
        if underscore_prefix(file_path):
            # sass files starting with underscores are partials and should not be deployed themselves
            return
        try:
            content_str = sass.compile(filename=full_path)
        except sass.CompileError as e:
            logger.error(e.args[0].decode('utf8'))
            raise HarrierProblem('Error compiling SASS') from e
        # TODO cope with maps etc.
        yield None, content_str.encode('utf8')


class FrontMatterFileSystemLoader(FileSystemLoader):
    content_cache = {}

    def get_source(self, environment, template):
        return self.content_cache['./' + template.lstrip('./')]

    def parse_source(self, environment, template):
        contents, filename, uptodate = super().get_source(environment, template)
        data, contents = parse_front_matter(contents)
        self.content_cache[template] = (contents, filename, uptodate)
        return data or {}


class Jinja(Tool):
    ownership_priority = 5  # should go early
    build_priority = -10  # should go last
    _template_files = None
    live_reload_slug = '\n<script src="http://localhost:{}/livereload.js"></script>\n'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO store the loader or env on the tool factory for faster partial builds
        # (this would need to cope with new files)
        self._loader = FrontMatterFileSystemLoader(self._config.jinja_directories)
        self._env = Environment(loader=self._loader)

        self._env.filters['S'] = self.static_file_filter

        self._file_ctxs = {}
        self._initialise_templates()

        self._ctx = self._config.context
        self._library = self._config.find_library()
        self._library_files = find_all_files(self._library) if self._library else []
        self._extra_files = []

    def _initialise_templates(self):
        template_names = self._env.list_templates(filter_func=self._filter_template)
        self._template_files = set(['./' + tf for tf in template_names])
        for t in self._template_files:
            self._file_ctxs[t] = self._loader.parse_source(self._env, t)

    @contextfilter
    def static_file_filter(self, context, file_url, library=None):
        if file_url.startswith('/'):
            file_path = file_url.lstrip('/')
        else:
            file_dir = os.path.dirname(context.name)
            file_path = os.path.join(file_dir, file_url)

        file_path = clean_path(file_path)

        if library:
            return self._library_file(file_path, file_url, library)
        else:
            return self._root_file(file_path, file_url)

    def _root_file(self, file_path, file_url):
        target_path = os.path.join(self._config.target_dir, file_path)
        if os.path.exists(target_path):
            return file_url

        mapped_target_path = self.map_path(target_path)
        if os.path.exists(mapped_target_path):
            return self.map_path(file_url)
        raise HarrierProblem('unable to find {} in build directory'.format(file_path))

    def _library_file(self, file_path, file_url, library):
        lib_path = self._find_lib_file(library, file_url)
        if lib_path is None:
            raise HarrierProblem('unable to find {} in library directory, url: {}'.format(library, file_url))

        with open(lib_path, 'rb') as f:
            self._extra_files.append((file_path, f.read()))
        return file_url

    def _find_lib_file(self, file_path, file_url):
        file_path = re.sub('^libs?/', '', file_path)
        if file_path in self._library_files:
            return os.path.join(self._library, file_path)
        for bf in self._library_files:
            if bf.endswith(file_path) or (bf.startswith(file_path) and bf.endswith(file_url)):
                return os.path.join(self._library, bf)

    def _check_ownership(self, file_path):
        return file_path in self._template_files

    def _filter_template(self, file_path):
        return any(fnmatch(file_path, m) for m in self._config.jinja_patterns)

    def convert_file(self, file_path):
        if file_path in self._extra_files:
            return
        self._extra_files = []
        template = self._env.get_template(file_path)
        file_ctx = self._file_ctxs[file_path]
        ctx = deepcopy(self._ctx)
        ctx.update(file_ctx)
        content_str = template.render(ctx)
        if not underscore_prefix(file_path):
            # to be consistent with sass and allow base templates to not be deployed we ignore files starting
            # with underscores
            if self._config.served_direct and self._config.serve_livereload:
                content_str += self.live_reload_slug.format(self._config.serve_port)
            yield None, content_str.encode('utf8')
        for name, content in self._extra_files:
            yield name, content
