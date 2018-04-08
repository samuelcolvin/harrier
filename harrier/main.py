import asyncio
import logging
import shutil
from enum import Enum
from pathlib import Path
from typing import Optional, Set, Union

import devtools

from .assets import copy_assets, run_grablib, run_webpack
from .build import build_som, render
from .config import Mode, get_config
from .dev import adev
from .extensions import apply_modifiers

logger = logging.getLogger('harrier.main')
StrPath = Union[str, Path]


class BuildSteps(str, Enum):
    extensions = 'extensions'
    copy_assets = 'copy_assets'
    clean = 'clean'
    pages = 'pages'
    sass = 'sass'
    webpack = 'webpack'


ALL_STEPS = [m.value for m in BuildSteps.__members__.values()]


def build(path: StrPath, steps: Set[BuildSteps]=None, mode: Optional[Mode]=None):
    config = get_config(path)
    if mode:
        config.mode = mode
    logger.debug('Config: %s', devtools.pformat(config.dict()))

    steps = steps or ALL_STEPS
    if BuildSteps.extensions in steps:
        config = apply_modifiers(config, config.extensions.pre_modifiers)

    clean = BuildSteps.clean in steps
    _empty_dir(config.dist_dir, clean)
    _empty_dir(config.get_tmp_dir(), clean)

    # TODO for large webpack and sass probjects, these could be done in parallel
    BuildSteps.copy_assets in steps and copy_assets(config)
    BuildSteps.sass in steps and run_grablib(config)
    BuildSteps.webpack in steps and run_webpack(config)

    if BuildSteps.pages in steps:
        som = build_som(config)

        if BuildSteps.extensions in steps:
            som = apply_modifiers(som, config.extensions.post_modifiers)

        render(config, som)
        return som


def dev(path: StrPath, port: int):
    config = get_config(path)
    config.mode = Mode.development
    logger.debug('Config:\n%s', devtools.pformat(config.dict()))

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    loop = asyncio.get_event_loop()
    loop.run_until_complete(adev(config, port))


def _empty_dir(d: Path, clean: bool=True):
    if clean and d.exists():
        shutil.rmtree(d)
    d.mkdir(exist_ok=True, parents=True)
