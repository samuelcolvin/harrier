import re
from enum import Enum
from importlib.util import module_from_spec, spec_from_file_location
from types import FunctionType

from jinja2 import (contextfilter, contextfunction, environmentfilter, environmentfunction, evalcontextfilter,
                    evalcontextfunction)

from .common import HarrierProblem

__all__ = (
    'modify',
    'template',
)


class ExtType(str, Enum):
    pre_modifiers = 'pre_modifiers'
    post_modifiers = 'post_modifiers'
    page_modifiers = 'page_modifiers'
    template_filters = 'template_filters'
    template_functions = 'template_functions'


class Extensions(dict):
    def __init__(self, extensions):
        super().__init__(extensions)
        self.pre_modifiers = extensions[ExtType.pre_modifiers]
        self.post_modifiers = extensions[ExtType.post_modifiers]
        self.page_modifiers = extensions[ExtType.page_modifiers]
        self.template_filters = extensions[ExtType.template_filters]
        self.template_functions = extensions[ExtType.template_functions]

    @classmethod
    def get_validators(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        extensions = {
            ExtType.pre_modifiers: [],
            ExtType.post_modifiers: [],
            ExtType.page_modifiers: [],
            ExtType.template_filters: {},
            ExtType.template_functions: {},
        }
        if not value:
            return cls(extensions)

        try:
            spec = spec_from_file_location('extensions', value)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
        except ImportError as e:
            raise ValueError(str(e)) from e

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            ext_type = getattr(attr, '__extension__', None)
            if ext_type == ExtType.page_modifiers:
                for regex in attr.regexes:
                    extensions[ext_type].append((re.compile(regex), attr))
            elif ext_type:
                extensions[ext_type].append(attr)
            elif any(getattr(attr, n, False) for n in filter_attrs):
                extensions[ExtType.template_filters][attr_name] = attr
            elif any(getattr(attr, n, False) for n in function_attrs):
                extensions[ExtType.template_functions][attr_name] = attr

        return cls(extensions)


def apply_modifiers(obj, ext):
    original_type = type(obj)
    for f in ext:
        obj = f(obj)
        if not isinstance(obj, original_type):
            raise HarrierProblem(f'extension "{f.__name__}" did not return a {original_type.__name__} as expected')
    return obj


class modify:
    @staticmethod
    def pre(f):
        f.__extension__ = ExtType.pre_modifiers
        return f

    @staticmethod
    def post(f):
        f.__extension__ = ExtType.post_modifiers
        return f

    @staticmethod
    def pages(*regexes):
        if not regexes:
            raise HarrierProblem('validator with no page regexes specified')
        elif isinstance(regexes[0], FunctionType):
            raise HarrierProblem("modify_pages should be used with page regexes as arguments, not bare. "
                                 "E.g. usage should be `@modify_pages('<page_regex>', ...)`")

        def dec(f):
            f.__extension__ = ExtType.page_modifiers
            f.regexes = regexes
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
