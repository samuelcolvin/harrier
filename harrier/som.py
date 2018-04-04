import re
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel, validator

from .common import Config, HarrierProblem

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)
# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')
DEFAULT_TEMPLATE = 'main.jinja'


def build_som(config: Config):
    all_defaults = config.defaults.pop('all', None) or {'template': DEFAULT_TEMPLATE}
    path_defaults = [
        (re.compile(k), v)
        for k, v in config.defaults.items() if v
    ]

    def build_dir(paths, *parents):
        d = {}
        for name, p in paths:
            if not isinstance(p, Path):
                d[name] = build_dir(p, *parents, name)
                continue
            try:
                html_output = p.suffix in OUTPUT_HTML
                data = {'infile': p}
                name = p.stem if html_output else name

                date_match = DATE_REGEX.match(name)
                if date_match:
                    *date_args, new_name = date_match.groups()
                    created = datetime(*map(int, date_args))
                    name = new_name or name
                else:
                    created = p.stat().st_mtime
                data.update(
                    title=name,
                    slug='' if p.name in {'index.html', 'index.md'} else slugify(name),
                    created=created
                )

                data.update(all_defaults)
                for regex, defaults in path_defaults:
                    if regex.match(str(p)):
                        data.update(defaults)

                maybe_render = p.suffix in MAYBE_RENDER
                if html_output or maybe_render:
                    fm_data, content = parse_front_matter(p.read_text())
                    if not html_output and not fm_data:
                        # don't render this file, just copy it across
                        data.pop('template')
                    else:
                        data['content'] = content
                        fm_data and data.update(fm_data)
                else:
                    data.pop('template')

                uri = data.get('uri')
                if not uri:
                    data['uri'] = '/' + '/'.join([slugify(p) for p in parents] + [data['slug']])
                elif URI_IS_TEMPLATE.search(uri):
                    try:
                        data['uri'] = slugify(uri.format(**data))
                    except KeyError as e:
                        raise KeyError(f'missing format variable "{e}" for "{fd.uri}"')

                if data.get('output', True):
                    outfile = config.dist_dir / data['uri'][1:]
                    if html_output and outfile.suffix != '.html':
                        outfile /= 'index.html'
                    data['outfile'] = outfile

                final_data = FileData(**data).dict()
                final_data['__file__'] = 1
                d[name] = final_data
            except Exception as e:
                raise HarrierProblem(f'{p}: {e.__class__.__name__} {e}') from e

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
    infile: Path
    title: str
    slug: str
    created: datetime
    uri: str

    @validator('uri')
    def validate_uri(cls, v):
        check_slug(v)
        return v

    class Config:
        allow_extra = True


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')


def check_slug(uri):
    if not uri.startswith('/'):
        raise ValueError(f'uri must start with a slash: "{uri}')
    invalid = URI_NOT_ALLOWED.findall(uri)
    if invalid:
        invalid = ', '.join(f'"{inv}"' for inv in invalid)
        raise ValueError(f'uri contains invalid characters: {invalid}')

