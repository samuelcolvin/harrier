import shutil
from itertools import product
from pathlib import Path

import yaml
from jinja2 import Environment
from yaml.error import YAMLError

from .common import Config, HarrierProblem, logger
from .som import build_som

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


def build(config_file):
    config_path = Path(config_file)
    if config_path.is_file():
        raw_config = load_config_file(config_path)
    else:
        try:
            config_path = next(config_path / f for f in CONFIG_FILE_TRIES if (config_path / f).exists())
        except StopIteration:
            raw_config = {'source_dir': config_path}
        else:
            raw_config = load_config_file(config_path)

    config = Config(**raw_config)

    som = build_som(config)
    render(som)


def render(som: dict):
    def page_gen(d: dict):
        for v in d.values():
            if '__file__' in v:
                if v.get('outfile'):
                    yield v
            else:
                yield from page_gen(v)
    dist_dir: Path = som['dist_dir']
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    env: Environment = som.pop('jinja_env')
    for p in page_gen(som['pages']):
        outfile: Path = p['outfile'].resolve()
        # this will raise an exception if somehow outfile is outside dis_dir
        outfile.relative_to(dist_dir)
        outfile.parent.mkdir(exist_ok=True, parents=True)
        if 'template' in p:
            template = env.get_template(p['template'])
            rendered = template.render(page=p, site=som)
            outfile.write_text(rendered)
        else:
            shutil.copy(p['infile'], outfile)
