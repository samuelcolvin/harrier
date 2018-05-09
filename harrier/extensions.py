import logging
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from types import FunctionType

from jinja2 import (contextfilter, contextfunction, environmentfilter, environmentfunction, evalcontextfilter,
                    evalcontextfunction)

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
    page_modifiers = 'page_modifiers'
    copy_modifiers = 'copy_modifiers'
    template_filters = 'template_filters'
    template_functions = 'template_functions'


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
        self.page_modifiers = self._extensions[ExtType.page_modifiers]
        self.copy_modifiers = self._extensions[ExtType.copy_modifiers]
        self.template_filters = self._extensions[ExtType.template_filters]
        self.template_functions = self._extensions[ExtType.template_functions]

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
            ExtType.page_modifiers: [],
            ExtType.copy_modifiers: [],
            ExtType.template_filters: {},
            ExtType.template_functions: {},
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


class modify:
    @staticmethod
    def config(f):
        f.__extension__ = ExtType.config_modifiers
        return f

    @staticmethod
    def som(f):
        f.__extension__ = ExtType.som_modifiers
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
