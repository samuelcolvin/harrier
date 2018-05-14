import pytest
from pytest_toolbox import mktree

from harrier.common import HarrierProblem
from harrier.config import Config
from harrier.data import load_data


def test_ok(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates': '{{ content }}',
        'data': {
            'path/to': {
                'foo.csv': (
                    'fruit, colour, price\n'
                    'apple, green, 1\n'
                    'banana, yellow, 2\n'
                    'raspberry, red, 3\n'
                ),
                'other.json': '[1,2,3]',
            },
            'happy people.json': '{"name": "spanner", "v": 123}',
            'sp$am.yaml': (
                'a: B\n'
                'b: 123.456\n'
                'c: false\n'
            ),
        }
    })

    config = Config(source_dir=tmpdir)
    data = load_data(config)
    assert data == {
        'happy_people': {
            'name': 'spanner',
            'v': 123,
        },
        'path': {
            'to': {
                'other': [1, 2, 3],
                'foo': [
                    {
                        'fruit': 'apple',
                        'colour': 'green',
                        'price': '1',
                    },
                    {
                        'fruit': 'banana',
                        'colour': 'yellow',
                        'price': '2',
                    },
                    {
                        'fruit': 'raspberry',
                        'colour': 'red',
                        'price': '3',
                    },
                ],
            },
        },
        'spam': {
            'a': 'B',
            'b': 123.456,
            'c': False,
        },
    }


def test_duplicate(tmpdir, caplog):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates': '{{ content }}',
        'data': {
            'path/to': {
                'foo.csv': (
                    'fruit, colour, price\n'
                    'apple, green, 1\n'
                ),
                'foo.json': '{"name": "spanner", "v": 123}'
            }
        }
    })

    config = Config(source_dir=tmpdir)
    data = load_data(config)
    assert data == {
        'path': {
            'to': {
                'foo': {'name': 'spanner', 'v': 123}
            }
        }
    }
    assert 'duplicate data key "path.to.foo"' in caplog.text


def test_invalid_yaml(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates': '{{ content }}',
        'data': {
            'foo.yaml': '1 : 2 : 3'
        }
    })

    config = Config(source_dir=tmpdir)
    with pytest.raises(HarrierProblem):
        load_data(config)
