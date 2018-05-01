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
from misaka import HtmlRenderer, Markdown, escape_html
from pydantic import BaseModel, validator
from pygments import highlight
from pygments.formatters import ClassNotFound
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from ruamel.yaml import YAMLError

from .assets import resolve_path
from .common import HarrierProblem, log_complete, yaml
from .config import Config
from .extensions import ExtensionError

FRONT_MATTER_START_REGEX = re.compile(r'---[ \t]*(.*?)\n---[ \t]*\n', re.S)
FRONT_MATTER_DIVIDER_REGEX = re.compile(r'\n?^--- ?([.\w_-]+) ?---[ \t]*\n', re.S | re.M)
FRONT_MATTER_DIVIDER_EXTRA_REGEX = re.compile(r'(.*?)\n---[ \t]*\n', re.S | re.M)
# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')

logger = logging.getLogger('harrier.build')


def build_pages(config: Config):
    start = time()
    pages, files = BuildPages(config).run()
    log_complete(start, 'pages built', files)
    return pages


def render_pages(config: Config, som: dict, build_cache=None):
    start = time()
    cache, files = Renderer(config, som, build_cache).run()
    log_complete(start, 'pages rendered', files)
    return cache


class BuildPages:
    __slots__ = 'config', 'tmp_dir', 'files', 'template_files'

    def __init__(self, config: Config):
        self.config = config
        self.files = 0
        self.template_files = 0

    def run(self):
        paths = sorted(self.config.pages_dir.glob('**/*'), key=lambda p_: (len(p_.parents), str(p_)))
        pages = {}
        for p in paths:
            if p.is_file():
                try:
                    v = self.prep_file(p)
                except ExtensionError:
                    # these are logged directly
                    raise
                except Exception:
                    logger.exception('%s: error building SOM for page', p)
                    raise
                if v:
                    pages[str(p.relative_to(self.config.pages_dir))] = v
        logger.debug('Built site object model with %d files, %d files to render', self.files, self.template_files)
        return pages, self.files

    def prep_file(self, p):
        path_ref = '/' + os.path.normcase(str(p.relative_to(self.config.pages_dir)))
        if any(path_match(path_ref) for path_match in self.config.ignore):
            return

        data, pass_through = self.get_page_data(p, path_ref)

        for path_match, f in self.config.extensions.page_modifiers:
            if path_match(path_ref):
                try:
                    data = f(data, config=self.config)
                except Exception as e:
                    logger.exception('%s error running page extension %s', p, f.__name__)
                    raise ExtensionError(str(e)) from e
                if not isinstance(data, dict):
                    logger.error('%s extension "%s" did not return a dict', p, f.__name__)
                    raise ExtensionError(f'extension "{f.__name__}" did not return a dict')

        fd = FileData(**data)
        final_data = fd.dict(exclude={'template', 'render'} if pass_through else set())
        final_data['pass_through'] = bool(pass_through)

        # logger.debug('added %s pass_through: %s, outfile %s', p, pass_through, fd.outfile)
        self.files += 1
        if not pass_through:
            self.template_files += 1

        return final_data

    def get_page_data(self, p, path_ref):  # noqa: C901 (ignore complexity)
        html_output = p.suffix in OUTPUT_HTML
        maybe_render = p.suffix in MAYBE_RENDER
        name = p.stem if html_output else p.name

        date_match = DATE_REGEX.match(name)
        if date_match:
            *date_args, new_name = date_match.groups()
            created = datetime(*map(int, date_args))
            name = new_name or name
        else:
            created = p.stat().st_mtime

        data = {
            'infile': p,
            'template': self.config.default_template,
            'title': name,
            'slug': '' if html_output and p.stem == 'index' else slugify(name),
            'created': created,
        }

        for path_match, defaults in self.config.defaults.items():
            if path_match(path_ref):
                data.update(defaults)

        pass_through = data.get('pass_through')
        if not pass_through and (html_output or maybe_render):
            fm_data, content = parse_front_matter(p.read_text())
            if html_output or fm_data:
                data['content'] = content
                fm_data and data.update(fm_data)

        if 'content' not in data:
            pass_through = True

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
                raise KeyError(f'missing format variable "{e.args[0]}" for "{uri}"')

        if data.get('output', True):
            outfile = self.config.dist_dir / data['uri'][1:]
            if html_output and outfile.suffix != '.html':
                outfile /= 'index.html'
            data['outfile'] = outfile
        return data, pass_through


def content_templates(pages, config):
    tmp_dir = config.get_tmp_dir()
    for page in pages:
        if not page['pass_through']:
            content_template = tmp_dir / 'content' / page['infile'].relative_to(config.pages_dir)
            if not content_template.parent.exists():
                content_template.parent.mkdir(parents=True)
            content_template.write_text(page['content'])
            page['content_template'] = str(content_template.relative_to(tmp_dir))


DL_REGEX = re.compile('<li>(.*?)::(.*?)</li>', re.S)
LI_REGEX = re.compile('<li>(.*?)</li>', re.S)
MD_EXTENSIONS = 'fenced-code', 'strikethrough', 'no-intra-emphasis', 'tables', 'underline'


class HarrierHtmlRenderer(HtmlRenderer):
    def blockcode(self, text, lang):
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except ClassNotFound:
            lexer = None

        if lexer:
            formatter = HtmlFormatter(cssclass='hi')
            return highlight(text, lexer, formatter)

        code = escape_html(text.strip())
        return f'<pre><code>{code}</code></pre>\n'

    def list(self, content, is_ordered, is_block):
        if not is_ordered and len(DL_REGEX.findall(content)) == len(LI_REGEX.findall(content)):
            return '<dl>\n' + DL_REGEX.sub(r'  <dt>\1</dt><dd>\2</dd>', content) + '</dl>'
        else:
            return content

    def header(self, content, level):
        return f'<h{level} id="{level}-{slugify(content)}">{content}</h{level}>\n'


class Renderer:
    __slots__ = 'config', 'som', 'build_cache', 'md', 'env', 'checked_dirs'

    def __init__(self, config: Config, som: dict, build_cache: dict=None):
        self.config = config
        self.som = som
        self.build_cache = build_cache

        md_renderer = HarrierHtmlRenderer()
        self.md = Markdown(md_renderer, extensions=MD_EXTENSIONS)

        template_dirs = [str(self.config.get_tmp_dir()), str(self.config.theme_dir / 'templates')]
        logger.debug('template directories: %s', ', '.join(template_dirs))

        self.env = Environment(loader=FileSystemLoader(template_dirs))
        self.env.filters.update(self.config.extensions.template_filters)

        self.env.globals.update(
            url=resolve_url,
            resolve_url=resolve_url,
            inline_css=inline_css,
        )
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
        logger.debug('generated %d files, copied %d files', gen, copy)
        return self.build_cache, gen + copy

    def render_file(self, p):
        if not p.get('outfile'):
            return
        outfile: Path = p['outfile']
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
            content_template = self.env.get_template(str(p['content_template']))
            content = content_template.render(page=p, site=self.som)

            content = split_content(content)

            if infile.suffix == '.md':
                if isinstance(content, dict):
                    content = {k: self._md_content(v) for k, v in content.items()}
                elif isinstance(content, list):
                    content = [self._md_content(v) for v in content]
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
            logger.exception('%s: error rendering page', infile)
            raise HarrierProblem(f'{e.__class__.__name__}: {e}') from e
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

    def _md_content(self, v):
        v['content'] = self.md(v['content'])
        return v

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


def parse_front_matter(s, regex=FRONT_MATTER_START_REGEX):
    m = regex.match(s)
    if not m:
        return None, s
    try:
        data = yaml.load(m.group(1)) or {}
    except YAMLError as e:
        raise HarrierProblem(f'error parsing YAML: {e}') from e
    content = s[m.end():]
    return data, content


def _parse_section_content(s):
    data, content = parse_front_matter(s, FRONT_MATTER_DIVIDER_EXTRA_REGEX)
    data = data or {}
    data['content'] = content
    return data


def split_content(s):
    m = FRONT_MATTER_DIVIDER_REGEX.search(s)
    if not m:
        return s
    content = []
    name = 'main'
    while True:
        start, end = m.span()
        content.append(
            (name, _parse_section_content(s[:start]))
        )
        name = m.group(1)
        s = s[end:]
        m = FRONT_MATTER_DIVIDER_REGEX.search(s)
        if not m:
            break
    content.append(
        (name, _parse_section_content(s))
    )
    names, values = zip(*content)
    names = set(names[1:])
    if names == {'.'}:
        return list(values)
    elif '.' in names:
        raise HarrierProblem(f'badly constructed multi-part front matter, dividers indicate a mix of list and dict')
    else:
        return {k: v for k, v in content if v['content']}


class FileData(BaseModel):
    infile: Path
    title: str
    slug: str
    created: datetime
    uri: str
    template: Optional[str]
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
    return resolve_path(path, ctx['site']['path_lookup'], ctx['site']['config'])


@contextfunction
def inline_css(ctx, path):
    path = resolve_path(path, ctx['site']['path_lookup'], None)
    real_path = Path(path[1:])
    p = ctx['site']['dist_dir'] / real_path
    css = p.read_text()
    map_path = real_path.with_suffix('.css.map')
    if (ctx['site']['dist_dir'] / map_path).exists():
        css = re.sub(r'/\*# sourceMappingURL=.*\*/', f'/*# sourceMappingURL=/{map_path} */', css)
    return css.strip('\r\n ')
