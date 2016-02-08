import os
import re
from fnmatch import fnmatch

import sass
from harrier.common import HarrierKnownProblem
from jinja2 import Environment, FileSystemLoader, contextfilter

from .config import Config


def find_all_files(root, prefix=''):

    def gen():
        for d, _, files in os.walk(root):
            for f in files:
                yield prefix + os.path.relpath(os.path.join(d, f), root)
    return list(gen())


class Tool:
    def __init__(self, config: Config):
        self._config = config
        self.to_build = []

    def check_ownership(self, file_path) -> bool:
        """
        Return true if this converter takes care of the given file_name, else false.

        The convert might also want to record the file to process it later.
        """
        raise NotImplementedError()

    def map_path(self, fp):
        for pattern, replace in self._config.path_mapping:
            fp = re.sub(pattern, replace, fp)
        return fp

    def build(self):
        gen_count = 0
        for file_path in self.to_build:
            for new_file_path, file_content in self.convert_file(file_path):
                new_file_path = new_file_path or self.map_path(file_path)
                target_file = os.path.join(self._config.target_dir, new_file_path)
                target_dir = os.path.dirname(target_file)
                os.makedirs(target_dir, exist_ok=True)
                with open(target_file, 'wb') as f:
                    gen_count += 1
                    f.write(file_content)
        return gen_count

    def convert_file(self, file_path) -> dict:
        """
        generate files this converter is responsible for in the target directory.
        """
        raise NotImplementedError()

    @property
    def name(self):
        return self.__class__.__name__


class CopyFile(Tool):
    def check_ownership(self, file_path):
        return True

    def convert_file(self, file_path):
        full_path = os.path.join(self._config.root, file_path)
        with open(full_path, 'rb') as f:
            yield None, f.read()


class Sass(Tool):
    def check_ownership(self, file_path):
        return any(file_path.endswith(ext) for ext in ['.sass', '.scss'])

    def convert_file(self, file_path):
        full_path = os.path.join(self._config.root, file_path)
        content_str = sass.compile(filename=full_path)
        # TODO cope with maps etc.
        yield None, content_str.encode('utf8')


class Jinja(Tool):
    def __init__(self, config):
        super(Jinja, self).__init__(config)
        # TODO custom load which deals with reloading
        self._loader = FileSystemLoader(config.jinja_directories)
        self._env = Environment(loader=self._loader)
        self._env.filters.update(
            static=self.static
        )

        template_names = self._env.list_templates(filter_func=self._filter_template)
        self._template_files = set(['./' + tf for tf in template_names])
        self._ctx = self._config.context
        self._bower = self._config.find_bower()
        self._bower_files = find_all_files(self._bower) if self._bower else []
        self._extra_files = []

    @contextfilter
    def static(self, context, file_url, **kwargs):
        if file_url.startswith('/'):
            file_path = file_url.lstrip('/')
        else:
            file_dir = os.path.dirname(context.name)
            file_path = os.path.join(file_dir, file_url)

        # TODO might be other places to use this
        file_path = file_path.replace('/./', '/').replace('//', '/')

        target_path = os.path.join(self._config.target_dir, file_path)
        if os.path.exists(target_path):
            return file_url

        mapped_target_path = self.map_path(target_path)
        if os.path.exists(mapped_target_path):
            return self.map_path(file_url)
        # TODO deal with relative file references eg. './whatever.png'

        bower_path = self._find_bower_file(file_url)
        if bower_path is None:
            raise HarrierKnownProblem('unable to find {} in build directory or bower directory'.format(file_path))
        with open(bower_path, 'rb') as f:
            self._extra_files.append((file_path, f.read()))
        return file_path

    def _find_bower_file(self, bower_path):
        bower_path = re.sub('^bower_components/', '', bower_path)
        if bower_path in self._bower_files:
            return os.path.join(self._bower, bower_path)
        for bf in self._bower_files:
            if bf.endswith(bower_path):
                return os.path.join(self._bower, bf)

    def check_ownership(self, file_path):
        return file_path in self._template_files

    def _filter_template(self, file_path):
        return any(fnmatch(file_path, m) for m in self._config.jinja_patterns)

    def convert_file(self, file_path):
        self._extra_files = []
        template = self._env.get_template(file_path)
        content_str = template.render(**self._ctx)
        yield None, content_str.encode('utf8')
        for name, content in self._extra_files:
            yield name, content
