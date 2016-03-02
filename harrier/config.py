import os
import json
from copy import deepcopy

import yaml
from yaml.scanner import MarkedYAMLError

from .common import HarrierProblem, logger

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), 'harrier.default.yml')


class Config:
    _already_setup = _base_dir = _target = target_dir = live = None

    def __init__(self, config_dict, config_file):
        self._orig_config = config_dict
        self._config = self._prepare_config(config_dict)
        self.config_file = config_file
        self.root = self._config['root']

    def _prepare_config(self, config):
        with open(DEFAULT_CONFIG) as f:
            c = yaml.load(f)
        unknown = set(config.keys()) - set(c.keys())
        if unknown:
            raise HarrierProblem('Unexpected sections in config: {}'.format(unknown))
        c.update(config)
        return c

    def setup(self, target_name, live=False, base_dir=None):
        if self._already_setup:
            return
        full_root = self._set_base_dir(base_dir)
        logger.debug('Full root directory %s exists ✓', full_root)
        self.root = full_root
        self.config_file = os.path.relpath(self.config_file, self.root)
        self._set_target(target_name)
        self._already_setup = True
        self.live = live

    def _set_target(self, name):
        target = self._config['target']
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
            raise HarrierProblem('parent of target directory {} does not exist'.format(self.target_dir))
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
            raise HarrierProblem(msg.format(root=self.root, base_dir=self._base_dir))
        return full_root

    def _get_setting(self, *args):

        def find_property(d, key_list):
            # TODO show more helpful errors eg if v is a string and v.get is called.
            v = deepcopy(d)
            for k in key_list:
                v = v.get(k)
                if v is None:
                    return
            return v

        target_prop = find_property(self._target, args)
        if target_prop is not None:
            return target_prop
        return find_property(self._config, args)

    @property
    def serve_port(self):
        return self._target.get('port') or 8000

    @property
    def serve_livereload(self):
        return self._target.get('livereload', True)

    @property
    def jinja_directories(self):
        rel_dirs = self._listify(self._get_setting('jinja', 'directories'))
        dirs = []
        for rel_dir in rel_dirs:
            full_dir = os.path.join(self.root, rel_dir)
            if not os.path.exists(full_dir):
                raise HarrierProblem('"{}" does not exist'.format(full_dir))
            elif not os.path.isdir(full_dir):
                raise HarrierProblem('"{}" is not a directory'.format(full_dir))
            dirs.append(full_dir)
        return dirs

    @property
    def jinja_patterns(self):
        return self._get_setting('jinja', 'patterns')

    @property
    def execute_commands(self):
        return self._listify(self._get_setting('execute', 'commands'))

    @property
    def execute_patterns(self):
        return self._listify(self._get_setting('execute', 'patterns'))

    @property
    def execute_generates(self):
        return self._listify(self._get_setting('execute', 'generates'))

    @property
    def execute_cleanup(self):
        cleanup = self._get_setting('execute', 'cleanup')
        return True if cleanup is None else bool(cleanup)

    @property
    def path_mapping(self):
        # TODO deal better with conf_dict, eg. dicts, list of dicts, check length of lists of lists
        # TODO add extra_mapping to avoid overriding these values
        return self._config['mapping']

    @property
    def exclude_patterns(self):
        return self._config['exclude']

    @property
    def tools(self):
        return self._config['tools']

    @property
    def context(self):
        # TODO add more things hre like commit sha
        _ctx = {
            'build_target': self._target['name'],
        }
        _ctx.update(self._config['context'] or {})
        _ctx.update(self._target.get('context') or {})
        return _ctx

    def find_library(self):
        ldir = self._config.get('library')
        dirs = [
            os.path.join(self.root, ldir),
            os.path.join(self._base_dir, ldir),
            ldir,
        ]
        for d in dirs:
            if os.path.exists(d):
                logger.debug('Found library directory {}'.format(d))
                return d

        if 'library' in self._orig_config:
            raise HarrierProblem("library supplied in config but can't be found.")
        else:
            logger.debug('unable to find library directory, ignoring as library was not supplied in config')

    def _listify(self, v):
        if isinstance(v, str):
            return [v]
        return list(v or [])


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


def load_config(config_file=None) -> Config:
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
            raise HarrierProblem(msg.format(file_path))
        with open(file_path) as f:
            try:
                config = loader(f)
            except (MarkedYAMLError, ValueError) as e:
                logger.error('%s: %s', e.__class__.__name__, e)
                raise HarrierProblem('error loading "{}"'.format(file_path)) from e
        config_file = os.path.realpath(file_path)
    return Config(config, config_file)
