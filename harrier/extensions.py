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


class ExtensionTypes(str, Enum):
    pre_modifier = 'pre_modifier'
    post_modifier = 'post_modifier'
    page_modifier = 'page_modifier'
    template_filters = 'template_filters'
    template_functions = 'template_functions'


class Extensions:
    @classmethod
    def get_validators(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not value:
            return
        try:
            spec = spec_from_file_location('extensions', value)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
        except ImportError as e:
            raise ValueError(str(e)) from e

        extensions = {
            ExtensionTypes.pre_modifier: [],
            ExtensionTypes.post_modifier: [],
            ExtensionTypes.page_modifier: [],
            ExtensionTypes.template_filters: {},
            ExtensionTypes.template_functions: {},
        }

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            ext_type = getattr(attr, '__extension__', None)
            if ext_type == ExtensionTypes.page_modifier:
                for regex in attr.regexes:
                    extensions[ext_type].append((re.compile(regex), attr))
            elif ext_type:
                extensions[ext_type].append(attr)
            elif any(getattr(attr, n, False) for n in filter_attrs):
                extensions[ExtensionTypes.template_filters][attr_name] = attr
            elif any(getattr(attr, n, False) for n in function_attrs):
                extensions[ExtensionTypes.template_functions][attr_name] = attr

        if any(extensions.values()):
            return extensions


class modify:
    @staticmethod
    def pre(f):
        if isinstance(f, FunctionType):
            raise HarrierProblem("pre_build should be used bare. "
                                 "E.g. usage should be `@pre_build`")
        f.__extension__ = ExtensionTypes.pre_modifier
        return f

    @staticmethod
    def pre(f):
        if isinstance(f, FunctionType):
            raise HarrierProblem("post_build should be used bare. "
                                 "E.g. usage should be `@post_build`")
        f.__extension__ = ExtensionTypes.post_modifier
        return f

    @staticmethod
    def pages(*regexes):
        if not regexes:
            raise HarrierProblem('validator with no page regexes specified')
        elif isinstance(regexes[0], FunctionType):
            raise HarrierProblem("modify_pages should be used with page regexes as arguments, not bare. "
                                 "E.g. usage should be `@modify_pages('<page_regex>', ...)`")

        def dec(f):
            f.__extension__ = ExtensionTypes.page_modifier
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
