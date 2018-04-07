from datetime import datetime
from pathlib import Path

from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import CloseToNow

from harrier.build import build_som, render
from harrier.config import Config


def test_simple_render(tmpdir):
    foo_page = '# hello\n\nthis is a test foo: {{ foo }}'
    mktree(tmpdir, {
        'pages': {
            'foobar.md': foo_page,
            'spam.html': '# SPAM',
            'favicon.ico': '*',
        },
        'theme': {
            'templates': {
                'main.jinja': 'main, content:\n\n{{ content }}'
            }
        },
        'tmp': {
            'content': {
                'foobar.md': foo_page,
            }
        }
    })
    config = Config(
        source_dir=str(tmpdir),
        dist_dir=str(tmpdir.join('dist')),
        tmp_dir=str(tmpdir.join('tmp')),
        foo='bar',
    )

    som = {
        'pages': {
            'foobar.md': {
                'outfile': config.dist_dir / 'foobar.html',
                'infile': config.pages_dir / 'foobar.md',
                'template': 'main.jinja',
                'render': True,
                'content_template': Path('content') / 'foobar.md',
                '__file__': 1,
            },
            'spam.html': {
                'outfile': config.dist_dir / 'spam.html',
                'infile': config.pages_dir / 'spam.html',
                'template': None,
                'render': False,
                'content': '# SPAM',
                '__file__': 1,
            },
            'favicon.ico': {
                'outfile': config.dist_dir / 'favicon.ico',
                'infile': config.pages_dir / 'favicon.ico',
                '__file__': 1,
            },
        }
    }
    expected_tree = {
        'foobar.html': (
            'main, content:\n\n'
            '<h1>hello</h1>\n\n'
            '<p>this is a test foo: </p>\n'
        ),
        'favicon.ico': '*',
        'spam.html': '# SPAM'
    }
    assert not tmpdir.join('dist').check()

    assert render(config, som) is None
    assert gettree(tmpdir.join('dist')) == expected_tree

    tmpdir.join('dist').remove(rec=1)
    assert not tmpdir.join('dist').check()

    cache = render(config, som, {})
    assert gettree(tmpdir.join('dist')) == expected_tree
    assert len(cache) == 3

    tmpdir.join('dist').remove(rec=1)
    assert not tmpdir.join('dist').check()

    cache = render(config, som, cache)
    assert gettree(tmpdir.join('dist')) != expected_tree


def test_build_simple_som(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello\n\nthis is a test foo: {{ foo }}',
            'posts': {
                '2032-06-01-testing.html': '# testing'
            },
            'static': {
                'image.png': '*'
            }
        },
        'theme': {
            'templates': {
                'main.jinja': 'main, content:\n\n {{ content }}'
            }
        },
    })
    config = Config(
        source_dir=str(tmpdir),
        dist_dir=str(tmpdir.join('dist')),
        tmp_dir=str(tmpdir.join('tmp')),
        foo='bar',
        defaults={
            'posts': {
                'uri': '/foobar/{slug}.html'
            }
        }
    )
    som = build_som(config)
    source_dir = Path(tmpdir)
    # debug(som)
    assert {
        'source_dir': source_dir,
        'pages_dir': source_dir / 'pages',
        'extensions': {
            'page_modifiers': [],
            'post_modifiers': [],
            'pre_modifiers': [],
            'template_filters': {},
            'template_functions': {},
        },
        'theme_dir': source_dir / 'theme',
        'data_dir': source_dir / 'data',
        'dist_dir': source_dir / 'dist',
        'dist_dir_sass': Path('theme'),
        'dist_dir_assets': Path('theme/assets'),
        'tmp_dir': source_dir / 'tmp',
        'download': {},
        'download_aliases': {},
        'defaults': {
            'posts': {
                'uri': '/foobar/{slug}.html',
            },
        },
        'webpack': {
            'cli': source_dir / 'node_modules/.bin/webpack-cli',
            'entry': source_dir / 'theme/js/index.js',
            'output_path': source_dir / 'dist/theme',
            'output_filename': 'main.js',
            'config': None,
            'run': False,
        },
        'foo': 'bar',
        'pages': {
            'foobar.md': {
                'infile': source_dir / 'pages/foobar.md',
                'content_template': 'content/foobar.md',
                'title': 'foobar',
                'slug': 'foobar',
                'created': CloseToNow(),
                'uri': '/foobar',
                'template': 'main.jinja',
                'render': True,
                'outfile': source_dir / 'dist/foobar/index.html',
                '__file__': 1,
            },
            'posts': {
                '2032-06-01-testing.html': {
                    'infile': source_dir / 'pages/posts/2032-06-01-testing.html',
                    'content_template': 'content/posts/2032-06-01-testing.html',
                    'title': 'testing',
                    'slug': 'testing',
                    'created': datetime(2032, 6, 1, 0, 0),
                    'uri': '/foobar/testing.html',
                    'template': 'main.jinja',
                    'render': True,
                    'outfile': source_dir / 'dist/foobar/testing.html',
                    '__file__': 1,
                },
            },
            'static': {
                'image.png': {
                    'infile': source_dir / 'pages/static/image.png',
                    'title': 'image.png',
                    'slug': 'image.png',
                    'created': CloseToNow(),
                    'uri': '/static/image.png',
                    'outfile': source_dir / 'dist/static/image.png',
                    '__file__': 1,
                },
            }

        },
        'data': {},
    } == som
