import asyncio
import shutil
from itertools import product
from pathlib import Path

import yaml
from jinja2 import Environment
from misaka import Markdown, HtmlRenderer
from yaml.error import YAMLError

from .assets import run_grablib, run_webpack
from .common import Config, HarrierProblem, logger
from .som import build_som
from .dev import adev

CONFIG_FILE_TRIES = 'harrier', 'config', '_config'
CONFIG_FILE_TRIES = [Path(f'{name}.{ext}') for name, ext in product(CONFIG_FILE_TRIES, ['yml', 'yaml'])]


def load_config_file(config_path: Path):
    try:
        raw_config = yaml.load(config_path.read_text()) or {}
    except YAMLError as e:
        logger.error('%s: %s', e.__class__.__name__, e)
        raise HarrierProblem(f'error loading "{config_path}"') from e
    raw_config.setdefault('source_dir', config_path.parent)
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


def build(path):
    config = get_config(path)

    _empty_dir(config.dist_dir)
    _empty_dir(config.get_tmp_dir())

    som = build_som(config)
    render(som)
    run_grablib(config)
    run_webpack(config)


def dev(path, port):
    config = get_config(path)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(adev(config, port))


def _empty_dir(d: Path):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)


def _page_gen(d: dict):
    for v in d.values():
        if '__file__' in v:
            if v.get('outfile'):
                yield v
        else:
            yield from _page_gen(v)


def render(som: dict):
    dist_dir: Path = som['dist_dir']

    rndr = HtmlRenderer()
    md = Markdown(rndr)

    env: Environment = som.pop('jinja_env')
    gen, copy = 0, 0
    for p in _page_gen(som['pages']):
        outfile: Path = p['outfile'].resolve()
        # this will raise an exception if somehow outfile is outside dis_dir
        outfile.relative_to(dist_dir)
        outfile.parent.mkdir(exist_ok=True, parents=True)
        infile: Path = p['infile']
        if 'template' in p:
            template_file = p['template']
            try:
                if p['render']:
                    content_template = env.get_template(str(p['content_template']))
                    content = content_template.render(page=p, site=som)
                else:
                    content = p.pop('content')

                if infile.suffix == '.md':
                    content = md(content)

                if template_file:
                    template = env.get_template(template_file)
                    rendered = template.render(content=content, page=p, site=som)
                else:
                    rendered = content
            except Exception as e:
                logger.error('%s: %s %s', infile, e.__class__.__name__, e)
                raise
            else:
                gen += 1
                outfile.write_text(rendered)
        else:
            copy += 1
            shutil.copy(infile, outfile)
    logger.info('generated %d files, copied %d files', gen, copy)
