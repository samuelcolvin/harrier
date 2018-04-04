import logging
from pathlib import Path

from pydantic import BaseSettings, validator

logger = logging.getLogger('harrier')


class HarrierProblem(RuntimeError):
    pass


class Config(BaseSettings):
    source_dir: Path
    pages_dir: Path = 'pages'
    theme_dir: Path = 'theme'
    data_dir: Path = 'data'

    default_templates = 'main.jinja'

    @validator('pages_dir', 'theme_dir', 'data_dir')
    def relative_paths(cls, v, values, **kwargs):
        return values['source_dir'] / v

    @validator('pages_dir', 'theme_dir')
    def paths_exist(cls, v, field, **kwargs):
        if v.exists():
            return v
        else:
            raise ValueError(f'{field.name} directory "{v}" does not exist')

    @validator('theme_dir')
    def theme_templates(cls, v):
        if (v / 'templates').exists():
            return v
        else:
            raise ValueError(f'theme directory "{v}" does not contain a "templates" directory')

    class Config:
        allow_extra = True
