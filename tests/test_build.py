import pytest
from harrier.build import build
from harrier.common import HarrierKnownProblem

from harrier.config import load_config


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
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_no_config(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    config = load_config(None)
    config.setup('build')
    build(config)
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


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
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['bar']


def test_build_css_js(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    tmpworkdir.join('styles.scss').write('a { b { color: blue; } }')
    config = load_config(None)
    config.setup('build')
    build(config)
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert sorted([p.basename for p in tmpworkdir.join('build').listdir()]) == ['styles.css', 'test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'
    assert tmpworkdir.join('build', 'styles.css').read_text('utf8') == 'a b {\n  color: blue; }\n'


def test_jinja(tmpworkdir):
    tmpworkdir.join('index.html').write('{{ 42 + 5 }}')
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'index.html').read_text('utf8') == '47'


def test_jinja_static(tmpworkdir):
    tmpworkdir.join('foo.txt').write('hello')
    tmpworkdir.join('index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'index.html').read_text('utf8') == 'foo.txt'


def test_jinja_static_relpath(tmpworkdir):
    tmpworkdir.mkdir('path')
    tmpworkdir.join('path', 'foo.txt').write('hello')
    tmpworkdir.join('path', 'index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'path', 'index.html').read_text('utf8') == 'foo.txt'


def test_jinja_static_abs_url(tmpworkdir):
    tmpworkdir.mkdir('path')
    tmpworkdir.join('foo.txt').write('hello')
    tmpworkdir.join('path', 'index.html').write("{{ '/foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'path', 'index.html').read_text('utf8') == '/foo.txt'
    assert tmpworkdir.join('build', 'foo.txt').read_text('utf8') == 'hello'


def test_jinja_static_missing(tmpworkdir):
    tmpworkdir.join('index.html').write("{{ 'foo.txt'|S }}")
    config = load_config(None)
    config.setup('build')
    with pytest.raises(HarrierKnownProblem):
        build(config)


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
    file_dir = tmpworkdir.mkdir('bower_components').mkdir('package').mkdir('path')
    file_dir.join('lib_file.js').write('hello')

    tmpworkdir.join('index.html').write("{{ 'lib_file.js'|S('%s') }}" % library)

    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'index.html').read_text('utf8') == 'lib_file.js'
    assert tmpworkdir.join('build', 'lib_file.js').check


def test_jinja_static_library_missing(tmpworkdir):
    tmpworkdir.join('index.html').write("{{ 'lib_file.js'|S('libs/lib_file.js') }}")

    config = load_config(None)
    config.setup('build')
    with pytest.raises(HarrierKnownProblem):
        build(config)


# def test_prebuild(tmpworkdir):
#     tmpworkdir.mkdir('lib').join('test.js').write('var hello = 42;')
#     tmpworkdir.join('harrier.yml').write("""\
# root: .
# prebuild:
#   commands: ['cp lib/test.js foobar.js']""")
