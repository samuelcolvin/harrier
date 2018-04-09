import hashlib
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from time import time
from typing import Optional

from jinja2 import Environment, FileSystemLoader, contextfunction
from misaka import HtmlRenderer, Markdown
from pydantic import BaseModel, validator
from ruamel.yaml import YAML, YAMLError

from .assets import find_theme_files
from .common import HarrierProblem, compile_glob
from .config import Config

FRONT_MATTER_START_REGEX = re.compile(r'---[ \t]*(.*)\n---[ \t]*\n', re.S)
FRONT_MATTER_DIVIDER_REGEX = re.compile(r'\n?^--- ?([.\w_-]+) ?---[ \t]*\n', re.S | re.M)
# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')
DEFAULT_TEMPLATE = 'main.jinja'

logger = logging.getLogger('harrier.build')


def build_som(config: Config):
    return BuildSOM(config).run()


def render(config: Config, som: dict, build_cache=None):
    return Renderer(config, som, build_cache).run()


class BuildSOM:
    def __init__(self, config: Config):
        self.config = config
        self.tmp_dir = config.get_tmp_dir()
        self.all_defaults = {
            'template': DEFAULT_TEMPLATE,
            **config.defaults.pop('all', {})
        }
        self.path_defaults = [(compile_glob(k), v) for k, v in config.defaults.items() if v]
        self.files = 0
        self.template_files = 0
        self.yaml = YAML(typ='safe')

    def run(self):
        logger.info('Building "%s"...', self.config.pages_dir)
        start = time()
        pages = self.build_pages()
        logger.info('Built site object model with %d files, %d files to render in %0.2fs',
                    self.files, self.template_files, time() - start)
        data = {}
        return {
            'pages': pages,
            'data': data,
            'theme_files': find_theme_files(self.config),
            **self.config.dict(),
        }

    def build_pages(self):
        paths = sorted(self.config.pages_dir.glob('**/*'), key=lambda p_: (len(p_.parents), str(p_)))
        d = {}
        for p in paths:
            if p.is_file():
                try:
                    d[str(p.relative_to(self.config.pages_dir))] = self.prep_file(p)
                except Exception as e:
                    raise HarrierProblem(f'{p}: {e.__class__.__name__} {e}') from e
        return d

    def prep_file(self, p):
        html_output = p.suffix in OUTPUT_HTML
        rel_path = os.path.normcase(str(p.relative_to(self.config.pages_dir)))
        data = self.get_page_data(p, html_output, rel_path)

        maybe_render = p.suffix in MAYBE_RENDER
        apply_jinja = False
        if html_output or maybe_render:
            fm_data, content = self.parse_front_matter(p.read_text())
            if html_output or fm_data:
                data['content'] = content
                fm_data and data.update(fm_data)
                apply_jinja = True

        self.set_page_uri_outfile(p, data, html_output)

        for regex, f in self.config.extensions.page_modifiers:
            if regex.match(rel_path):
                data = f(data, config=self.config)
                if not isinstance(data, dict):
                    raise HarrierProblem(f'extension "{f.__name__}" did not return a dict')

        fd = FileData(**data)
        final_data = fd.dict(exclude=set() if apply_jinja else {'template', 'render'})
        final_data['__file__'] = 1

        if apply_jinja and fd.render:
            if not fd.content_template.parent.exists():
                fd.content_template.parent.mkdir(parents=True)
            fd.content_template.write_text(final_data.pop('content'))
            final_data['content_template'] = str(fd.content_template.relative_to(self.tmp_dir))
        else:
            final_data.pop('content_template')

        # logger.debug('added %s apply_jinja: %s, outfile %s', p, apply_jinja, fd.outfile)
        self.files += 1
        if apply_jinja:
            self.template_files += 1

        return final_data

    def get_page_data(self, p, html_output, rel_path):
        data = {
            'infile': p,
            'content_template': self.tmp_dir / 'content' / p.relative_to(self.config.pages_dir)
        }
        name = p.stem if html_output else p.name

        date_match = DATE_REGEX.match(name)
        if date_match:
            *date_args, new_name = date_match.groups()
            created = datetime(*map(int, date_args))
            name = new_name or name
        else:
            created = p.stat().st_mtime
        data.update(
            title=name,
            slug='' if html_output and p.stem == 'index' else slugify(name),
            created=created
        )

        data.update(self.all_defaults)
        for regex, defaults in self.path_defaults:
            if regex.match(rel_path):
                data.update(defaults)
        return data

    def set_page_uri_outfile(self, p, data, html_output):
        uri = data.get('uri')
        if not uri:
            parents = str(p.parent.relative_to(self.config.pages_dir)).split('/')
            if parents == ['.']:
                data['uri'] = '/' + data['slug']
            else:
                data['uri'] = '/' + '/'.join([slugify(p) for p in parents] + [data['slug']])
        elif URI_IS_TEMPLATE.search(uri):
            try:
                data['uri'] = slugify(uri.format(**data))
            except KeyError as e:
                raise KeyError(f'missing format variable "{e}" for "{uri}"')

        if data.get('output', True):
            outfile = self.config.dist_dir / data['uri'][1:]
            if html_output and outfile.suffix != '.html':
                outfile /= 'index.html'
            data['outfile'] = outfile

    def parse_front_matter(self, s):
        m = FRONT_MATTER_START_REGEX.match(s)
        if not m:
            return None, s
        try:
            data = self.yaml.load(m.groups()[0]) or {}
        except YAMLError as e:
            raise HarrierProblem(f'error parsing YAML: {e}') from e
        content = s[m.end():]
        return data, content


class Renderer:
    __slots__ = 'start', 'config', 'som', 'build_cache', 'md', 'env', 'checked_dirs'

    def __init__(self, config: Config, som: dict, build_cache: dict=None):
        self.start = time()
        self.config = config
        self.som = som
        self.build_cache = build_cache

        rndr = HtmlRenderer()
        self.md = Markdown(rndr)

        template_dirs = [str(self.config.get_tmp_dir()), str(self.config.theme_dir / 'templates')]
        logger.debug('template directories: %s', ', '.join(template_dirs))

        self.env = Environment(loader=FileSystemLoader(template_dirs))
        self.env.filters.update(self.config.extensions.template_filters)
        self.env.globals['url'] = resolve_url
        self.env.globals.update(self.config.extensions.template_functions)

        self.checked_dirs = set()

    def run(self):
        gen, copy = 0, 0
        for p in self.som['pages'].values():
            action = self.render_file(p)
            if action == 1:
                gen += 1
            elif action == 2:
                copy += 1
        logger.info('generated %d files, copied %d files in %0.2fs', gen, copy, time() - self.start)
        return self.build_cache

    def render_file(self, p):
        if not p.get('outfile'):
            return
        outfile: Path = p['outfile'].resolve()
        out_dir = outfile.parent
        if out_dir not in self.checked_dirs:
            # this will raise an exception if somehow outfile is outside dis_dir
            out_dir.relative_to(self.config.dist_dir)
            out_dir.mkdir(exist_ok=True, parents=True)
            self.checked_dirs.add(out_dir)

        infile: Path = p['infile']
        if 'template' in p:
            return self.render_template(p, infile, outfile)
        else:
            return self.copy_file(p, infile, outfile)

    def render_template(self, p: dict, infile: Path, outfile: Path):
        template_file = p['template']
        try:
            if p['render']:
                content_template = self.env.get_template(str(p['content_template']))
                content = content_template.render(page=p, site=self.som)
            else:
                content = p['content']

            content = split_content(content)

            if infile.suffix == '.md':
                if isinstance(content, dict):
                    content = {k: self.md(v) for k, v in content.items()}
                elif isinstance(content, list):
                    content = [self.md(v) for v in content]
                else:
                    # assumes content is a str
                    content = self.md(content)

            if template_file:
                template = self.env.get_template(template_file)
                rendered = template.render(content=content, page=p, site=self.som)
            else:
                rendered = content
            rendered = rendered.rstrip(' \t\r\n') + '\n'
        except Exception as e:
            logger.exception('%s: %s %s', infile, e.__class__.__name__, e)
            raise
        else:
            rendered_b = rendered.encode()
            if self.build_cache is not None:
                out_hash = hashlib.md5(rendered_b).digest()
                if self.build_cache.get(infile) == out_hash:
                    # file hasn't changed
                    return
                else:
                    self.build_cache[infile] = out_hash
            outfile.write_bytes(rendered_b)
            return 1

    def copy_file(self, p: dict, infile: Path, outfile: Path):
        if self.build_cache is not None:
            mtime = infile.stat().st_mtime
            if self.build_cache.get(infile) == mtime:
                # file hasn't changed
                return
            else:
                self.build_cache[infile] = mtime
        shutil.copy(infile, outfile)
        return 2


def split_content(s):
    m = FRONT_MATTER_DIVIDER_REGEX.search(s)
    if not m:
        return s
    content = []
    name = 'main'
    while True:
        start, end = m.span()
        content.append(
            (name, s[:start])
        )
        name = m.groups()[0]
        s = s[end:]
        m = FRONT_MATTER_DIVIDER_REGEX.search(s)
        if not m:
            break
    content.append(
        (name, s)
    )
    names, values = zip(*content)
    names = set(names[1:])
    if names == {'.'}:
        return list(values)
    elif '.' in names:
        raise HarrierProblem(f'badly constructed multi-part front matter, dividers indicate a mix of list and dict')
    else:
        return {k: v for k, v in content if v}


class FileData(BaseModel):
    infile: Path
    content_template: Path
    title: str
    slug: str
    created: datetime
    uri: str
    template: Optional[str]
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


@contextfunction
def resolve_url(ctx, path):
    # TODO try more things, raise error on failure
    theme_files = ctx['site']['theme_files']
    return theme_files.get(path) or path
