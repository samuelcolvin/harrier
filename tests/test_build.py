from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import CloseToNow, RegexStr

from harrier.build import FileData, build_pages, content_templates, render_pages
from harrier.common import HarrierProblem, PathMatch
from harrier.config import Config, Mode
from harrier.main import build


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

    som = config.dict()
    pages = build_pages(config)
    som['pages'] = content_templates(pages, config)
    source_dir = Path(tmpdir)
    # debug(som)
    assert {
        'source_dir': source_dir,
        'config_path': None,
        'build_time': CloseToNow(),
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
        'dist_dir_assets': Path('.'),
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
            'cli': None,
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
                'outfile': source_dir / 'dist/foobar/index.html',
                'content': (
                    '# hello\n'
                    '\n'
                    'this is a test foo: {{ foo }}'
                ),
                'pass_through': False,
            },
            'posts/2032-06-01-testing.html': {
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
            'static/image.png': {
                'infile': source_dir / 'pages/static/image.png',
                'title': 'image.png',
                'slug': 'image.png',
                'created': CloseToNow(),
                'uri': '/static/image.png',
                'outfile': source_dir / 'dist/static/image.png',
                'pass_through': True,
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
                    '  {{ v.content }}\n'
                    '{% endfor %}\n'
                ),
                'dict.jinja': (
                    '{{ content.main.content }}\n'
                    '{{ content.other.content }}\n'
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
            'no_template.md': 'this should be passed through as-is',
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
            '    pass_through: true\n'
        )
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'no_template': {
            'index.html': 'this should be passed through as-is',
        },
        'normal': {
            'index.html': 'rendered <p>hello this is normal</p>\n',
        },

    }


def test_inline_css_prod(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.html': '{{inline_css("theme/main.css")}}'
        },
        'theme': {
            'sass/main.scss': 'body {width: 10px + 10px;}',
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': (
                'body{width:20px}\n'
            ),
        },
        'theme': {
            'main.a1ac3a7.css': 'body{width:20px}\n',
        },
    }


def test_inline_css_dev(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.html': '{{inline_css("theme/main.css")}}',
            'bar.html': "{{ url('theme/main.css') }}",
        },
        'theme': {
            'sass/main.scss': 'body {width: 10px + 10px;}',
        },
    })
    som = build(tmpdir, mode=Mode.development)
    assert gettree(tmpdir.join('dist')) == {
        'foo': {
            'index.html': (
                'body {\n'
                '  width: 20px; }\n'
                '\n'
                '/*# sourceMappingURL=/theme/main.css.map */\n'
            ),
        },
        'bar': {
            'index.html': f'/theme/main.css?t={som["config"].build_time:%s}\n',
        },
        'theme': {
            'main.css.map': RegexStr('{.*'),
            'main.css': (
                'body {\n'
                '  width: 20px; }\n'
                '\n'
                '/*# sourceMappingURL=main.css.map */'
            ),
            '.src': {
                'main.scss': 'body {width: 10px + 10px;}',
            },
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


def test_render_code_lang(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                'testing\n\n'
                '```py\n'
                'x = 4\n'
                '```\n'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert tmpdir.join('dist/foobar/index.html').read_text('utf8') == (
        '<p>testing</p>\n'
        '<div class="hi"><pre><span></span><span class="n">x</span> '
        '<span class="o">=</span> <span class="mi">4</span>\n'
        '</pre></div>\n'
    )


def test_render_code_unknown_lang(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                'testing\n\n'
                '```notalanguage\n'
                'x = 4\n'
                '```\n'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert tmpdir.join('dist/foobar/index.html').read_text('utf8') == (
        '<p>testing</p>\n'
        '<pre><code>x = 4</code></pre>\n'
    )


def test_list_not_dd(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                '* whatever\n'
                '* thing:: other\n'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert tmpdir.join('dist/foobar/index.html').read_text('utf8') == (
        '<li>whatever</li>\n'
        '<li>thing:: other</li>\n'
    )


def test_list_dd(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': (
                '* name:: whatever\n'
                '* thing:: other\n'
            ),
        },
    })
    build(tmpdir, mode=Mode.production)
    assert tmpdir.join('dist/foobar/index.html').read_text('utf8') == (
        '<dl>\n'
        '  <dt>name</dt><dd> whatever</dd>\n'
        '  <dt>thing</dt><dd> other</dd>\n'
        '</dl>\n'
    )


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
