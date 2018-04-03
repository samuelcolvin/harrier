from itertools import product
from pathlib import Path

import yaml
from yaml.error import YAMLError

from .common import Config, HarrierProblem, logger
from .som import build_som

CONFIG_FILE_TRIES = 'harrier', 'config', '_config'
CONFIG_FILE_TRIES = [Path(f'{name}.{ext}') for name, ext in product(CONFIG_FILE_TRIES, ['yml', 'yaml'])]


def load_config_file(config_path: Path):
    try:
        raw_config = yaml.load(config_path.read_text()) or {}
    except YAMLError as e:
        logger.error('%s: %s', e.__class__.__name__, e)
        raise HarrierProblem(f'error loading "{config_path}"') from e
    raw_config.setdefault('source_dir', config_path.parent)
    return raw_config


def build(config_file):
    config_path = Path(config_file)
    if config_path.is_file():
        raw_config = load_config_file(config_path)
    else:
        try:
            config_path = next(config_path / f for f in CONFIG_FILE_TRIES if (config_path / f).exists())
        except StopIteration:
            raw_config = {'source_dir': config_path}
        else:
            raw_config = load_config_file(config_path)

    config = Config(**raw_config)

    debug(config.dict())
    build_som(config)
