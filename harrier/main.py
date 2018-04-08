import asyncio
import logging
import shutil
from enum import Enum
from pathlib import Path
from typing import Set, Union

from .assets import copy_assets, run_grablib, run_webpack
from .build import build_som, render
from .config import get_config
from .dev import adev
from .extensions import apply_modifiers

logger = logging.getLogger('harrier.main')
StrPath = Union[str, Path]


class BuildSteps(str, Enum):
    extensions = 'extensions'
    copy_assets = 'copy_assets'
    pages = 'pages'
    sass = 'sass'
    webpack = 'webpack'


ALL_STEPS = [m.value for m in BuildSteps.__members__.values()]


def build(path: StrPath, steps: Set[BuildSteps]=None):
    config = get_config(path)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug('Config:\n%s', '\n'.join([f'  {k}: {v}' for k, v in config.dict().items()]))

    steps = steps or ALL_STEPS
    if BuildSteps.extensions in steps:
        config = apply_modifiers(config, config.extensions.pre_modifiers)

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    BuildSteps.copy_assets in steps and copy_assets(config)

    if BuildSteps.pages in steps:
        som = build_som(config)

        if BuildSteps.extensions in steps:
            som = apply_modifiers(som, config.extensions.post_modifiers)

        render(config, som)

    BuildSteps.sass in steps and run_grablib(config)
    BuildSteps.webpack in steps and run_webpack(config)


def dev(path: StrPath, port: int):
    config = get_config(path)

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(adev(config, port))


def _empty_dir(d: Path):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
