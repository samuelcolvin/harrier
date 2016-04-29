import pytest

from harrier.build import build
from harrier.common import HarrierProblem
from harrier.config import Config

from ..conftest import gettree, mktree


def test_no_config(tmpworkdir):
    mktree(tmpworkdir, {'foo': 'bar'})
    config = Config()
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foo': 'bar'}


def test_simple_build(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    tmpworkdir.join('harrier.yml').write("""\
root: .
target:
  build:
    path: build""")
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'test.js': 'var hello = 1;'}


def test_extra_config(tmpworkdir):
    tmpworkdir.join('harrier.yml').write('foobar: 42')
    with pytest.raises(HarrierProblem) as excinfo:
        Config()
    assert excinfo.value.args[0] == "Unexpected sections in config: {'foobar'}"


def test_json_seperate_root(tmpworkdir):
    root_dir = tmpworkdir.mkdir('foobar')
    tmpworkdir.join('harrier.json').write('{"root": "foobar"}')
    root_dir.join('bar').write('hello')
    config = Config('harrier.json')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'bar': 'hello'}


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
    config = Config()
    config.setup()
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
    config = Config()
    config.setup()
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
    config = Config()
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'foo': 'C_foo', 'foobar.js': 'C_test.js'}
    assert gettree(tmpworkdir.join('path').join('different_root')) == {
        'foo': 'C_foo',
        'lib': {
            'test.js': 'C_test.js',
        }
    }


def test_subdirectory(tmpworkdir):
    tmpworkdir.join('test.js').write('X')
    tmpworkdir.join('harrier.yml').write("""\
subdirectory: apples""")
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {'apples': {'test.js': 'X'}}


def test_subdirectory_bad(tmpworkdir):
    tmpworkdir.join('test.js').write('X')
    tmpworkdir.join('harrier.yml').write("""\
subdirectory: /apples""")
    config = Config('harrier.yml')
    with pytest.raises(HarrierProblem):
        config.setup()
