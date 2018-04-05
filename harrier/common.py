import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

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
    sass_dir: Path = 'styles/css'

    download: Dict[str, Any] = {}
    download_aliases: Dict[str, str] = {}

    defaults: Dict[str, Dict[str, Any]] = {}

    webpack_cli: Path = 'node_modules/.bin/webpack-cli'
    webpack_entry: Path = 'js/index.js'
    webpack_output_path: Path = 'styles/js'
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

    class Config:
        allow_extra = True


def log_config(log_level: str) -> dict:
    """
    Setup default config. for dictConfig.
    :param log_level: str name or django debugging int
    :return: dict suitable for ``logging.config.dictConfig``
    """
    assert log_level in {'DEBUG', 'INFO', 'WARNING', 'ERROR'}, 'wrong log level %s' % log_level
    return {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {'format': '%(message)s'},
            'indent': {'format': '    %(message)s'},
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'grablib.common.ClickHandler',
                'formatter': 'default'
            },
            'progress': {
                'level': log_level,
                'class': 'grablib.common.ProgressHandler',
                'formatter': 'indent'
            },
        },
        'loggers': {
            logger.name: {
                'handlers': ['default'],
                'level': log_level,
                'propagate': False,
            },
            'grablib.main': {
                'handlers': ['default'],
                'level': log_level,
                'propagate': False,
            },
            'grablib.progress': {
                'handlers': ['progress'],
                'level': log_level,
                'propagate': False,
            },
        },
    }


def setup_logging(log_level):
    config = log_config(log_level)
    logging.config.dictConfig(config)
