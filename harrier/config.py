import os
import json

import yaml

from .common import HarrierKnownProblem, logger


class Config:
    def __init__(self, config_dict, config_file):
        self.root = config_dict.get('root') or '.'
        self.config_file = config_file
        self.config_dict = config_dict
        self._already_setup = False
        self._base_dir = None
        self._target = None
        self.target_dir = None

    def setup(self, target_name, base_dir=None):
        if self._already_setup:
            return
        full_root = self._set_base_dir(base_dir)
        logger.debug('Full root directory %s exists ✓', full_root)
        self.root = full_root
        self.config_file = os.path.relpath(self.config_file, self.root)
        self._set_target(target_name)
        self._already_setup = True

    def _set_target(self, name):
        # TODO this could be more forgiving, eg. default flag etc.
        target = self.config_dict.get('target') or {}
        self._target = target.get(name)
        if self._target is None:
            for k, v in target.items():
                if v.get(name) is True:
                    self._target = v
                    name = k
                    break
        self._target = self._target or {}
        self._target['name'] = name

        default_paths = {
            'build': 'build',
            'serve': '.serve',
        }

        target_dir = self._target.get('path') or default_paths.get(name, default_paths['serve'])
        self.target_dir = os.path.join(self._base_dir, target_dir)
        if not os.path.exists(os.path.dirname(self.target_dir)):
            raise HarrierKnownProblem('parent of target directory {} does not exist'.format(self.target_dir))
        logger.debug('Output directory set to %s ✓', self.target_dir)

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
        defaults = ['.']
        rel_dirs = self.config_dict.get('jinja_directories') or defaults
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
        defaults = ['*.html', '*.jinja', '*.jinja2']
        return self.config_dict.get('jinja_patterns') or defaults

    @property
    def path_mapping(self):
        defaults = [
            (r'/s[ac]ss/', '/css/'),
            (r'\.s[ac]ss$', '.css'),
            (r'\(.{2,4}\w\).jinja2?$', r'\1'),
            (r'\.jinja2?$', '.html'),
        ]
        # TODO deal better with conf_dict, eg. dicts, list of dicts, check length of lists of lists
        return self.config_dict.get('path_mapping') or defaults

    @property
    def exclude_patterns(self):
        defaults = [
            '*/bower_components/*',
            '*/' + self.config_file,
        ]
        return self.config_dict.get('exclude_patterns') or defaults

    @property
    def tools(self):
        defaults = [
            'harrier.tools.CopyFile',
            'harrier.tools.Sass',
            'harrier.tools.Jinja',
        ]
        return self.config_dict.get('tools') or defaults

    @property
    def context(self):
        # add more things hre like commit sha
        _ctx = {
            'build_target': self._target['name'],
        }
        _ctx.update(self.config_dict.get('context') or {})
        _ctx.update(self._target.get('context') or {})
        return _ctx

    def find_bower(self):
        bc = 'bower_components'
        bdir = self.config_dict.get(bc, bc)
        dirs = [
            os.path.join(self.root, bdir),
            os.path.join(self._base_dir, bdir),
            bdir,
        ]
        for d in dirs:
            if os.path.exists(d):
                logger.debug('Found bower directory {}'.format(d))
                return d

        if bc in self.config_dict:
            raise HarrierKnownProblem('"bower_components" supplied in config but can\'t be found.')


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
        msg = 'no config file supplied and none found with expected names: {}. Using default settings.'
        logger.warning(msg.format(', '.join(DEFAULT_CONFIG_FILES)))
        config = {}
        config_file = './None'
    else:
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
