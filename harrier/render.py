import datetime as datetime
import hashlib
import json
import logging
import re
import shutil
from html import escape
from pathlib import Path
from time import time
from types import GeneratorType

from devtools import debug, pformat
from jinja2 import Environment, FileSystemLoader, contextfilter, contextfunction
from misaka import HtmlRenderer, Markdown, escape_html
from pygments import highlight
from pygments.formatters import ClassNotFound
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name

from .assets import resolve_path
from .common import HarrierProblem, PathMatch, log_complete, slugify
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
    __slots__ = 'config', 'som', 'build_cache', 'md', 'env', 'checked_dirs', 'ctx'

    def __init__(self, config: Config, som: dict, build_cache: dict=None):
        self.config = config
        self.som = som
        self.build_cache = build_cache

        md_renderer = HarrierHtmlRenderer()
        self.md = Markdown(md_renderer, extensions=MD_EXTENSIONS)

        template_dirs = [str(self.config.get_tmp_dir()), str(self.config.theme_dir / 'templates')]
        logger.debug('template directories: %s', ', '.join(template_dirs))

        self.env = Environment(loader=FileSystemLoader(template_dirs), extensions=['jinja2.ext.loopcontrols'])
        self.env.filters.update(
            glob=page_glob,
            slugify=slugify,
            format=format_filter,
            tojson=json_filter,
            debug=debug_filter,
            markdown=self.md,
            paginate=paginate_filter,
        )
        self.env.filters.update(self.config.extensions.template_filters)

        self.env.globals.update(
            url=resolve_url,
            resolve_url=resolve_url,
            inline_css=inline_css,
        )
        self.env.globals.update(self.config.extensions.template_functions)
        self.som['config'] = config
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
            # this will raise an exception if somehow outfile is outside dist_dir
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
            content = content_template.render(page=p, **self.som)

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
                rendered = template.render(content=content, page=p, **self.som)
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
    return resolve_path(path, ctx['path_lookup'], ctx['config'])


@contextfunction
def inline_css(ctx, path):
    path = resolve_path(path, ctx['path_lookup'], None)
    real_path = Path(path[1:])
    config: Config = ctx['config']
    p = config.dist_dir / real_path
    css = p.read_text()
    map_path = real_path.with_suffix('.css.map')
    if (config.dist_dir / map_path).exists():
        css = re.sub(r'/\*# sourceMappingURL=.*\*/', f'/*# sourceMappingURL=/{map_path} */', css)
    return css.strip('\r\n ')


def page_glob(pages, *globs, test='path'):
    assert test in ('uri', 'path'), 'the "test" argument should be either "uri" or "path"'
    matches = globs and [PathMatch(glob) for glob in globs]
    for k, page in pages.items():
        glob_key = k if test == 'path' else page['uri']
        if any(match(glob_key) for match in matches):
            yield page


def format_filter(s, *args, **kwargs):
    return s.format(*args, **kwargs)


def isoformat(o):
    return o.isoformat()


class UniversalEncoder(json.JSONEncoder):
    ENCODE_BY_TYPE = {
        datetime.datetime: isoformat,
        datetime.date: isoformat,
        datetime.time: isoformat,
        set: list,
        frozenset: list,
        GeneratorType: list,
        bytes: lambda o: o.decode(),
    }

    def default(self, obj):
        encoder = self.ENCODE_BY_TYPE.get(type(obj), str)
        return encoder(obj)


def json_filter(content, indent=None):
    return json.dumps(content, indent=indent, cls=UniversalEncoder)


def lenient_len(v):
    try:
        return len(v)
    except TypeError:
        return '-'


STYLES = 'white-space:pre-wrap;background:#444;color:white;border-radius:5px;padding:10px;font-size:13px'


def debug_filter(c, html=True):
    output = f'{pformat(debug.format(c).arguments[0].value)} (type={c.__class__.__name__} length={lenient_len(c)})'
    print('debug filter:', output)
    if html:
        output = f'<pre style="{STYLES}">\n{escape(output, quote=False)}\n</pre>'
    return output


@contextfilter
def paginate_filter(ctx, v, page=1, per_page=None):
    per_page = per_page or ctx['config'].paginate_by
    start = (page - 1) * per_page
    return list(v)[start:start + per_page]
