import logging
from pathlib import Path

from pydantic import BaseSettings, validator

logger = logging.getLogger('harrier')


class HarrierProblem(RuntimeError):
    pass


class Config(BaseSettings):
    source_dir: Path
    site: Path = 'site'
    theme: Path = 'theme'
    data: Path = 'data'

    @validator('site', 'theme', 'data')
    def relative_paths(cls, v, values, **kwargs):
        return values['source_dir'] / v

    @validator('site', 'theme')
    def paths_exist(cls, v, field, **kwargs):
        if v.exists():
            return v
        else:
            raise ValueError(f'{field.name} directory "{v}" does not exist')

    @validator('theme')
    def theme_templates(cls, v):
        if (v / 'templates').exists():
            return v
        else:
            raise ValueError(f'theme directory "{v}" does not contain a "templates" directory')

