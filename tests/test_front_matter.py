import pytest

from harrier.build import parse_front_matter, split_content
from harrier.common import HarrierProblem


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
    with pytest.raises(HarrierProblem):
        parse_front_matter(s)


def test_empty_front_matter():
    s = """\
---
---
the content"""
    obj, content = parse_front_matter(s)
    assert obj == {}
    assert content == 'the content'


def test_no_starting_front_matter():
    s = (
        '\n'
        '---\n'
        '---\n'
        'the content'
    )
    obj, content = parse_front_matter(s)
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
def test_multi_part_good(s, result):
    assert split_content(s) == result


def test_multi_mixed():
    s = """\
---
---
--- . ---
another
--- bar ---
the third"""
    with pytest.raises(HarrierProblem):
        split_content(s)
