import json
from pathlib import Path
from copy import deepcopy

import yaml
from yaml.scanner import MarkedYAMLError

from .common import HarrierProblem, logger

DEFAULT_CONFIG = Path(__file__).parent.joinpath('harrier.default.yml')


class Config:
    _already_setup = _base_dir = _target = target_dir = served_direct = None

    def __init__(self, config_dict: dict, config_file: Path):
        self._orig_config = config_dict
        self._config = self._prepare_config(config_dict)
        self.config_file = config_file
        self.root = Path(self._config['root'])

    def _prepare_config(self, config):
        with DEFAULT_CONFIG.open() as f:
            c = yaml.load(f)
        unknown = set(config.keys()) - set(c.keys())
        if unknown:
            raise HarrierProblem('Unexpected sections in config: {}'.format(unknown))
        return self._merge_dicts(config, c)

    @classmethod
    def _merge_dicts(cls, d_update:  dict, d_base:  dict):
        d_new = deepcopy(d_base)
        for k, v in d_update.items():
            base_v = d_base.get(k)
            if isinstance(v, dict) and isinstance(base_v, dict):
                d_new[k] = cls._merge_dicts(v, base_v)
            else:
                d_new[k] = v
        return d_new

    def setup(self, target_name, served_direct=False, base_dir=None):
        if self._already_setup:
            return
        full_root = self._set_base_dir(base_dir)
        logger.debug('Full root directory %s exists ✓', full_root)
        self.root = full_root
        self.config_file = self.config_file.relative_to(self._base_dir)
        self._set_target(target_name)
        self._already_setup = True
        self.served_direct = served_direct

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
        self.target_dir = self._base_dir.joinpath(target_dir)
        if not self.target_dir.parent.exists():
            raise HarrierProblem('parent of target directory {} does not exist'.format(self.target_dir))
        logger.debug('Output directory set to %s ✓', self.target_dir)

    def _set_base_dir(self, base_dir):
        self._base_dir = Path(base_dir or self.config_file.parent)
        logger.debug('Setting config root directory relative to {}'.format(self._base_dir))
        try:
            full_root = self._base_dir.joinpath(self.root).resolve()
        except FileNotFoundError:
            if base_dir is None:
                msg = 'config root "{root}" does not exist relative to config file directory "{base_dir}"'
            else:
                msg = 'config root "{root}" does not exist relative to directory "{base_dir}"'
            raise HarrierProblem(msg.format(root=self.root, base_dir=self._base_dir))
        else:
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
            full_dir = self.root.joinpath(rel_dir)
            if not full_dir.exists():
                raise HarrierProblem('"{}" does not exist'.format(full_dir))
            elif not full_dir.is_dir():
                raise HarrierProblem('"{}" is not a directory'.format(full_dir))
            dirs.append(str(full_dir))
        return dirs

    @property
    def jinja_patterns(self):
        return self._get_setting('jinja', 'patterns') + self._get_setting('jinja', 'extra_patterns')

    @property
    def execute_commands(self):
        return self._listify(self._get_setting('execute', 'commands'))

    @property
    def execute_patterns(self):
        return self._listify(self._get_setting('execute', 'patterns'))

    @property
    def execute_cleanup(self):
        cleanup = self._get_setting('execute', 'cleanup')
        return True if cleanup is None else bool(cleanup)

    @property
    def asset_file(self):
        return self._get_setting('assets', 'file')

    @property
    def asset_url_root(self):
        return self._get_setting('assets', 'url_root')

    @property
    def path_mapping(self):
        # TODO deal better with conf_dict, eg. dicts, list of dicts, check length of lists of lists
        # TODO add extra_mapping to avoid overriding these values
        return self._config['mapping']

    @property
    def exclude_patterns(self):
        exclude = set(self._config['exclude'])
        return exclude | set('*/' + e for e in exclude)

    @property
    def tools(self):
        tools = []
        for k, v in self._config.items():
            if isinstance(v, dict) and 'tool_path' in v and v.get('active', False) is True:
                tools.append(v['tool_path'])
        return tools

    @property
    def context(self):
        _ctx = {
            'build_target': self._target['name'],
        }
        _ctx.update(self._config['context'])
        _ctx.update(self._target.get('context') or {})
        return _ctx

    @property
    def subprocesses(self):
        return self._config['subprocesses']

    def find_library(self):
        ldir = self._config['library']
        dirs = [
            self.root.joinpath(ldir),
            self._base_dir.joinpath(ldir),
            Path(ldir),
        ]
        for d in dirs:
            if d.exists():
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


def find_config_file(path=Path('.')):
    logger.debug('looking for config file with default name in "%s"', path.relative_to('.'))
    for default_file in DEFAULT_CONFIG_FILES:
        for fn in path.iterdir():
            if fn.name == default_file:
                logger.info('Found default config file {}'.format(fn.name))
                return fn


def pretty_yaml_dump(obj):
    return yaml.dump(obj, default_flow_style=False)


def pretty_json_dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + '\n'


def yaml_or_json(file_path):
    if any(file_path.endswith(ext) for ext in ['.yaml', '.yml']):
        logger.debug('Processing %s as a yaml file', file_path)
        return yaml.load, pretty_yaml_dump
    elif file_path.endswith('.json'):
        logger.debug('Processing %s as a json file', file_path)
        return json.load, pretty_json_dump
    else:
        msg = 'Unexpected extension for "{}", should be json or yml/yaml'
        raise HarrierProblem(msg.format(file_path))


def load_config(config_file=None) -> Config:
    if config_file:
        config_file = Path(config_file)
        if config_file.is_file():
            file_path = config_file
        else:
            file_path = find_config_file(config_file)
    else:
        file_path = find_config_file()

    if file_path is None:
        msg = 'no config file supplied and none found with expected names: {}. Using default settings.'
        logger.warning(msg.format(', '.join(DEFAULT_CONFIG_FILES)))
        config = {}
        config_file = Path('./None')
    else:
        loader, _ = yaml_or_json(str(file_path))
        with file_path.open() as f:
            try:
                config = loader(f)
            except (MarkedYAMLError, ValueError) as e:
                logger.error('%s: %s', e.__class__.__name__, e)
                raise HarrierProblem('error loading "{}"'.format(file_path)) from e
        config_file = file_path.relative_to('.')
    return Config(config, config_file)
