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


class ExtType(str, Enum):
    config_modifiers = 'config_modifiers'
    som_modifiers = 'som_modifiers'
    page_modifiers = 'page_modifiers'
    template_filters = 'template_filters'
    template_functions = 'template_functions'


class Extensions:
    def __init__(self, path):
        self._path = path
        self._extensions = {}

    def __getstate__(self):
        return self._path

    def __setstate__(self, state):
        self._path = state
        self._extensions = {}

    def _set_extensions(self):
        self.config_modifiers = self._extensions[ExtType.config_modifiers]
        self.som_modifiers = self._extensions[ExtType.som_modifiers]
        self.page_modifiers = self._extensions[ExtType.page_modifiers]
        self.template_filters = self._extensions[ExtType.template_filters]
        self.template_functions = self._extensions[ExtType.template_functions]

    @classmethod
    def get_validators(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        extensions = cls(value)
        try:
            extensions.load()
        except (ImportError, FileNotFoundError) as e:
            raise ValueError(str(e)) from e
        return extensions

    def load(self):
        self._extensions = {
            ExtType.config_modifiers: [],
            ExtType.som_modifiers: [],
            ExtType.page_modifiers: [],
            ExtType.template_filters: {},
            ExtType.template_functions: {},
        }
        if self._path:
            spec = spec_from_file_location('extensions', self._path)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                if attr_name.startswith('_'):
                    continue
                attr = getattr(module, attr_name)
                ext_type = getattr(attr, '__extension__', None)
                if ext_type == ExtType.page_modifiers:
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

    def __eq__(self, other):
        return self._extensions == getattr(other, '_extensions', other)


def apply_modifiers(obj, ext):
    original_type = type(obj)
    for f in ext:
        obj = f(obj)
        if not isinstance(obj, original_type):
            raise HarrierProblem(f'extension "{f.__name__}" did not return a {original_type.__name__} '
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

    @staticmethod
    def pages(*globs):
        if not globs:
            raise HarrierProblem('validator with no page globs specified')
        elif isinstance(globs[0], FunctionType):
            raise HarrierProblem("modify_pages should be used with page globs as arguments, not bare. "
                                 "E.g. usage should be `@modify_pages('<page_glob>', ...)`")

        def dec(f):
            f.__extension__ = ExtType.page_modifiers
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
