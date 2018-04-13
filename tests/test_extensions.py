from pathlib import Path

import pytest
from pytest_toolbox import gettree, mktree

from harrier.common import HarrierProblem
from harrier.extensions import Extensions
from harrier.main import build


def test_extensions_ok(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
            'bar.html': '{{ 4|add_one }} {{ site.dynamic }}',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': """
from harrier.extensions import modify, template

@modify.pages('/foo.*')
def modify_foo(page, config):
    page['content'] += ' changed by extension'
    return page

@modify.som
def post_build(site):
    site['dynamic'] = 42
    return site

@template.filter
def add_one(v):
    return v + 1
        """
    })

    build(str(tmpdir))
    assert gettree(tmpdir.join('dist')) == {
        'foo': {
            'index.html': '<h1>foo changed by extension</h1>\n',
        },
        'bar': {
            'index.html': '5 42\n',
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


def test_bad_python(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
        },
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': 'xxx'
    })

    with pytest.raises(NameError):
        build(str(tmpdir))


def test_load_template_methods(tmpdir):
    mktree(tmpdir, {
        'foobar.py': """
from harrier.extensions import modify, template

@modify.config
def before(site):
    pass

@modify.pages('x', 'y')
def modify_pages(site):
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
def modify_pages(site):
    pass
        """
    })
    with pytest.raises(HarrierProblem) as exc_info:
        Extensions.validate(Path(tmpdir.join('foobar.py')))
    assert exc_info.value.args[0].startswith('modify_pages should be used with page globs as arguments, not bare.')


def test_page_modifier_no_args(tmpdir):
    mktree(tmpdir, {
        'foobar.py': """
from harrier.extensions import modify

@modify.pages()
def modify_pages(site):
    pass
        """
    })
    with pytest.raises(HarrierProblem) as exc_info:
        Extensions.validate(Path(tmpdir.join('foobar.py')))
    assert exc_info.value.args[0] == 'validator with no page globs specified'
