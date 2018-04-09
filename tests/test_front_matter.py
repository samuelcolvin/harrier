import pytest
from pytest_toolbox import mktree

from harrier.build import BuildSOM
from harrier.common import HarrierProblem
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
    with pytest.raises(HarrierProblem):
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


def test_no_starting_front_matter(tmpdir):
    mktree(tmpdir, basic_files)
    s = (
        '\n'
        '---\n'
        '---\n'
        'the content'
    )
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj is None
    assert content == s


def test_multi_list(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
---
main content
--- . ---
another

---.---
the third"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {}
    assert content == ['main content', 'another\n', 'the third']


def test_multi_dict(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
abc: def
---
main content
--- foo ---
another

---bar---
the third"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {'abc': 'def'}
    assert content == {'main': 'main content', 'foo': 'another\n', 'bar': 'the third'}


def test_multi_dict_empty(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
---
--- foo ---
another
--- bar ---
the third"""
    obj, content = BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
    assert obj == {}
    assert content == {'foo': 'another', 'bar': 'the third'}


def test_multi_mixed(tmpdir):
    mktree(tmpdir, basic_files)
    s = """\
---
---
--- . ---
another
--- bar ---
the third"""
    with pytest.raises(HarrierProblem):
        BuildSOM(Config(source_dir=tmpdir)).parse_front_matter(s)
