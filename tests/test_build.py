from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import CloseToNow

from harrier.build import FileData, build_pages, render_pages
from harrier.common import PathMatch
from harrier.config import Config, Mode
from harrier.main import build


def test_full_build(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': (
                '{{url("theme/assets/foobar.png")}}\n'
                '{{url("theme/main.css")}}'
            ),
        },
        'theme': {
            'templates/main.jinja': '{{ content }}',
            'sass/main.scss': 'body {width: 10px + 10px;}',
            'assets/foobar.png': '*',
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': (
                'theme/assets/foobar.3389dae.png\n'
                'theme/main.a1ac3a7.css\n'
            ),
        },
        'theme': {
            'main.a1ac3a7.css': 'body{width:20px}\n',
            'assets': {
                'foobar.3389dae.png': '*',
            },
        },
    }


def test_build_no_templates(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                '# whatever'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': (
                '<h1>whatever</h1>\n'
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
        'spam.html': '# SPAM\n'
    }
    assert not tmpdir.join('dist').check()

    assert render_pages(config, som) is None
    assert gettree(tmpdir.join('dist')) == expected_tree

    tmpdir.join('dist').remove(rec=1)
    assert not tmpdir.join('dist').check()

    cache = render_pages(config, som, {})
    assert gettree(tmpdir.join('dist')) == expected_tree
    assert len(cache) == 3

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

    som = config.dict()
    som['pages'] = build_pages(config)
    source_dir = Path(tmpdir)
    # debug(som)
    assert {
        'source_dir': source_dir,
        'extensions': {
            'config_modifiers': [],
            'som_modifiers': [],
            'page_modifiers': [],
            'template_filters': {},
            'template_functions': {},
        },
        'mode': Mode.production,
        'pages_dir': source_dir / 'pages',
        'theme_dir': source_dir / 'theme',
        'data_dir': source_dir / 'data',
        'dist_dir': source_dir / 'dist',
        'dist_dir_sass': Path('theme'),
        'dist_dir_assets': Path('theme/assets'),
        'tmp_dir': source_dir / 'tmp',
        'download': {},
        'download_aliases': {},
        'default_template': None,
        'defaults': {
            PathMatch('/posts/*'): {
                'uri': '/foobar/{slug}.html',
            },
        },
        'ignore': [],
        'webpack': {
            'cli': source_dir / 'node_modules/.bin/webpack-cli',
            'entry': source_dir / 'theme/js/index.js',
            'output_path': source_dir / 'dist/theme',
            'dev_output_filename': 'main.js',
            'prod_output_filename': 'main.[hash].js',
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
                'template': None,
                'render': True,
                'outfile': source_dir / 'dist/foobar/index.html',
                '__file__': 1,
            },
            'posts/2032-06-01-testing.html': {
                'infile': source_dir / 'pages/posts/2032-06-01-testing.html',
                'content_template': 'content/posts/2032-06-01-testing.html',
                'title': 'testing',
                'slug': 'testing',
                'created': datetime(2032, 6, 1, 0, 0),
                'uri': '/foobar/testing.html',
                'template': None,
                'render': True,
                'outfile': source_dir / 'dist/foobar/testing.html',
                '__file__': 1,
            },
            'static/image.png': {
                'infile': source_dir / 'pages/static/image.png',
                'title': 'image.png',
                'slug': 'image.png',
                'created': CloseToNow(),
                'uri': '/static/image.png',
                'outfile': source_dir / 'dist/static/image.png',
                '__file__': 1,
            }

        },
    } == som


def test_render_error(tmpdir, caplog):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': '{{ 1/0 }}',
        },
        'theme': {
            'templates/main.jinja': '{{ content }}',
        },
    })
    with pytest.raises(ZeroDivisionError):
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


def test_build_multi_part(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'multipart_list.md': (
                '---\n'
                'uri: /list_md.html\n'
                'template: list.jinja\n'
                '---\n'
                'part 1\n'
                '--- . ---\n'
                'part **2**\n'
                '---.---\n'
                'this is part *3*\n'
            ),
            'multipart_dict.md': (
                '---\n'
                'uri: /dict_md.html\n'
                'template: dict.jinja\n'
                '---\n'
                'the main **section**\n'
                '--- other ---\n'
                'part *2*\n'
            ),
            'multipart_list.html': (
                '---\n'
                'uri: /list_html.html\n'
                'template: list.jinja\n'
                '---\n'
                'part 1\n'
                '--- . ---\n'
                'part 2\n'
                '---.---\n'
                'this is part 3\n'
            ),
            'multipart_dict.html': (
                '---\n'
                'uri: /dict_html.html\n'
                'template: dict.jinja\n'
                '---\n'
                'the main section\n'
                '--- other ---\n'
                'part 2\n'
            ),
        },
        'theme': {
            'templates/': {
                'list.jinja': (
                    '{% for v in content %}\n'
                    '  {{ v}}\n'
                    '{% endfor %}\n'
                ),
                'dict.jinja': (
                    '{{ content.main }}\n'
                    '{{ content.other }}\n'
                ),
            },
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'list_md.html': (
            '\n'
            '  <p>part 1</p>\n'
            '\n\n'
            '  <p>part <strong>2</strong></p>\n'
            '\n\n'
            '  <p>this is part <em>3</em></p>\n'
        ),
        'dict_md.html': (
            '<p>the main <strong>section</strong></p>\n'
            '\n'
            '<p>part <em>2</em></p>\n'
        ),
        'list_html.html': (
            '\n'
            '  part 1\n'
            '\n'
            '  part 2\n'
            '\n'
            '  this is part 3\n'
        ),
        'dict_html.html': (
            'the main section\n'
            'part 2\n'
        ),
    }


def test_ignore_no_template(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'ignore_this.md': 'this file is ignored',
            'normal.md': 'hello this is normal',
            'no_template.md': 'this should be rendered as-is',
            'normal_but_no_output.md': (
                '---\n'
                'output: false\n'
                '---\n'
                'hello this is normal\n'
            )
        },
        'theme': {
            'templates/foobar.jinja': 'rendered {{ content }}',
        },
        'harrier.yml': (
            'default_template: "foobar.jinja"\n'
            'ignore:\n'
            '- "**/ignore*"\n'
            'defaults:\n'
            '  "/no_temp*":\n'
            '    apply_template: false\n'
        )
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'no_template': {
            'index.html': 'this should be rendered as-is',
        },
        'normal': {
            'index.html': 'rendered <p>hello this is normal</p>\n',
        },

    }


def test_xml_front_matter(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.xml': (
                '---\n'
                'foo: bar\n'
                '---\n'
                '<x><y>{{ site.whatever }}</y></x>'
            ),
        },
        'harrier.yml': 'whatever: 123'
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar.xml': '<x><y>123</y></x>\n'
    }


def test_xml_no_front_matter(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.xml': (
                '<x><y>{{ site.whatever }}</y></x>'
            ),
        },
        'harrier.yml': 'whatever: 123'
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar.xml': '<x><y>{{ site.whatever }}</y></x>'
    }


def test_file_data_ok():
    fd = FileData(
        infile='foo/bar.md',
        content_template='/tmp/x/bar.md',
        title='Bar',
        slug='bar',
        created=123,
        uri='/bar',
        template=None,
    )
    assert fd.infile == Path('foo/bar.md')


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
