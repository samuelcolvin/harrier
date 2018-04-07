import asyncio
import logging
import shutil
from itertools import product
from pathlib import Path

import yaml
from yaml.error import YAMLError

from .assets import copy_assets, run_grablib, run_webpack
from .common import Config, HarrierProblem
from .build import build_som, render
from .dev import adev

CONFIG_FILE_TRIES = 'harrier', 'config', '_config'
CONFIG_FILE_TRIES = [Path(f'{name}.{ext}') for name, ext in product(CONFIG_FILE_TRIES, ['yml', 'yaml'])]
logger = logging.getLogger('harrier.main')


def load_config_file(config_path: Path):
    try:
        raw_config = yaml.load(config_path.read_text()) or {}
    except YAMLError as e:
        logger.error('%s: %s', e.__class__.__name__, e)
        raise HarrierProblem(f'error loading "{config_path}"') from e
    raw_config.setdefault('source_dir', config_path.parent)
    return raw_config


def get_config(path) -> Config:
    config_path = Path(path)
    if config_path.is_file():
        config = load_config_file(config_path)
    else:
        try:
            config_path = next(config_path / f for f in CONFIG_FILE_TRIES if (config_path / f).exists())
        except StopIteration:
            config = {'source_dir': config_path}
        else:
            config = load_config_file(config_path)

    return Config(**config)


def build(path):
    config = get_config(path)
    logger.debug('Config: %s', config)

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    copy_assets(config)
    som = build_som(config)
    render(config, som)
    run_grablib(config)
    run_webpack(config)


def dev(path, port):
    config = get_config(path)

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(adev(config, port))


def _empty_dir(d: Path):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
