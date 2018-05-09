from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import CloseToNow

from harrier.build import FileData, build_pages, content_templates
from harrier.common import HarrierProblem
from harrier.config import Config, Mode
from harrier.main import build
from harrier.render import render_pages


def test_full_build(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': (
                '{{ url("foobar.png") }}\n'
                '{{ resolve_url("theme/main.css") }}\n'
                '{{ resolve_url("another") }}\n'
            ),
            'another.md': '# Hello'
        },
        'theme': {
            'sass/main.scss': 'body {width: 10px + 10px;}',
            'assets/foobar.png': '*',
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': (
                '/foobar.3389dae.png\n'
                '/theme/main.a1ac3a7.css\n'
                '/another\n'
            ),
        },
        'another': {
            'index.html': '<h1 id="1-hello">Hello</h1>\n'
        },
        'theme': {
            'main.a1ac3a7.css': 'body{width:20px}\n',
        },
        'foobar.3389dae.png': '*',
    }


def test_build_no_templates(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                '### Whatever'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': (
                '<h3 id="3-whatever">Whatever</h3>\n'
            ),
        },
    }


def test_simple_render(tmpdir):
    foo_page = '# hello\n\nthis is a test foo: {{ foo }}'
    mktree(tmpdir, {
        'pages': {
            'foobar.md': foo_page,
            'spam.html': '# SPAM',
            'favicon.ico': '*',
        },
        'theme/templates/main.jinja': 'main, content:\n\n{{ content }}',
        'tmp/content/foobar.md': foo_page,
    })
    config = Config(
        source_dir=str(tmpdir),
        tmp_dir=str(tmpdir.join('tmp')),
        foo='bar',
    )

    som = {
        'pages': {
            'foobar.md': {
                'outfile': config.dist_dir / 'foobar.html',
                'infile': config.pages_dir / 'foobar.md',
                'template': 'main.jinja',
                'content_template': Path('content') / 'foobar.md',
            },
            'favicon.ico': {
                'outfile': config.dist_dir / 'favicon.ico',
                'infile': config.pages_dir / 'favicon.ico',
            },
        }
    }
    expected_tree = {
        'foobar.html': (
            'main, content:\n\n'
            '<h1 id="1-hello">hello</h1>\n\n'
            '<p>this is a test foo: </p>\n'
        ),
        'favicon.ico': '*',
    }
    assert not tmpdir.join('dist').check()

    assert render_pages(config, som) is None
    assert gettree(tmpdir.join('dist')) == expected_tree

    tmpdir.join('dist').remove(rec=1)
    assert not tmpdir.join('dist').check()

    cache = render_pages(config, som, {})
    assert gettree(tmpdir.join('dist')) == expected_tree
    assert len(cache) == 2

    tmpdir.join('dist').remove(rec=1)
    assert not tmpdir.join('dist').check()

    render_pages(config, som, cache)
    assert gettree(tmpdir.join('dist')) != expected_tree


def test_build_simple_som(tmpdir):
    mktree(tmpdir, {
        'dist/theme/assets/whatever.1234567.png': '**',
        'pages': {
            'foobar.md': '# hello\n\nthis is a test foo: {{ foo }}',
            'posts/2032-06-01-testing.html': '# testing',
            'static/image.png': '*',
        },
        'theme/templates/main.jinja': 'main, content:\n\n {{ content }}',
    })
    config = Config(
        source_dir=str(tmpdir),
        tmp_dir=str(tmpdir.join('tmp')),
        foo='bar',
        defaults={
            '/posts/*': {
                'uri': '/foobar/{slug}.html'
            }
        }
    )

    pages = build_pages(config)
    content_templates(pages.values(), config)
    source_dir = Path(tmpdir)
    # debug(som)
    assert {
        '/foobar.md': {
            'infile': source_dir / 'pages/foobar.md',
            'content_template': 'content/foobar.md',
            'title': 'foobar',
            'slug': 'foobar',
            'created': CloseToNow(),
            'uri': '/foobar',
            'template': None,
            'outfile': source_dir / 'dist/foobar/index.html',
            'content': (
                '# hello\n'
                '\n'
                'this is a test foo: {{ foo }}'
            ),
            'pass_through': False,
        },
        '/posts/2032-06-01-testing.html': {
            'infile': source_dir / 'pages/posts/2032-06-01-testing.html',
            'content_template': 'content/posts/2032-06-01-testing.html',
            'title': 'testing',
            'slug': 'testing',
            'created': datetime(2032, 6, 1, 0, 0),
            'uri': '/foobar/testing.html',
            'template': None,
            'outfile': source_dir / 'dist/foobar/testing.html',
            'content': '# testing',
            'pass_through': False,
        },
        '/static/image.png': {
            'infile': source_dir / 'pages/static/image.png',
            'title': 'image.png',
            'slug': 'image.png',
            'created': CloseToNow(),
            'uri': '/static/image.png',
            'outfile': source_dir / 'dist/static/image.png',
            'pass_through': True,
        }
    } == pages


def test_render_error(tmpdir, caplog):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': '{{ 1/0 }}',
        },
        'theme': {
            'templates/main.jinja': '{{ content }}',
        },
    })
    with pytest.raises(HarrierProblem):
        build(tmpdir, mode=Mode.production)
    assert 'ZeroDivisionError: division by zero' in caplog.text


def test_uri_key_error(tmpdir, caplog):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': (
                '---\n'
                'uri: "{foo}/whatever"\n'
                '---\n'
                'hello'
            ),
        },
        'theme': {
            'templates/main.jinja': '{{ content }}',
        },
    })
    with pytest.raises(KeyError):
        build(tmpdir, mode=Mode.production)
    assert 'missing format variable "foo" for "{foo}/whatever"' in caplog.text


def test_file_data_no_slash():
    with pytest.raises(ValidationError):
        FileData(
            infile='foo/bar.md',
            content_template='/tmp/x/bar.md',
            title='Bar',
            slug='bar',
            created=123,
            uri='bar',
            template=None,
        )


def test_file_data_illegal_char():
    with pytest.raises(ValidationError):
        FileData(
            infile='foo/bar.md',
            content_template='/tmp/x/bar.md',
            title='Bar',
            slug='bar',
            created=123,
            uri='/bar more',
            template=None,
        )
