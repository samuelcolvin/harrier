import logging
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import FunctionType
from typing import Optional

from jinja2 import (contextfilter, contextfunction, environmentfilter, environmentfunction, evalcontextfilter,
                    evalcontextfunction)
from pydantic import BaseModel, ValidationError

from .common import HarrierProblem, PathMatch

__all__ = (
    'modify',
    'template',
)
logger = logging.getLogger('harrier.extensions')


class ExtensionError(HarrierProblem):
    pass


class ExtType(str, Enum):
    config_modifiers = 'config_modifiers'
    som_modifiers = 'som_modifiers'
    generate_pages = 'generate_pages'
    page_modifiers = 'page_modifiers'
    post_page_render = 'post_page_render'
    copy_modifiers = 'copy_modifiers'
    template_filters = 'template_filters'
    template_functions = 'template_functions'
    template_tests = 'template_tests'


class Extensions:
    def __init__(self, path):
        self.path = path
        self._extensions = {}

    def __getstate__(self):
        return self.path

    def __setstate__(self, state):
        self.path = state
        self._extensions = {}

    def _set_extensions(self):
        self.config_modifiers = self._extensions[ExtType.config_modifiers]
        self.som_modifiers = self._extensions[ExtType.som_modifiers]
        self.generate_pages = self._extensions[ExtType.generate_pages]
        self.page_modifiers = self._extensions[ExtType.page_modifiers]
        self.post_page_render = self._extensions[ExtType.post_page_render]
        self.copy_modifiers = self._extensions[ExtType.copy_modifiers]
        self.template_filters = self._extensions[ExtType.template_filters]
        self.template_functions = self._extensions[ExtType.template_functions]
        self.template_tests = self._extensions[ExtType.template_tests]

    @classmethod
    def get_validators(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        extensions = cls(value)
        extensions.load()
        return extensions

    def load(self):
        self._extensions = {
            ExtType.config_modifiers: [],
            ExtType.som_modifiers: [],
            ExtType.generate_pages: [],
            ExtType.page_modifiers: [],
            ExtType.post_page_render: [],
            ExtType.copy_modifiers: [],
            ExtType.template_filters: {},
            ExtType.template_functions: {},
            ExtType.template_tests: {},
        }
        if self.path.exists():
            spec = spec_from_file_location('extensions', self.path)
            module = module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                logger.exception('error loading extensions %s %s', e.__class__.__name__, e)
                raise ExtensionError(str(e)) from e

            for attr_name in dir(module):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(module, attr_name)
                ext_type = getattr(attr, '__extension__', None)
                if ext_type in {ExtType.page_modifiers, ExtType.copy_modifiers}:
                    self._extensions[ext_type].extend([(path_match, attr) for path_match in attr.path_matches])
                elif ext_type:
                    self._extensions[ext_type].append(attr)
                elif any(getattr(attr, n, False) is True for n in filter_attrs):
                    self._extensions[ExtType.template_filters][attr_name] = attr
                elif any(getattr(attr, n, False) is True for n in function_attrs):
                    self._extensions[ExtType.template_functions][attr_name] = attr
                elif getattr(attr, test_attr, False):
                    self._extensions[ExtType.template_tests][attr_name] = attr
        self._set_extensions()

    def __repr__(self):
        ext = self._extensions and {k.value: v for k, v in self._extensions.items()}
        return f'<Extensions {repr(ext) if ext else "not loaded"}>'


def apply_modifiers(obj, ext):
    original_type = type(obj)
    for f in ext:
        try:
            obj = f(obj)
        except Exception as e:
            logger.exception('error running extension %s', f.__name__)
            raise ExtensionError(str(e)) from e

        if not isinstance(obj, original_type):
            logger.error('extension "%s" did not return a %s object as expected', f.__name__, original_type.__name__)
            raise ExtensionError(f'extension "{f.__name__}" did not return a {original_type.__name__} '
                                 f'object as expected')
    return obj


class PageGeneratorModel(BaseModel):
    path: Path
    content: Optional[str]
    data: dict = {}


def run_ext(ext, som):
    try:
        yield from ext(som)
    except Exception as e:
        logger.exception('error running extension %s', ext.__name__)
        raise ExtensionError(str(e)) from e


def apply_page_generator(som, config):
    from .build import get_page_data
    path_refs = set()
    if config.extensions.generate_pages:
        for ext in config.extensions.generate_pages:
            for d in run_ext(ext, som):
                try:
                    m = PageGeneratorModel.parse_obj(d)
                except ValidationError as e:
                    logger.error('invalid response from extensions %s:\n%s', ext.__name__, e.errors())
                    raise ExtensionError(f'{ext.__name__} response error') from e
                m.path = config.pages_dir / m.path
                final_data = get_page_data(m.path, config=config, file_content=m.content, **m.data)
                path_ref = final_data.pop('path_ref')
                som['pages'][path_ref] = final_data
                path_refs.add(path_ref)
    return path_refs


class modify:
    @staticmethod
    def config(f):
        f.__extension__ = ExtType.config_modifiers
        return f

    @staticmethod
    def som(f):
        f.__extension__ = ExtType.som_modifiers
        return f

    @staticmethod
    def generate_pages(f):
        f.__extension__ = ExtType.generate_pages
        return f

    @staticmethod
    def post_page_render(f):
        f.__extension__ = ExtType.post_page_render
        return f

    @classmethod
    def pages(cls, *globs):
        return cls._file_glob_add(globs, ExtType.page_modifiers, 'pages')

    @classmethod
    def copy(cls, *globs):
        return cls._file_glob_add(globs, ExtType.copy_modifiers, 'copy')

    @staticmethod
    def _file_glob_add(globs, key: ExtType, name):
        if not globs:
            raise HarrierProblem(f'modify.{name} with no file globs specified')
        elif isinstance(globs[0], FunctionType):
            raise HarrierProblem(f"modify.{name} should be used with page globs as arguments, not bare. "
                                 f"E.g. usage should be `@modify.{name}('<file_glob>', ...)`")

        def dec(f):
            f.__extension__ = key
            f.path_matches = [PathMatch(glob) for glob in globs]
            return f
        return dec


filter_attrs = 'contextfilter', 'evalcontextfilter', 'environmentfilter', '__vanilla_filter__'
function_attrs = 'contextfunction', 'evalcontextfunction', 'environmentfunction', '__vanilla_function__'
test_attr = '__vanilla_test__'


class template:
    contextfilter = contextfilter
    evalcontextfilter = evalcontextfilter
    environmentfilter = environmentfilter
    contextfunction = contextfunction
    environmentfunction = environmentfunction
    evalcontextfunction = evalcontextfunction

    @staticmethod
    def filter(f):
        f.__vanilla_filter__ = True
        return f

    @staticmethod
    def function(f):
        f.__vanilla_function__ = True
        return f

    @staticmethod
    def test(f):
        f.__vanilla_test__ = True
        return f
