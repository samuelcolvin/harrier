from pathlib import Path

import pytest

from harrier.build import build
from harrier.common import HarrierProblem
from harrier.config import load_config
from harrier.tools import find_all_files

from ..conftest import gettree, mktree


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
    with pytest.raises(HarrierProblem) as excinfo:
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


def test_execute(tmpworkdir):
    tmpworkdir.mkdir('lib').join('test.js').write('XX')
    tmpworkdir.join('harrier.yml').write("""\
execute:
  commands:
    -
      command: 'cp lib/test.js foobar.js'
      generates: ['foobar.js']
  patterns:
    - ./lib/*.js""")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foobar.js': 'XX'}
    assert tmpworkdir.join('foobar.js').check() is False


def test_execute_no_cleanup(tmpworkdir):
    tmpworkdir.mkdir('lib').join('test.js').write('XX')
    tmpworkdir.join('harrier.yml').write("""\
execute:
  commands:
    -
      command: 'cp lib/test.js foobar.js'
      generates: ['foobar.js']
  cleanup: False
  patterns:
    - ./lib/*.js""")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foobar.js': 'XX'}
    assert tmpworkdir.join('foobar.js').check()


def test_execute_different_dir(tmpworkdir):
    mktree(tmpworkdir, {
        'path/different_root': {
            'foo': 'C_foo',
            'lib/test.js': 'C_test.js',
        },
        'harrier.yml': """\
root: path/different_root
execute:
  commands:
    -
      command: 'cp {ROOT}/lib/test.js {ROOT}/foobar.js'
      generates: ['foobar.js']
  patterns:
    - ./lib/*"""
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


def test_sass_exclude(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            '_foo.scss': '$primary-colour: #016997;',
            'bar.scss': """\
@import 'foo';
body {
  color: $primary-colour;
}"""
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config(None)
    config.setup('build')
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'bar.css': 'body {\n  color: #016997; }\n'}


def test_walk(tmpworkdir):
    mktree(tmpworkdir, {
        'path/different_root': {
            'foo': 'C_foo',
            'lib/test.js': 'C_test.js',
        },
        'harrier.yml': 'yaml'
    })
    print(find_all_files(Path('.')))
