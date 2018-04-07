import asyncio
import logging
import shutil
from pathlib import Path

from .assets import copy_assets, run_grablib, run_webpack
from .build import build_som, render
from .config import get_config
from .dev import adev
from .extensions import apply_modifiers

logger = logging.getLogger('harrier.main')


def build(path):
    config = get_config(path)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Config:\n%s', '\n'.join([f'  {k}: {v}' for k, v in config.dict().items()]))

    config = apply_modifiers(config, config.extensions.pre_modifiers)
    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    copy_assets(config)
    som = build_som(config)

    som = apply_modifiers(som, config.extensions.post_modifiers)

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
