import re
import shlex
import subprocess
from copy import deepcopy
from fnmatch import fnmatch
from itertools import chain
from pathlib import PurePosixPath, Path

import yaml
import sass
from jinja2 import Environment, FileSystemLoader, contextfilter

from .config import Config, yaml_or_json
from .common import logger, HarrierProblem


def walk(root: Path):
    def gen(p):
        for _p in p.iterdir():
            if _p.is_dir():
                yield from gen(_p)
            else:
                yield _p.relative_to(root)
    return list(gen(root))


def hash_file(path: Path):
    with path.open('rb') as f:
        return hash(f.read())

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)


def parse_front_matter(s):
    m = re.match(FRONT_MATTER_REGEX, s)
    if not m:
        return None, s
    data = yaml.load(m.groups()[0]) or {}
    return data, s[m.end():]


def underscore_prefix(file_path: Path):
    return file_path.name.startswith('_')


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

    def assign_file(self, file_path: Path, changed: bool) -> bool:
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
        return re.match(self.ownership_regex, str(file_path))

    def map_path(self, fp: Path):
        fps = str(fp)
        for pattern, replace in self._config.path_mapping:
            fps = re.sub(pattern, replace, fps)
        return Path(fps)

    def build(self):
        files_built = 0
        source_map = {}
        for file_path in self.to_build:
            source_files = set()
            for new_file_path, file_content in self.convert_file(file_path):
                new_file_path = new_file_path or self.map_path(file_path)
                source_files.add(new_file_path)

                target_file = Path(self._config.target_dir) / new_file_path

                if target_file.exists() and hash(file_content) == hash_file(target_file):
                    continue

                target_file.parent.mkdir(parents=True, exist_ok=True)
                with target_file.open('wb') as f:
                    f.write(file_content)
                files_built += 1
            source_map[file_path] = source_files
            if self.single_call:
                break
        return files_built, source_map

    def convert_file(self, file_path: Path) -> tuple:
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
        # TODO is just str correct here?
        if not self._commands or str(file_path) in self.extra_files:
            return False
        return any(file_path.match(m) for m in self.ownership_patterns)

    def build(self):
        super().build()
        return len(self.extra_files), {}

    def convert_file(self, file_path: Path):
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
                full_path = self._config.root / path
                if not full_path.exists():
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
            self._config.root.joinpath(fp).unlink()

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

    def convert_file(self, file_path: Path):
        path = Path(self._config.root) / file_path
        try:
            path = path.resolve()
        except FileNotFoundError:
            raise HarrierProblem('"{}" does not exist'.format(path))
        else:
            with path.open('rb') as f:
                yield None, f.read()


class Sass(Tool):
    ownership_regex = r'.*\.s(a|c)ss$'
    ownership_priority = 1  # should go early

    def convert_file(self, file_path: Path):
        full_path = self._config.root / file_path
        if underscore_prefix(file_path):
            # sass files starting with underscores are partials and should not be deployed themselves
            return
        try:
            content_str = sass.compile(
                filename=str(full_path),
                precision=self._config.sass_precision,
            )
            print(self._config.sass_precision)
        except sass.CompileError as e:
            error = e.args[0]
            error = error.decode('utf8') if isinstance(error, bytes) else error
            logger.error(error)
            raise HarrierProblem('Error compiling SASS') from e
        # TODO cope with maps etc.
        yield None, content_str.encode('utf8')


class FrontMatterFileSystemLoader(FileSystemLoader):
    content_cache = {}

    def get_source(self, environment, template):
        return self.content_cache[str(template)]

    def parse_source(self, environment, template):
        contents, filename, uptodate = super().get_source(environment, template)
        data, contents = parse_front_matter(contents)
        self.content_cache[template] = (contents, filename, uptodate)
        return data or {}


class Jinja(Tool):
    ownership_priority = 5  # should go early
    build_priority = -8  # should go late
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
        self._library_files = walk(self._library) if self._library else []
        self._extra_files = []

    def _initialise_templates(self):
        template_names = self._env.list_templates(filter_func=self._filter_template)
        self._template_files = set(template_names)
        for t in self._template_files:
            self._file_ctxs[t] = self._loader.parse_source(self._env, t)

    @contextfilter
    def static_file_filter(self, context, file_url, library=None):
        if file_url.startswith('/'):
            file_path = file_url.lstrip('/')
        else:
            file_dir = Path(context.name).parent
            file_path = file_dir / file_url

        if library:
            return self._library_file(file_path, file_url, library)
        else:
            return self._root_file(file_path, file_url)

    def _root_file(self, file_path, file_url):
        target_path = self._config.target_dir / file_path
        if target_path.exists():
            return file_url

        mapped_target_path = self.map_path(target_path)
        if mapped_target_path.exists():
            return self.map_path(file_url)
        raise HarrierProblem('unable to find {} in build directory'.format(file_path))

    def _library_file(self, file_path, file_url, library):
        lib_path = self._find_lib_file(library, file_url)
        if lib_path is None:
            raise HarrierProblem('unable to find {} in library directory, url: {}'.format(library, file_url))

        with lib_path.open('rb') as f:
            self._extra_files.append((str(file_path), f.read()))
        return file_url

    def _find_lib_file(self, file_path, file_url):
        file_path = re.sub('^libs?/', '', file_path)
        if file_path in self._library_files:
            return self._library / file_path
        for lf in self._library_files:
            lfs = str(lf)
            if lfs.endswith(file_path) or (lfs.startswith(file_path) and lfs.endswith(file_url)):
                return self._library / lf

    def _check_ownership(self, file_path):
        return str(file_path) in self._template_files

    def _filter_template(self, file_path):
        return any(fnmatch(file_path, m) for m in self._config.jinja_patterns)

    def convert_file(self, file_path: Path):
        if file_path in self._extra_files:
            return
        self._extra_files = []
        template = self._env.get_template(str(file_path))
        file_ctx = self._file_ctxs[str(file_path)]
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


class AssetDefinition(Tool):
    ownership_priority = 0
    build_priority = -10  # should go last

    def __init__(self, config: Config, partial_build: bool):
        super().__init__(config, partial_build)
        self.to_build = [config.asset_file]
        self.active = True

    @classmethod
    def _get_commit(cls):
        try:
            cp = subprocess.run(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            pass
        else:
            if cp.returncode == 0:
                return cp.stdout.strip('\n')
        return 'unknown'

    def _check_ownership(self, file_path):
        return False

    def convert_file(self, file_path: Path):
        # TODO if this could ever be called more than once for the same target_dir we should cache the result
        _, dumper = yaml_or_json(file_path)
        commit = self._get_commit()
        file_map = {}
        root = UrlPath(self._config.asset_url_root)
        for f in walk(self._config.target_dir):
            # TODO remove file hashes from key once they're implemented
            file_map[str(f)] = str(root / f)
        # TODO, find version from previous deploy, add hash of all files this could be done with
        # modified source_map since hash doesn't have to be correct on partial builds
        obj = {
            'commit': commit,
            'files': file_map,
        }
        content = dumper(obj)
        yield file_path, content.encode('utf8')


class UrlPath(PurePosixPath):
    def __str__(self):
        s = super().__str__()
        # we have to reinstate the second / of http:// as PurePosixPath removes it
        return re.sub('(https?:)/([^/])', r'\1//\2', s)
