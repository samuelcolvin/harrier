import datetime as datetime
import hashlib
import json
import logging
import re
import shutil
from decimal import Decimal
from html import escape
from pathlib import Path
from time import time
from types import GeneratorType
from uuid import UUID

from devtools import debug
from jinja2 import Environment, FileSystemLoader, contextfunction
from misaka import HtmlRenderer, Markdown, escape_html
from pygments import highlight
from pygments.formatters import ClassNotFound
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name

from .assets import resolve_path
from .common import HarrierProblem, log_complete, slugify
from .config import Config
from .frontmatter import split_content

# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')

logger = logging.getLogger('harrier.render')


def render_pages(config: Config, som: dict, build_cache=None):
    start = time()
    cache, files = Renderer(config, som, build_cache).run()
    log_complete(start, 'pages rendered', files)
    return cache


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
            json=json_function,
            debug=debug_function,
            markdown=self.md,
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


def isoformat(o):
    return o.isoformat()


class UniversalEncoder(json.JSONEncoder):
    ENCODER_BY_TYPE = {
        UUID: str,
        datetime.datetime: isoformat,
        datetime.date: isoformat,
        datetime.time: isoformat,
        set: list,
        frozenset: list,
        GeneratorType: list,
        bytes: lambda o: o.decode(),
        Decimal: str,
    }

    def default(self, obj):
        try:
            encoder = self.ENCODER_BY_TYPE[type(obj)]
        except KeyError:
            return repr(obj)
        return encoder(obj)


def json_function(content, indent=None):
    return json.dumps(content, indent=indent, cls=UniversalEncoder)


def lenient_len(v):
    try:
        return len(v)
    except TypeError:
        return '-'


def debug_function(content):
    debug(content)
    return (
        f'<pre style="white-space: pre-wrap;">\n'
        f'  type: {escape(str(type(content)))}\n'
        f'length: {lenient_len(content)}\n'
        f'  json: {escape(json_function(content, indent=2), quote=False)}\n'
        f'</pre>')
