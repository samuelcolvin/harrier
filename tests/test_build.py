import pytest

from harrier.build import build
from harrier.common import HarrierKnownProblem
from harrier.config import load_config

from .conftest import gettree, mktree


def test_simple_build(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    tmpworkdir.join('harrier.yml').write("""\
root: .
target:
  build:
    path: build""")
    config = load_config('harrier.yml')
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'test.js': 'var hello = 1;'}


def test_no_config(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'test.js': 'var hello = 1;'}


def test_extra_config(tmpworkdir):
    tmpworkdir.join('harrier.yml').write('foobar: 42')
    with pytest.raises(HarrierKnownProblem) as excinfo:
        load_config(None)
    assert excinfo.value.args[0] == "Unexpected sections in config: {'foobar'}"


def test_json_seperate_root(tmpworkdir):
    root_dir = tmpworkdir.mkdir('foobar')
    tmpworkdir.join('harrier.json').write('{"root": "foobar"}')
    root_dir.join('bar').write('hello')
    config = load_config('harrier.json')
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'bar': 'hello'}


def test_build_css_js(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    tmpworkdir.join('styles.scss').write('a { b { color: blue; } }')
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'var hello = 1;',
        'styles.css': 'a b {\n  color: blue; }\n'
    }


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
        'index.html': '47\n<script src="http://localhost:8000/livereload.js"></script>'
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
    with pytest.raises(HarrierKnownProblem):
        build(config)
    assert gettree(tmpworkdir) == {'index.html': "{{ 'foo.txt'|S }}"}


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
    mktree(tmpworkdir, **{
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
    with pytest.raises(HarrierKnownProblem):
        build(config)
    assert gettree(tmpworkdir) == {'index.html': "{{ 'lib_file.js'|S('libs/lib_file.js') }}"}


def test_prebuild(tmpworkdir):
    tmpworkdir.mkdir('lib').join('test.js').write('XX')
    tmpworkdir.join('harrier.yml').write("""\
prebuild:
  commands:
    - 'cp lib/test.js foobar.js'
  patterns:
    - ./lib/*.js
  generates:
    - foobar.js""")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foobar.js': 'XX'}
    assert tmpworkdir.join('foobar.js').check() is False


def test_prebuild_no_cleanup(tmpworkdir):
    tmpworkdir.mkdir('lib').join('test.js').write('XX')
    tmpworkdir.join('harrier.yml').write("""\
prebuild:
  commands:
    - 'cp lib/test.js foobar.js'
  cleanup: False
  patterns:
    - ./lib/*.js
  generates:
    - foobar.js""")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foobar.js': 'XX'}
    assert tmpworkdir.join('foobar.js').check()


def test_prebuild_different_dir(tmpworkdir):
    mktree(tmpworkdir, **{
        'path/different_root': {
            'foo': 'C_foo',
            'lib/test.js': 'C_test.js',
        },
        'harrier.yml': """\
root: path/different_root
prebuild:
  commands:
    - 'cp lib/test.js foobar.js'
  patterns:
    - ./lib/*
  generates:
    - foobar.js"""
    })
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foo': 'C_foo', 'foobar.js': 'C_test.js'}
    assert gettree(tmpworkdir.join('path').join('different_root')) == {
        'foo': 'C_foo',
        'lib': {
            'test.js': 'C_test.js',
        }
    }
