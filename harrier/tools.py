import os
import re
from fnmatch import fnmatch

import sass
from jinja2 import Environment, FileSystemLoader, contextfilter

from .config import Config


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
        for file_path in self.to_build:
            for new_file_path, file_content in self.convert_file(file_path):
                new_file_path = new_file_path or self.map_path(file_path)
                target_file = os.path.join(self._config.target_dir, new_file_path)
                target_dir = os.path.dirname(target_file)
                os.makedirs(target_dir, exist_ok=True)
                with open(target_file, 'wb') as f:
                    f.write(file_content)

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


@contextfilter
def static(context, file_name, **kwargs):
    pass


class Jinja(Tool):
    def __init__(self, config):
        super(Jinja, self).__init__(config)
        # TODO custom load which deals with reloading
        self._loader = FileSystemLoader(config.jinja_directories)
        self._env = Environment(loader=self._loader)
        tfs = self._env.list_templates(filter_func=self._filter_template)
        self._template_files = set(['./' + tf for tf in tfs])

    def check_ownership(self, file_path):
        return file_path in self._template_files

    def _filter_template(self, file_path):
        return any(fnmatch(file_path, m) for m in self._config.jinja_patterns)

    # def build(self):
    #     for template in self._env.list_templates(self._filter_template):

    def convert_file(self, file_path):
        yield None, b'testing'
