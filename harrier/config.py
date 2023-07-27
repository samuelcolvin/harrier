import hashlib
import logging
import tempfile
from datetime import datetime
from enum import Enum
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Extra, field_validator
from ruamel.yaml import YAMLError

from .common import HarrierProblem, PathMatch, yaml
from .extensions import Extensions

logger = logging.getLogger('harrier.config')
CONFIG_FILE_TRIES = 'harrier', 'config', '_config'
CONFIG_FILE_TRIES = [Path(f'{name}.{ext}') for name, ext in product(CONFIG_FILE_TRIES, ['yml', 'yaml'])]


class Mode(str, Enum):
    development = 'development'
    production = 'production'


class WebpackConfig(BaseModel):
    cli: Path = None
    entry: Optional[Path] = 'js/index.js'
    output_path: Path = 'theme'
    dev_output_filename: Optional[str] = '[name].js'
    prod_output_filename: Optional[str] = '[name].[hash].js'
    config: Path = None
    run: bool = True

    class Config:
        validate_all = True


class Config(BaseModel, extra=Extra.allow):
    source_dir: Path = Path('/')
    config_path: Union[Path, None] = None
    mode: Mode = Mode.production
    pages_dir: Path = Path('pages')
    extensions: Extensions = 'extensions.py'
    theme_dir: Path = Path('theme')
    data_dir: Path = Path('data')

    dist_dir: Path = Path('dist')
    dist_dir_sass: Path = Path('theme')
    dist_dir_assets: Path = Path('.')
    tmp_dir: Union[Path, None] = None

    download: Dict[str, Any] = {}
    download_aliases: Dict[str, str] = {}

    default_template: Optional[str] = None
    paginate_by: int = 20
    apply_trailing_slash: bool = True
    defaults: Dict[PathMatch, Dict[str, Any]] = {}
    ignore: List[PathMatch] = []
    no_hash: List[PathMatch] = ['/favicon.???']

    webpack: WebpackConfig = WebpackConfig()
    build_time: Union[datetime, None] = None

    @field_validator('source_dir')
    def resolve_source_dir(cls, v):
        return v.resolve(strict=True)

    @field_validator('pages_dir', 'theme_dir', 'data_dir')
    def resolve_relative_paths(cls, v, info):
        return (info.data['source_dir'] / v).resolve()

    @field_validator('pages_dir')
    def is_dir(cls, v, info):
        if not v.exists():
            raise ValueError(f'{info.field_name} directory "{v}" does not exist')
        elif not v.is_dir():
            raise ValueError(f'{info.field_name} "{v}" is not a directory')
        else:
            return v

    @field_validator('dist_dir')
    def check_dist_dir(cls, p, info):
        if not p.is_absolute():
            p = (info.data['source_dir'] / p).resolve()
        if not p.parent.exists():
            raise ValueError(f'dist_dir "{p}" parent directory does not exist')
        elif p.exists() and not p.is_dir():
            raise ValueError(f'dist_dir "{p}" is not a directory')
        else:
            return p

    @field_validator('default_template')
    def theme_templates(cls, v, info):
        templates_dir = info.data['theme_dir'] / 'templates'
        if not v or templates_dir.is_dir():
            return v
        else:
            raise ValueError(f'default-template set but template directory "{templates_dir}" does not exist')

    @field_validator('extensions', mode='before')
    def validate_extensions(cls, v, info):
        p = info.data['source_dir'] / v
        if p.exists() and not p.is_file():
            raise ValueError('"extensions" should be a python file, not directory')
        else:
            return p

    @field_validator('webpack')
    def validate_webpack(cls, v, info):
        webpack: WebpackConfig = v
        if not webpack.run:
            return webpack

        if {'source_dir', 'theme_dir', 'source_dir', 'dist_dir'} - info.data.keys():
            # some values are missing, can't validate properly
            return webpack

        if webpack.cli is None:
            default_cli = info.data['source_dir'] / 'node_modules/.bin/webpack-cli'
            if default_cli.exists():
                webpack.cli = default_cli
        elif not webpack.cli.is_absolute():
            webpack.cli = info.data['source_dir'] / webpack.cli

        if not webpack.cli:
            webpack.run = False
        elif not webpack.cli.exists():
            raise ValueError(f'webpack cli path set but does not exist "{webpack.cli}", not running webpack')

        if webpack.config:
            webpack.config = info.data['source_dir'] / webpack.config
            if not webpack.config.exists():
                raise ValueError(f'webpack config set but does not exist "{webpack.config}", not running webpack')
            logger.info('webpack config file found')
        else:
            webpack.entry = info.data['theme_dir'] / webpack.entry
            if not webpack.entry.exists() and webpack.run:
                logger.warning('webpack entry point "%s" does not exist, not running webpack', webpack.entry)
                webpack.run = False
            webpack.output_path = info.data['dist_dir'] / webpack.output_path
        return webpack

    @field_validator('build_time', mode='before')
    def set_build_time(cls, v):
        return datetime.utcnow()

    def get_tmp_dir(self) -> Path:
        if self.tmp_dir:
            return self.tmp_dir
        else:
            path_hash = hashlib.md5(b'%s' % self.source_dir).hexdigest()
            return Path(tempfile.gettempdir()) / f'harrier-{path_hash}'

    model_config = ConfigDict(validate_default=True, arbitrary_types_allowed=True)


def load_config_file(config_path: Path):
    try:
        raw_config = yaml.load(config_path.read_text()) or {}
    except YAMLError as e:
        logger.error('%s: %s', e.__class__.__name__, e)
        raise HarrierProblem(f'error loading "{config_path}"') from e
    raw_config.setdefault('source_dir', config_path.parent)
    raw_config.setdefault('config_path', config_path.resolve())
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
