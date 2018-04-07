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
        },
        'theme': {
            'templates': {
                'main.jinja': 'main, content:\n\n {{ content }}'
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
            'foobar': {
                'outfile': config.dist_dir / 'foobar.html',
                'infile': config.pages_dir / 'foobar.md',
                'template': 'main.jinja',
                'render': True,
                'content_template': Path('content') / 'foobar.md',
                '__file__': 1,
            }
        }
    }
    assert not tmpdir.join('dist').check()
    render(config, som)
    assert gettree(tmpdir.join('dist')) == {
        'foobar.html': (
            'main, content:\n'
            '\n'
            ' <h1>hello</h1>\n'
            '\n'
            '<p>this is a test foo: </p>\n'
        ),
    }


def test_build_simple_som(tmpdir):
    foo_page = '# hello\n\nthis is a test foo: {{ foo }}'
    mktree(tmpdir, {
        'pages': {
            'foobar.md': foo_page,
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
    )
    som = build_som(config)
    source_dir = Path(tmpdir)
    assert {
        'source_dir': source_dir,
        'pages_dir': source_dir / 'pages',
        'theme_dir': source_dir / 'theme',
        'data_dir': source_dir / 'data',
        'dist_dir': source_dir / 'dist',
        'dist_dir_sass': Path('theme'),
        'theme_assets_dir': Path('theme/assets'),
        'tmp_dir': source_dir / 'tmp',
        'download': {},
        'download_aliases': {},
        'defaults': {},
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
                'uri': '/./foobar',
                'template': 'main.jinja',
                'render': True,
                'outfile': source_dir / 'dist/foobar/index.html',
                '__file__': 1,
            },
        },
        'data': {},
    } == som
