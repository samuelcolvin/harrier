import pytest

from harrier.common import HarrierProblem
from harrier.frontmatter import parse_front_matter, parse_yaml, split_content


def test_simple_front_matter():
    s = """\
---
happy: True
---
the content"""
    obj, content = parse_front_matter(s)
    assert obj == {'happy': True}
    assert content == 'the content'


def test_simple_raw_yaml():
    s = """\
happy: True
"""
    obj, content = parse_yaml(s)
    assert obj == {'happy': True}
    assert content == ''


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


def test_bad_raw_yaml():
    s = """\
foobar:
not valid"""
    with pytest.raises(HarrierProblem):
        parse_yaml(s)


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
the third""", [{'content': 'main content'}, {'content': 'another\n'}, {'content': 'the third'}]),
    ("""\
main content
--- foo ---
another

---bar---
the third""",
     {'main': {'content': 'main content'}, 'foo': {'content': 'another\n'}, 'bar': {'content': 'the third'}}),
    ("""\
--- foo ---
another
--- bar ---
the third""", {'foo': {'content': 'another'}, 'bar': {'content': 'the third'}}),
    ("""\
main content
--- . ---
foo: 1
bar: [1, 2, 3]
---
another

---.---
x: y
---
the third""", [
        {
            'content': 'main content',
        },
        {
            'content': 'another\n',
            'foo': 1,
            'bar': [1, 2, 3],
        },
        {
            'content': 'the third',
            'x': 'y',
        }
    ]),
    ("""\
--- . ---
foo: 1
---
first
---.---
foo: 2
---
second""", [
        {
            'foo': 1,
            'content': 'first',
        },
        {
            'foo': 2,
            'content': 'second',
        }
    ]),
    ("""\
--- foo ---
x: 1
---
another
--- bar ---
y: 2
---
the third""", {
        'foo': {
            'content': 'another',
            'x': 1,
        },
        'bar': {
            'content': 'the third',
            'y': 2,
        }
    }),
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


@pytest.mark.parametrize('s,result', [
    ("""\
---
test: 1
---
--- xx ---
x: 1
---
this is x
--- yy ---
y: 2
---
this is y""", {
        'test': 1,
        'content': {
            'xx': {
                'content': 'this is x',
                'x': 1,
            },
            'yy': {
                'content': 'this is y',
                'y': 2
            }
        }
    }
    ),
    ("""\
---
test: 2
---
whatever
--- . ---
this is more
--- . ---
has_dict: true
---
more""", {
        'test': 2,
        'content': [
            {
                'content': 'whatever',
            },
            {
                'content': 'this is more',
            },
            {
                'content': 'more',
                'has_dict': True,
            }
        ]
    }
    )
])
def test_more_front_matter(s, result):
    obj, content = parse_front_matter(s)
    obj['content'] = split_content(content)
    assert obj == result
