import os
import json

import yaml

from .common import HarrierKnownProblem, logger


class Config:
    def __init__(self, config_dict, config_file):
        self.root = config_dict['root']
        self.config_file = config_file
        self.config_dict = config_dict
        self._already_setup = False
        self._base_dir = None
        self._output = None
        self.output_dir = None

    def setup(self, output_name, base_dir=None):
        if self._already_setup:
            return
        full_root = self._set_base_dir(base_dir)
        logger.debug('Full root directory %s exists ✓', full_root)
        self.root = full_root
        self.config_file = os.path.relpath(self.config_file, self.root)
        self._set_output(output_name)
        self._already_setup = True

    def _set_output(self, name):
        # TODO this could be more forgiving, eg. default flag etc.
        self._output = self.config_dict['output'][name]
        output_dir = self._output.get('path') or name
        self.output_dir = os.path.join(self._base_dir, output_dir)
        if not os.path.exists(os.path.dirname(self.output_dir)):
            raise HarrierKnownProblem('parent of output directory {} does not exist'.format(self.output_dir))
        logger.debug('Output directory set to %s ✓', self.output_dir)

    def _set_base_dir(self, base_dir):
        self._base_dir = base_dir or os.path.dirname(self.config_file)
        logger.debug('Setting config root directory relative to {}'.format(self._base_dir))
        full_root = os.path.join(self._base_dir, self.root)
        if not os.path.exists(full_root):
            if base_dir is None:
                msg = 'config root "{root}" does not exist relative to config file directory "{base_dir}"'
            else:
                msg = 'config root "{root}" does not exist relative to directory "{base_dir}"'
            raise HarrierKnownProblem(msg.format(root=self.root, base_dir=self._base_dir))
        return full_root

    @property
    def jinja_directories(self):
        default = ['.']
        rel_dirs = self.config_dict.get('jinja_directories') or default
        dirs = []
        for rel_dir in rel_dirs:
            full_dir = os.path.join(self.root, rel_dir)
            if not os.path.exists(full_dir):
                raise HarrierKnownProblem('"{}" does not exist'.format(full_dir))
            elif not os.path.isdir(full_dir):
                raise HarrierKnownProblem('"{}" is not a directory'.format(full_dir))
            dirs.append(full_dir)
        return dirs

    @property
    def jinja_patterns(self):
        default = ['*.html', '*.jinja', '*.jinja2']
        return self.config_dict.get('jinja_patterns') or default

    @property
    def path_mapping(self):
        default = [
            (r'/s[ac]ss/', '/css/'),
            (r'\.s[ac]ss$', '.css'),
            (r'\.jinja2?$', '.html'),
        ]
        # TODO deal better with conf_dict, eg. dicts, list of dicts, check length of lists of lists
        return self.config_dict.get('path_mapping') or default

    @property
    def exclude_patterns(self):
        default = [
            '*/bower_components/*',
            '*/' + self.config_file,
        ]
        return self.config_dict.get('exclude_patterns') or default

    @property
    def tools(self):
        default = [
            'harrier.tools.CopyFile',
            'harrier.tools.Sass',
            'harrier.tools.Jinja',
        ]
        return self.config_dict.get('tools') or default


# in order if preference:
DEFAULT_CONFIG_FILES = [
    'harrier.yml',
    'harrier.json',
    'config.yml',
    'config.json',
]


def find_config_file(path='.'):
    logger.debug('looking for config file with default name in "%s"', os.path.realpath(path))
    for default_file in DEFAULT_CONFIG_FILES:
        for fn in os.listdir(path):
            if fn == default_file:
                logger.info('Found default config file {}'.format(fn))
                return fn


def load_config(config_file) -> Config:
    if config_file:
        if os.path.isfile(config_file):
            file_path = config_file
        else:
            file_path = find_config_file(config_file)
    else:
        file_path = find_config_file()

    if file_path is None:
        names = ', '.join(DEFAULT_CONFIG_FILES)
        raise HarrierKnownProblem('no config file supplied and none found with expected names: {}'.format(names))

    if any(file_path.endswith(ext) for ext in ['.yaml', '.yml']):
        logger.debug('Processing %s as a yaml file', file_path)
        loader = yaml.load
    elif file_path.endswith('.json'):
        logger.debug('Processing %s as a json file', file_path)
        loader = json.load
    else:
        msg = 'Unexpected extension for config file: "{}", should be json or yml/yaml'
        raise HarrierKnownProblem(msg.format(file_path))
    with open(file_path) as f:
        config = loader(f)
    # TODO: cerberus test of config shape
    config_file = os.path.realpath(file_path)
    return Config(config, config_file)
