import logging
import re

from ruamel.yaml import YAMLError

from .common import HarrierProblem, yaml

logger = logging.getLogger('harrier.frontmatter')
FRONT_MATTER_START_REGEX = re.compile(r'---[ \t]*(.*?)\n---[ \t]*\n', re.S)
FRONT_MATTER_DIVIDER_REGEX = re.compile(r'\n?^--- ?([.\w_-]+) ?---[ \t]*\n', re.S | re.M)
FRONT_MATTER_DIVIDER_EXTRA_REGEX = re.compile(r'(.*?)\n---[ \t]*\n', re.S | re.M)


def parse_yaml(s):
    """
    parse a yaml file like it's a front matter file
    """
    try:
        data = yaml.load(s) or {}
    except YAMLError as e:
        logger.error('error parsing YAML: %s', e)
        raise HarrierProblem(f'error parsing YAML: {e}') from e
    return data, data.get('content', '')


def parse_front_matter(s, regex=FRONT_MATTER_START_REGEX):
    m = regex.match(s)
    if not m:
        return None, s
    try:
        data = yaml.load(m.group(1)) or {}
    except YAMLError as e:
        logger.error('error parsing YAML: %s', e)
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
        return [v for v in values if v['content']]
    elif '.' in names:
        raise HarrierProblem('badly constructed multi-part front matter, dividers indicate a mix of list and dict')
    else:
        return {k: v for k, v in content if v['content']}
