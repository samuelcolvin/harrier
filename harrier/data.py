import csv
import json
import logging
import re
from pathlib import Path
from time import time

from ruamel.yaml import YAMLError

from .common import HarrierProblem, log_complete, yaml
from .config import Config

logger = logging.getLogger('harrier.data')
csv_dialect = csv.excel
csv_dialect.skipinitialspace = True


def load_data(config: Config):
    start = time()
    d = config.data_dir
    if not d.is_dir():
        return None
    ext_lookup = {
        '.json': read_json,
        '.csv': read_csv,
        '.yaml': read_yaml,
        '.yml': read_yaml,
    }
    data = {}
    count = 0
    for ext in ext_lookup:
        for p in d.glob(f'**/*{ext}'):
            key = re.sub('[-/ ]', '_', str(p.relative_to(d).with_suffix('')))
            key = re.sub('\W', '', key)
            if key in data:
                logger.warning('duplicate data key "%s", ignoring data in "%s", please rename', key, p)
                continue
            logger.debug('reading data from "%s" as "%s"', p, key)
            try:
                data[key] = ext_lookup[p.suffix](p)
            except (ValueError, YAMLError) as e:
                raise HarrierProblem(f'error reading {p} {e.__class__.__name__}: {e}') from e
            count += 1
    log_complete(start, 'data loaded', count)
    return data


def read_json(p: Path):
    with p.open() as f:
        return json.load(f)


def read_csv(p: Path):
    with p.open(newline='') as f:
        reader = csv.DictReader(f, dialect=csv_dialect, restval='other')
        return [dict(r) for r in reader]


def read_yaml(p: Path):
    return yaml.load(p.read_text())
