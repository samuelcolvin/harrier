import pytest
from pytest_toolbox import mktree

from harrier.build import BuildSOM, split_content
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


@pytest.mark.parametrize('s,result', [
    ("""\
main content
--- . ---
another

---.---
the third""", ['main content', 'another\n', 'the third']),
    ("""\
main content
--- foo ---
another

---bar---
the third""",
     {'main': 'main content', 'foo': 'another\n', 'bar': 'the third'}),
    ("""\
--- foo ---
another
--- bar ---
the third""", {'foo': 'another', 'bar': 'the third'}),
])
def test_multi_part_good(s, result, tmpdir):
    mktree(tmpdir, basic_files)
    assert split_content(s) == result


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
        split_content(s)
