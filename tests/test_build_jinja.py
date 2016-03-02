import pytest

from harrier.build import build
from harrier.common import HarrierProblem
from harrier.config import load_config

from .conftest import gettree, mktree


def test_jinja(tmpworkdir):
    tmpworkdir.join('index.html').write('{{ 42 + 5 }}')
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'index.html': '47'}


def test_jinja_live(tmpworkdir):
    tmpworkdir.join('index.html').write('{{ 42 + 5 }}')
    config = load_config(None)
    config.setup('build', True)
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'index.html': '47\n<script src="http://localhost:8000/livereload.js"></script>\n',
    }


def test_jinja_static(tmpworkdir):
    tmpworkdir.join('foo.txt').write('hello')
    tmpworkdir.join('index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'index.html': 'foo.txt', 'foo.txt': 'hello'}


def test_jinja_static_relpath(tmpworkdir):
    tmpworkdir.mkdir('path')
    tmpworkdir.join('path', 'foo.txt').write('hello')
    tmpworkdir.join('path', 'index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'path': {'index.html': 'foo.txt', 'foo.txt': 'hello'}}


def test_jinja_static_abs_url(tmpworkdir):
    tmpworkdir.mkdir('path')
    tmpworkdir.join('foo.txt').write('hello')
    tmpworkdir.join('path', 'index.html').write("{{ '/foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'path': {'index.html': '/foo.txt'}, 'foo.txt': 'hello'}


def test_jinja_static_missing(tmpworkdir):
    tmpworkdir.join('index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    with pytest.raises(HarrierProblem):
        build(config)
    assert gettree(tmpworkdir) == {'index.html': "{{ 'foo.txt'|S }}", 'build': {}}


@pytest.mark.parametrize('library', [
    'libs/package/path/lib_file.js',
    'lib/package/path/lib_file.js',
    'package/path/lib_file.js',
    'lib_file.js',
    'lib/package/path/',
    'lib/package/',
    'package/',
])
def test_jinja_static_library(tmpworkdir, library):
    # here the library directory is inside the config root, shouldn't make any difference
    mktree(tmpworkdir, {
        'bower_components/package/path/lib_file.js': 'lib content',
        'index.html': "{{ 'lib_file.js'|S('%s') }}" % library
    })

    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'index.html': 'lib_file.js', 'lib_file.js': 'lib content'}


def test_jinja_static_library_missing(tmpworkdir):
    tmpworkdir.join('index.html').write("{{ 'lib_file.js'|S('libs/lib_file.js') }}")

    config = load_config(None)
    config.setup('build')
    with pytest.raises(HarrierProblem):
        build(config)
    assert gettree(tmpworkdir) == {'index.html': "{{ 'lib_file.js'|S('libs/lib_file.js') }}", 'build': {}}


def test_extends_build(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.html': 'start\n{% block hello %}{% endblock %}',
            'bar.html': """
{% extends 'foo.html' %}
{% block hello %}
body
{% endblock %}""",
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'foo.html': 'start\n',
        'bar.html': '\nstart\n\nbody\n',
    }


def test_extends_exclude_build(tmpworkdir):
    mktree(tmpworkdir, {
        'bower_components/package/path/lib_file.js': 'lib content',
        'src': {
            '_foo.html': """\
{{ 'lib_file.js'|S('lib_file.js') }}
start
{% block hello %}{% endblock %}""",
            'bar.html': """\
{% extends '_foo.html' %}
{% block hello %}
body
{% endblock %}""",
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'bar.html': 'lib_file.js\nstart\n\nbody\n',
        'lib_file.js': 'lib content'
    }


def test_simple_frontmatter(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.html': """\
---
test_var: "carrot cake"
---
I would like some {{ test_var }}.""",
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'foo.html': 'I would like some carrot cake.',
    }
