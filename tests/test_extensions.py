from pathlib import Path

import pytest
from pytest_toolbox import gettree, mktree

from harrier.common import HarrierProblem
from harrier.extensions import ExtensionError, Extensions
from harrier.main import BuildSteps, build


def test_extensions_ok(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
            'bar.html': '{{ 4|add_one }} {{ dynamic }}',
            'spam.html': 'before',
            'splat.html': '{{ 3 is two }} {{ 2 is two }}',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': """
from harrier.extensions import modify, template

@modify.pages('/foo.*')
def modify_foo(page, config):
    page['content'] += ' changed by extension'
    return page

@modify.som
def add_var(site):
    site['dynamic'] = 42
    return site

@modify.som
def change_pages(site):
    site['pages']['/spam.html']['content'] = 'after'
    return site

@template.filter
def add_one(v):
    return v + 1

@template.test
def two(v):
    return v == 2
        """
    })

    build(str(tmpdir))
    assert gettree(tmpdir.join('dist')) == {
        'foo': {
            'index.html': '<h1 id="1-foo-changed-by-extension">foo changed by extension</h1>\n',
        },
        'bar': {
            'index.html': '5 42\n',
        },
        'spam': {
            'index.html': 'after\n',
        },
        'splat': {
            'index.html': 'False True\n',
        },
    }


def test_broken_ext(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': """
from harrier.extensions import modify

@modify.config
def before(site):
    pass
        """
    })

    with pytest.raises(HarrierProblem) as exc_info:
        build(str(tmpdir))
    assert exc_info.value.args[0] == 'extension "before" did not return a Config object as expected'


def test_ext_error(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': """
from harrier.extensions import modify

@modify.config
def before(site):
    raise RuntimeError('xxx')
        """
    })

    with pytest.raises(ExtensionError) as exc_info:
        build(str(tmpdir))
    assert exc_info.value.args[0] == 'xxx'


def test_pages_error(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'extensions.py': """
from harrier.extensions import modify

@modify.pages('**/*')
def modify_pages(data, config):
    raise ValueError('xxx')
        """
    })

    with pytest.raises(ExtensionError) as exc_info:
        build(str(tmpdir), steps={BuildSteps.pages})
    assert exc_info.value.args[0] == 'xxx'


def test_pages_broken(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': """
from harrier.extensions import modify

@modify.pages('**/*')
def modify_pages(data, config):
    return None
        """
    })

    with pytest.raises(ExtensionError) as exc_info:
        build(str(tmpdir))
    assert exc_info.value.args[0] == 'extension "modify_pages" did not return a dict'


def test_bad_python(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': 'xxx'
    })

    with pytest.raises(ExtensionError):
        build(str(tmpdir))


def test_load_template_methods(tmpdir):
    mktree(tmpdir, {
        'foobar.py': """
from harrier.extensions import modify, template

@modify.config
def before(site):
    pass

@modify.pages('x', 'y')
def modify_pages(data, config):
    pass

@template.function
def foobar(whatever):
    return str(whatever)
        """
    })
    ext = Extensions(Path(tmpdir.join('foobar.py')))
    assert str(ext) == '<Extensions not loaded>'
    ext.load()
    assert str(ext).startswith("<Extensions {'config_modifiers'")
    assert len(ext.config_modifiers) == 1
    assert len(ext.som_modifiers) == 0
    assert len(ext.page_modifiers) == 2
    assert len(ext.template_functions) == 1
    assert len(ext.template_filters) == 0


def test_page_modifier_bare(tmpdir):
    mktree(tmpdir, {
        'foobar.py': """
from harrier.extensions import modify

@modify.pages
def modify_pages(data, config):
    pass
        """
    })
    with pytest.raises(HarrierProblem) as exc_info:
        Extensions.validate(Path(tmpdir.join('foobar.py')))
    assert exc_info.value.args[0].startswith('modify.pages should be used with page globs as arguments, not bare.')


def test_page_modifier_no_args(tmpdir):
    mktree(tmpdir, {
        'foobar.py': """
from harrier.extensions import modify

@modify.pages()
def modify_pages(data, config):
    pass
        """
    })
    with pytest.raises(HarrierProblem) as exc_info:
        Extensions.validate(Path(tmpdir.join('foobar.py')))
    assert exc_info.value.args[0] == 'modify.pages with no file globs specified'


def test_copy_extensions(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': 'hello',
        },
        'theme/assets': {
            'image1.png': 'a',
            'image2.png': 'c',
            'foo/bar.svg': 'c',
        },
        'extensions.py': """
from harrier.extensions import modify, template

@modify.copy('/foo/*')
def modify_foo(in_path, out_path, config):
    out_path.write_text(f'{in_path.name} {in_path.read_text()} custom')
    return 1  # prevent default copy

@modify.copy('/image2.png')
def print_in_path(in_path, out_path, config):
    out_path.with_name(out_path.name + '.alt').write_bytes(in_path.read_bytes() + b'2')
    # return nothing so normal copy also happens
    """
    })

    build(str(tmpdir))
    assert gettree(tmpdir.join('dist')) == {
        'index.html': 'hello\n',
        'foo': {
            'bar.4a8a08f.svg': 'bar.svg c custom',
        },
        'image1.0cc175b.png': 'a',
        'image2.4a8a08f.png': 'c',
        'image2.4a8a08f.png.alt': 'c2',
    }


def test_copy_extensions_error(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': 'hello',
        },
        'theme/assets': {
            'foo/bar.svg': 'b',
        },
        'extensions.py': """
from harrier.extensions import modify, template

@modify.copy('/foo/*')
def modify_foo(in_path, out_path, config):
    raise RuntimeError('x')
    """
    })
    with pytest.raises(ExtensionError):
        build(str(tmpdir))


def test_generate_pages(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': 'hello',
        },
        'extensions.py': """
from pathlib import Path
from harrier.extensions import modify
THIS_DIR = Path(__file__).parent.resolve()

@modify.generate_pages
def add_extra_pages(som):
    config: Config = som['config']
    yield {
        'path': Path('extra/index.md'),
        'content': '# this is a test\\n\\nwith of generating pages dynamically',
    }
    yield {
        'path': Path('more/index.html'),
        'content': 'testing {{ page.x }}',
        'data': {
            'uri': '/foo-bar-whatever',
            'x': 123,
        }
    }
    (THIS_DIR / 'pages' / 'binary_file').write_bytes(b'xxx')
    yield {
        'path': 'binary_file',
        'content': None,
    }
    """
    })
    build(str(tmpdir))
    assert gettree(tmpdir.join('dist')) == {
        'extra': {
            'index.html': (
                '<h1 id="1-this-is-a-test">this is a test</h1>\n'
                '\n'
                '<p>with of generating pages dynamically</p>\n'
            ),
        },
        'foo-bar-whatever': {
            'index.html': 'testing 123\n'
        },
        'index.html': 'hello\n',
        'binary_file': 'xxx',
    }


def test_post_page_render(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.md': (
                '[Whatever](https://google.com)'
            ),
        },
        'extensions.py': """
from pathlib import Path
from harrier.extensions import modify
THIS_DIR = Path(__file__).parent.resolve()


@modify.post_page_render
def add_nofollow(page, html):
    return html.replace('google', 'foobar')
    """
    })
    build(str(tmpdir))
    assert gettree(tmpdir.join('dist')) == {
        'index.html': (
            '<p><a href="https://foobar.com">Whatever</a></p>\n'
        ),
    }


def test_generate_pages_invalid(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': 'hello',
        },
        'extensions.py': """
from pathlib import Path
from harrier.extensions import modify

@modify.generate_pages
def add_extra_pages(som):
    config: Config = som['config']
    yield {
        'path': Path('extra/index.md'),
        'content': [1, 2, 3],
    }
    """
    })
    with pytest.raises(ExtensionError):
        build(str(tmpdir))


def test_generate_pages_error(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'index.html': 'hello',
        },
        'extensions.py': """
from pathlib import Path
from harrier.extensions import modify

@modify.generate_pages
def add_extra_pages(som):
    raise RuntimeError('xx')
    """
    })
    with pytest.raises(ExtensionError):
        build(str(tmpdir))
