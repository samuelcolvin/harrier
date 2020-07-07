import asyncio
import logging
import shutil
from concurrent.futures import ProcessPoolExecutor
from enum import Enum
from pathlib import Path
from typing import Optional, Set, Union

import devtools

from .assets import assets_grablib, get_path_lookup, run_webpack
from .build import build_pages, content_templates
from .common import completed_logger
from .config import Mode, get_config
from .data import load_data
from .dev import adev
from .extensions import apply_modifiers, apply_page_generator
from .render import render_pages

logger = logging.getLogger('harrier.main')
StrPath = Union[str, Path]


class BuildSteps(str, Enum):
    clean = 'clean'
    extensions = 'extensions'
    copy_assets = 'copy_assets'
    pages = 'pages'
    data = 'data'
    sass = 'sass'
    webpack = 'webpack'


ALL_STEPS = [m.value for m in BuildSteps.__members__.values()]


def build(path: StrPath, steps: Set[BuildSteps] = None, mode: Optional[Mode] = None):
    completed_logger.info('building site...')
    config = get_config(path)
    if mode:
        config.mode = mode
    logger.debug('Config: %s', devtools.pformat(config.dict()))

    steps = steps or ALL_STEPS
    if BuildSteps.extensions in steps:
        config = apply_modifiers(config, config.extensions.config_modifiers)

    clean = BuildSteps.clean in steps
    _empty_dir(config.dist_dir, clean)
    _empty_dir(config.get_tmp_dir(), clean)

    pages = None
    data_future = None
    with ProcessPoolExecutor() as executor:
        futures = [
            BuildSteps.sass in steps and executor.submit(assets_grablib, config),
            BuildSteps.webpack in steps and executor.submit(run_webpack, config),
        ]

        if BuildSteps.data in steps:
            data_future = executor.submit(load_data, config)

        if BuildSteps.pages in steps:
            pages = build_pages(config)
        # this will raise errors if any of the above went wrong
        [f.result() for f in futures if f]

    som = dict(
        pages=pages,
        data=data_future and data_future.result(),
        config=config,
    )

    if BuildSteps.extensions in steps:
        apply_page_generator(som, config)

    som['path_lookup'] = get_path_lookup(config, pages)

    if BuildSteps.extensions in steps:
        som = apply_modifiers(som, config.extensions.som_modifiers)

    if som['pages'] is not None:
        content_templates(som['pages'].values(), config)
        render_pages(config, som)
    return som


def dev(path: StrPath, port: int):
    config = get_config(path)
    config.mode = Mode.development
    logger.debug('Config:\n%s', devtools.pformat(config.dict()))

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(adev(config, port))


def _empty_dir(d: Path, clean: bool = True):
    if clean and d.exists():
        shutil.rmtree(d)
    d.mkdir(exist_ok=True, parents=True)
