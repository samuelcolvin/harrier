import logging
import os
import re
from datetime import datetime
from pathlib import Path
from time import time
from typing import Optional

from pydantic import BaseModel, validator

from .common import URI_NOT_ALLOWED, log_complete, slugify
from .config import Config
from .extensions import ExtensionError
from .frontmatter import parse_front_matter

# extensions where we want to do anything except just copy the file to the output dir
OUTPUT_HTML = {'.html', '.md'}
MAYBE_RENDER = {'.xml'}
DATE_REGEX = re.compile(r'(\d{4})-(\d{2})-(\d{2})-?(.*)')
URI_IS_TEMPLATE = re.compile('[{}]')

logger = logging.getLogger('harrier.build')


def build_pages(config: Config):
    start = time()
    pages, files = BuildPages(config).run()
    log_complete(start, 'pages built', files)
    return pages


def content_templates(pages, config):
    tmp_dir = config.get_tmp_dir()
    for page in pages:
        if not page['pass_through']:
            content_template = tmp_dir / 'content' / page['infile'].relative_to(config.pages_dir)
            if not content_template.parent.exists():
                content_template.parent.mkdir(parents=True)
            content_template.write_text(page['content'])
            page['content_template'] = str(content_template.relative_to(tmp_dir))


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
