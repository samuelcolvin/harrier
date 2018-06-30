from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import RegexStr

from harrier.build import FileData
from harrier.config import Mode
from harrier.main import build
from harrier.render import json_filter, paginate_filter


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
    build(tmpdir, mode=Mode.development)
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
            'index.html': RegexStr(r'/theme/main.css\?t=\d+\n'),
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


def test_frontmatter_maybe(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.xml': (
                '---\n'
                'foo: bar\n'
                '---\n'
                '<x><y>{{ config.whatever }}</y></x>'
            ),
            'foobar.txt': (
                '---\n'
                'x: 1\n'
                '---\n'
                '{{ page.x }}'
            ),
        },
        'harrier.yml': 'whatever: 123'
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar.xml': '<x><y>123</y></x>\n',
        'foobar.txt': '1\n',
    }


def test_xml_no_front_matter(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.xml': (
                '<x><y>{{ config.whatever }}</y></x>'
            ),
        },
        'harrier.yml': 'whatever: 123'
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'foobar.xml': '<x><y>{{ config.whatever }}</y></x>'
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


@pytest.mark.parametrize('input,output', [
    (
        '_this should be emphasised_',
        '<p><em>this should be emphasised</em></p>\n'
    ),
    (
        (
            'testing\n\n'
            '```notalanguage\n'
            'x = 4\n'
            '```\n'
        ),
        (
            '<p>testing</p>\n'
            '<pre><code>x = 4</code></pre>\n'
        )
    ),
    (
        '___this should be underlined___',
        '<p><u>this should be underlined</u></p>\n'
    ),
    (
        '***this should be underlined***',
        '<p><u>this should be underlined</u></p>\n'
    ),
    (
        (
            '* foo\n'
            '* bar\n'
            '* spam\n'
        ),
        (
            '<ul>\n'
            '<li>foo</li>\n'
            '<li>bar</li>\n'
            '<li>spam</li>\n'
            '</ul>\n'
        )
    ),
    (
        (
            '1. i am\n'
            '2. ordered\n'
            '2. with numbers\n'
        ),
        (
            '<ol>\n'
            '<li>i am</li>\n'
            '<li>ordered</li>\n'
            '<li>with numbers</li>\n'
            '</ol>\n'
        )
    ),
    (
        (
            '* whatever\n'
            '* thing:: other\n'
        ),
        (
            '<ul>\n'
            '<li>whatever</li>\n'
            '<li>thing:: other</li>\n'
            '</ul>\n'
        )
    ),
    (
        (
            '* name:: whatever\n'
            '* thing:: other\n'
        ),
        (
            '<dl>\n'
            '  <dt>name</dt><dd> whatever</dd>\n'
            '  <dt>thing</dt><dd> other</dd>\n'
            '</dl>\n'
        )
    )
])
def test_markdown_extensions(input, output, tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': input,
        },
    })
    build(tmpdir, mode=Mode.production)
    assert tmpdir.join('dist/foobar/index.html').read_text('utf8') == output


@pytest.mark.parametrize('input,output', [
    (
        '{{ [1,2,3]|batch(2)|tojson }}',
        '[[1, 2], [3]]\n'
    ),
    (
        '{{ [1,2,3,"hello"]|debug }}',
        (
            '<pre '
            'style="white-space:pre-wrap;background:#444;color:white;border-radius:5px;padding:10px;font-size:13px">'
            '\n[\n'
            '    1,\n'
            '    2,\n'
            '    3,\n'
            "    'hello',\n"
            '] (type=list length=4)\n'
            '</pre>\n'
        )
    ),
    (
        '{{ [1,2,3]|batch(2)|debug(html=False) }}',
        (
            '(\n'
            '    [1, 2],\n'
            '    [3],\n'
            ') (type=generator length=-)\n'
        )
    ),
    (
        '{{ 3|debug(html=False) }}',
        (
            '3 (type=int length=-)\n'
        )
    ),
    (
        '{{ "this is some **markdown**"|markdown }}',
        (
            '<p>this is some <strong>markdown</strong></p>\n'
        )
    ),
    (
        '{% for p in [1,2,3,4,5]|paginate(2) %}{{ p }}|{% endfor %}',
        (
            '4|5|\n'
        )
    ),
    (
        "{{ width('image.png') }} {{ height('image.png') }}",
        (
            '60 30\n'
        )
    ),
    (
        "{{ width('image.png') }} {{ width('image.png') }} {{ width('image.png') }}",
        (
            '60 60 60\n'
        )
    ),
])
def test_jinja_functions(input, output, tmpdir):
    mktree(tmpdir, {
        'pages/index.html': input,
        'theme/assets': {},
        'harrier.yml': 'paginate_by: 3',
    })
    img = Image.new('RGB', (60, 30), (255, 255, 255))
    img.save(str(tmpdir.join('theme/assets/image.png')), 'PNG')

    build(tmpdir, mode=Mode.production)
    # debug(tmpdir.join('dist/index.html').read_text('utf8'))
    assert tmpdir.join('dist/index.html').read_text('utf8') == output.replace('{tmpdir}', str(tmpdir))


@pytest.mark.parametrize('input,output', [
    (
        'this is **before**\n'
        '{% markdown %}\n'
        '  # whatever\n'
        '  some **content**\n'
        '{% endmarkdown %}\n'
        'this is **after**\n',

        'this is **before**\n'
        '<h1 id="1-whatever">whatever</h1>\n'
        '\n'
        '<p>some <strong>content</strong></p>\n'
        '\n'
        'this is **after**\n'
    ),
    (
        '{% markdown %}\n'
        '  # whatever\n'
        '  some **{{ 1 + 1 }}**\n'
        '{% endmarkdown %}\n',

        '<h1 id="1-whatever">whatever</h1>\n'
        '\n'
        '<p>some <strong>2</strong></p>\n'
    ),
    (
        '{% markdown %}\n'
        '    this is code:\n\n'
        '        7 = 4 + 3\n\n'
        '{% endmarkdown %}\n',

        '<p>this is code:</p>\n'
        '<pre><code>7 = 4 + 3</code></pre>\n'
    ),
])
def test_jinja_md_extensions(input, output, tmpdir):
    mktree(tmpdir, {
        'pages/index.html': input,
    })
    build(tmpdir, mode=Mode.production)
    # debug(tmpdir.join('dist/index.html').read_text('utf8'))
    assert tmpdir.join('dist/index.html').read_text('utf8') == output


@pytest.mark.parametrize('input,output', [
    (
        {'x': datetime(2032, 6, 1)},
        '{"x": "2032-06-01T00:00:00"}'
    ),
    (
        {'x': b'123'},
        '{"x": "123"}'
    ),
    (
        {'x': type('Foobar', (), {'__repr__': lambda s: 'Foobar repr output'})()},
        '{"x": "Foobar repr output"}'
    ),
])
def test_json_filter(input, output):
    assert json_filter(input) == output


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


@pytest.mark.parametrize('infile,outfile', [
    (
        '{% for page in pages|glob("*")|sort(attribute="uri") -%}\n'
        '<a href="{{ page.uri }}">{{ page.title }}</a>\n'
        '{% endfor %}\n',

        '<a href="/">Index</a>\n'
        '<a href="/foobar/">Foobar</a>\n'
        '<a href="/robots.txt">robots.txt</a>\n'
        '<a href="/testing/">Testing</a>\n'
    ),
    (
        '{% for page in pages|glob("*.txt") -%}\n'
        '<a href="{{ page.uri }}">{{ page.title }}</a>\n'
        '{% endfor %}\n',

        '<a href="/robots.txt">robots.txt</a>\n'
    ),
    (
        '{% for page in pages|glob("**/*.html", test="path") -%}\n'
        '<a href="{{ page.uri }}">{{ page.title }}</a>\n'
        '{% endfor %}\n',

        '<a href="/">Index</a>\n'
        '<a href="/testing/">Testing</a>\n'
    ),
])
def test_pages_function(infile, outfile, tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': '1',
            'foobar.md': '2',
            'robots.txt': '3',
            'testing.html': infile,
        }
    })
    build(tmpdir, mode=Mode.production)
    # debug(tmpdir.join('dist/testing/index.html').read_text('utf8'))
    assert tmpdir.join('dist/testing/index.html').read_text('utf8') == outfile


def test_jinja_format(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': '{{"{:0.2f}"|format(3.1415)}}',
            '2032-06-02-date.txt': '---\nx: 1\n---\n{{ "{:%b %d, %Y}"|format(page.created) }}',
        },
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'index.html': '3.14\n',
        'date.txt': 'Jun 02, 2032\n'
    }


def test_paginate_filter():
    v = ['a', 'b', 'c', 'd', 'e']
    ctx = {'config': type('Config', (), {'paginate_by': 20})}
    assert paginate_filter(ctx, v) == v
    assert paginate_filter(ctx, v, 2) == []
    assert paginate_filter(ctx, v, 1, 2) == ['a', 'b']
    assert paginate_filter(ctx, v, 2, 2) == ['c', 'd']


def test_no_trailing_slash(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': '<a href="{{ url("other") }}">link to other</a>',
            'other.html': 'xxx'
        },
        'harrier.yml': 'apply_trailing_slash: false'
    })
    build(tmpdir, mode=Mode.production)
    assert gettree(tmpdir.join('dist')) == {
        'other': {
            'index.html': 'xxx\n',
        },
        'index.html': '<a href="/other">link to other</a>\n',
    }
