import re
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel, ValidationError, validator

from .common import Config, HarrierProblem

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)
# extensions where we want to do anything except just copy the file to the output dir
ACTIVE_EXT = {'.html', '.md'}
URI_NOT_ALLOWED_REGEX = re.compile(r'[^a-zA-Z0-9_\-/.]')
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')


def build_som(config: Config):
    def build_dir(paths, *parents):
        d = {}
        for name, p in paths:
            if not isinstance(p, Path):
                d[name] = build_dir(p, *parents, name)
                continue

            render = p.suffix in ACTIVE_EXT
            data = {
                'path': p,
                'ext': p.suffix and p.suffix[1:],
                'render': render,
            }
            name = p.stem if render else name

            date_match = DATE_REGEX.match(name)
            if date_match:
                *date_args, new_name = date_match.groups()
                created = datetime(*map(int, date_args))
                name = new_name or name
            else:
                created = p.stat().st_mtime
            data.update(title=name, slug=slugify(name), created=created)

            if render:
                fm_data, content = parse_front_matter(p.read_text())
                data['content'] = content
                fm_data and data.update(fm_data)

            try:
                fd = FileData(**data)
            except ValidationError as e:
                raise HarrierProblem(f'{p}: {e}') from e

            if not fd.uri:
                fd.uri = '/' + '/'.join([slugify(p) for p in parents] + [fd.slug])

            d[name] = fd.dict()
        return d

    som = config.dict()
    som.update(
        pages=build_dir(walk(config.pages_dir)),
        data={},
        jinja_env=Environment(loader=FileSystemLoader(str(config.theme_dir / 'templates')))
    )
    return som


def walk(path: Path, _root: Path=None):
    root = _root or path
    for p in sorted(path.iterdir(), key=lambda p_: (p_.is_dir(), p_.name)):
        yield p.name, walk(p, root) if p.is_dir() else p.resolve()


def parse_front_matter(s):
    m = re.match(FRONT_MATTER_REGEX, s)
    if not m:
        return None, s
    data = yaml.load(m.groups()[0]) or {}
    return data, s[m.end():].lstrip('\r\n')


class FileData(BaseModel):
    title: str
    slug: str
    created: datetime
    path: Path
    ext: str
    render: bool
    uri: str = None
    output: bool = True

    @validator('uri')
    def validate_uri(cls, v):
        if not v.startswith('/'):
            raise ValueError('uri must start with a slash')
        invalid = URI_NOT_ALLOWED_REGEX.findall(v)
        if invalid:
            invalid = ', '.join(f'"{inv}"' for inv in invalid)
            raise ValueError(f'uri contains invalid characters: {invalid}')

    class Config:
        allow_extra = True


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED_REGEX.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')
