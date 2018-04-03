import re
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import validator, BaseModel

from .common import Config

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)
# extensions where we want to do anything except just copy the file to the output dir
ACTIVE_EXT = {'.html', '.md'}


class FileData(BaseModel):
    title: str
    lastmod: datetime
    slug: str = ''
    output: bool = True

    @validator('slug', always=True)
    def set_slug(cls, v, values, **kwargs):
        if v:
            # TODO perhaps validate this is a valid slug
            return v
        name = values['title'].replace(' ', '-').lower()
        name = re.sub('[^a-z0-9\-]', '', name)
        return re.sub('-{2,}', '-', name)


def build_som(config: Config):
    def build_dir(paths):
        d = {}
        for name, p in paths:
            if isinstance(p, Path):
                active = p.suffix in ACTIVE_EXT
                data = {
                    'title': p.stem,
                    'lastmod': p.stat().st_mtime
                }
                if active:
                    fm_data, content = parse_front_matter(p.read_text())
                    fm_data and data.update(fm_data)
                file_data = FileData(**data)
                d[name] = {
                    'path': p,
                    'active': active,
                    'data': file_data.dict(),
                }
            else:
                d[name] = build_dir(p)
        return d

    som = build_dir(walk(config.site))
    debug(som)


def walk(path: Path, _root: Path=None):
    root = _root or path
    for p in sorted(path.iterdir(), key=lambda p_: (p_.is_dir(), p_.name)):
        yield p.name, walk(p, root) if p.is_dir() else p.resolve()


def parse_front_matter(s):
    m = re.match(FRONT_MATTER_REGEX, s)
    if not m:
        return None, s
    data = yaml.load(m.groups()[0]) or {}
    return data, s[m.end():]
