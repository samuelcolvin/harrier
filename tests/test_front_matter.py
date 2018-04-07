import pytest
from yaml.scanner import MarkedYAMLError

from harrier.build import parse_front_matter


def test_simple_front_matter():
    s = """\
---
happy: True
---
the content"""
    obj, content = parse_front_matter(s)
    assert obj == {'happy': True}
    assert content == 'the content'


def test_no_front_matter():
    s = 'the content'
    obj, content = parse_front_matter(s)
    assert obj is None
    assert content == 'the content'


def test_odd_front_matter():
    s = """---  \t \n happy: True\n---   \nthe content"""
    obj, content = parse_front_matter(s)
    assert obj == {'happy': True}
    assert content == 'the content'


def test_bad_front_matter():
    s = """\
---
foobar:
not valid
---
the content"""
    with pytest.raises(MarkedYAMLError):
        parse_front_matter(s)


def test_empty_front_matter():
    s = """\
---
---
the content"""
    obj, content = parse_front_matter(s)
    assert obj == {}
    assert content == 'the content'
