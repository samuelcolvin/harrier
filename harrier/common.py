import logging
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

    defaults: Dict[str, Dict[str, Any]] = {}

    @validator('pages_dir', 'theme_dir', 'data_dir')
    def relative_paths(cls, v, values, **kwargs):
        return values['source_dir'] / v

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

    class Config:
        allow_extra = True
