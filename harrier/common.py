import hashlib
import logging
import logging.config
import tempfile
from pathlib import Path
from typing import Any, Dict

import click
from pydantic import BaseSettings, validator

logger = logging.getLogger('harrier')


class HarrierProblem(RuntimeError):
    pass


class Config(BaseSettings):
    source_dir: Path
    pages_dir: Path = 'pages'
    theme_dir: Path = 'theme'
    data_dir: Path = 'data'
    dist_dir: Path = 'dist'
    sass_dir: Path = 'theme'
    theme_assets_dir: Path = 'theme/assets'

    download: Dict[str, Any] = {}
    download_aliases: Dict[str, str] = {}

    defaults: Dict[str, Dict[str, Any]] = {}

    webpack_cli: Path = 'node_modules/.bin/webpack-cli'
    webpack_entry: Path = 'js/index.js'
    webpack_output_path: Path = 'theme'
    webpack_output_filename = 'main.js'
    webpack_config: Path = None
    webpack_run: bool = True

    @validator('source_dir')
    def resolve_source_dir(cls, v):
        return v.resolve(strict=True)

    @validator('pages_dir', 'theme_dir', 'data_dir', 'webpack_cli')
    def relative_paths(cls, v, values, **kwargs):
        return (values['source_dir'] / v).resolve()

    @validator('pages_dir', 'theme_dir')
    def is_dir(cls, v, field, **kwargs):
        if not v.is_dir():
            raise ValueError(f'{field.name} "{v}" is not a directory')
        elif not v.exists():
            raise ValueError(f'{field.name} directory "{v}" does not exist')
        else:
            return v

    @validator('dist_dir')
    def check_dist_dir(cls, v):
        p = Path(v).resolve()
        if not p.parent.exists():
            raise ValueError(f'dist_dir "{p}" parent directory does not exist')
        elif p.exists() and not p.is_dir():
            raise ValueError(f'dist_dir "{p}" is not a directory')
        else:
            return p

    @validator('theme_dir')
    def theme_templates(cls, v):
        if (v / 'templates').exists():
            return v
        else:
            raise ValueError(f'theme directory "{v}" does not contain a "templates" directory')

    @property
    def download_root(self) -> Path:
        return self.theme_dir / 'libs'

    def get_tmp_dir(self) -> Path:
        path_hash = hashlib.md5(b'%s' % self.source_dir).hexdigest()
        return Path(tempfile.gettempdir()) / f'harrier-{path_hash}'

    class Config:
        allow_extra = True


class GrablibHandler(logging.Handler):
    formats = {
        logging.DEBUG: {'fg': 'white', 'dim': True},
        logging.INFO: {'fg': 'white', 'dim': True},
        logging.WARN: {'fg': 'yellow'},
    }

    def get_log_format(self, record):
        return self.formats.get(record.levelno, {'fg': 'red'})

    def emit(self, record):
        log_entry = self.format(record)
        click.secho(log_entry, **self.get_log_format(record))


def log_config(verbose: bool) -> dict:
    if verbose is True:
        log_level = 'DEBUG'
    elif verbose is False:
        log_level = 'WARNING'
    else:
        assert verbose is None
        log_level = 'INFO'
    return {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {
                'format': '%(message)s'
            },
            'server': {
                'format': '[%(asctime)s] %(message)s',
                'datefmt': '%H:%M:%S',
            },
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'grablib.common.ClickHandler',
                'formatter': 'default'
            },
            'grablib': {
                'level': 'INFO' if verbose else 'WARNING',
                'class': 'harrier.common.GrablibHandler',
                'formatter': 'default'
            },
            'server_logging': {
                'level': log_level,
                'class': 'aiohttp_devtools.runserver.log_handlers.AuxiliaryHandler',
                'formatter': 'server'
            },
        },
        'loggers': {
            logger.name: {
                'handlers': ['default'],
                'level': log_level,
            },
            'grablib': {
                'handlers': ['grablib'],
                'level': log_level,
            },
            'adev.server.aux': {
                'handlers': ['server_logging'],
                'level': log_level,
            },
        },
    }


def setup_logging(verbose):
    config = log_config(verbose)
    logging.config.dictConfig(config)
