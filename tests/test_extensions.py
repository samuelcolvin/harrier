import pytest
from pytest_toolbox import gettree, mktree

from harrier.common import HarrierProblem
from harrier.main import build


def test_copy_assets(tmpdir):
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

@modify.post
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

@modify.post
def post_build(site):
    pass
        """
    })

    with pytest.raises(HarrierProblem) as exc_info:
        build(str(tmpdir))
    assert exc_info.value.args[0] == 'extension "post_build" did not return a dict as expected'


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
