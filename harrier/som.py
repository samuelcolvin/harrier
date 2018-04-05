import re
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel, validator

from .common import Config, HarrierProblem, logger

FRONT_MATTER_REGEX = re.compile(r'^---[ \t]*(.*)\n---[ \t]*\n', re.S)
# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')
DEFAULT_TEMPLATE = 'main.jinja'


class BuildSOM:
    def __init__(self, config: Config):
        self.config = config
        self.all_defaults = {
            'template': DEFAULT_TEMPLATE,
            **config.defaults.pop('all', {})
        }
        self.path_defaults = [
            (re.compile(k), v)
            for k, v in config.defaults.items() if v
        ]
        self.files = 0
        self.template_files = 0
        self.output_files = 0

    def __call__(self):
        som = self.config.dict()
        som.update(
            pages=self.build_dir(walk(self.config.pages_dir)),
            data={},
            jinja_env=Environment(loader=FileSystemLoader(str(self.config.theme_dir / 'templates')))
        )
        logger.info('Built site object model with %d files, %d to apply template, %d to output',
                    self.files, self.template_files, self.output_files)
        return som

    def build_dir(self, paths, *parents):
        d = {}
        for name, p in paths:
            if not isinstance(p, Path):
                d[name] = self.build_dir(p, *parents, name)
                continue
            try:
                d[name] = self.prep_file(name, p, parents)
            except Exception as e:
                raise HarrierProblem(f'{p}: {e.__class__.__name__} {e}') from e

        return d

    def prep_file(self, name, p, parents):
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

        data.update(self.all_defaults)
        for regex, defaults in self.path_defaults:
            if regex.match(str(p)):
                data.update(defaults)

        maybe_render = p.suffix in MAYBE_RENDER
        apply_template = False
        if html_output or maybe_render:
            fm_data, content = parse_front_matter(p.read_text())
            if html_output or fm_data:
                data['content'] = content
                fm_data and data.update(fm_data)
                apply_template = True

        uri = data.get('uri')
        if not uri:
            data['uri'] = '/' + '/'.join([slugify(p) for p in parents] + [data['slug']])
        elif URI_IS_TEMPLATE.search(uri):
            try:
                data['uri'] = slugify(uri.format(**data))
            except KeyError as e:
                raise KeyError(f'missing format variable "{e}" for "{fd.uri}"')

        if data.get('output', True):
            outfile = self.config.dist_dir / data['uri'][1:]
            if html_output and outfile.suffix != '.html':
                outfile /= 'index.html'
            data['outfile'] = outfile

        fd = FileData(**data)
        logger.debug('added %s apply_template: %s, outfile %s', p, apply_template, fd.outfile)
        self.files += 1
        if apply_template:
            self.template_files += 1
        if fd.outfile:
            self.output_files += 1

        final_data = fd.dict(exclude=set() if apply_template else {'template', 'render'})
        final_data['__file__'] = 1
        return final_data


def walk(path: Path):
    for p in sorted(path.iterdir(), key=lambda p_: (p_.is_dir(), p_.name)):
        yield p.name, walk(p) if p.is_dir() else p.resolve()


def parse_front_matter(s):
    m = re.match(FRONT_MATTER_REGEX, s)
    if not m:
        return None, s.strip('\r\n')
    data = yaml.load(m.groups()[0]) or {}
    return data, s[m.end():].strip('\r\n')


class FileData(BaseModel):
    infile: Path
    title: str
    slug: str
    created: datetime
    uri: str
    template: str
    render: bool = True
    outfile: Path = None

    @validator('uri')
    def validate_uri(cls, v):
        if not v.startswith('/'):
            raise ValueError(f'uri must start with a slash: "{v}')
        invalid = URI_NOT_ALLOWED.findall(v)
        if invalid:
            invalid = ', '.join(f'"{inv}"' for inv in invalid)
            raise ValueError(f'uri contains invalid characters: {invalid}')
        return v

    class Config:
        allow_extra = True


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')
