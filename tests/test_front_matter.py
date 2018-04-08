import pytest
from pytest_toolbox import mktree
from ruamel.yaml import YAMLError

from harrier.build import BuildSOM
from harrier.config import Config

basic_files = {
    'pages': {},
    'theme/templates/main.jinja': 'main:\n {{ content }}',
}


def test_simple_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
happy: True
---
the content"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {'happy': True}
    assert content == 'the content'


def test_no_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = 'the content'
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj is None
    assert content == 'the content'


def test_odd_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = """---  \t \n happy: True\n---   \nthe content"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {'happy': True}
    assert content == 'the content'


def test_bad_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
foobar:
not valid
---
the content"""
    with pytest.raises(YAMLError):
        BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)


def test_empty_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
---
the content"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {}
    assert content == 'the content'
