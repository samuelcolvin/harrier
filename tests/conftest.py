import os
import pytest
from harrier.config import load_config


@pytest.yield_fixture
def tmpworkdir(tmpdir):
    """
    Create a temporary working working directory.
    """
    root_dir = tmpdir.mkdir('test_root')
    cwd = os.getcwd()
    os.chdir(root_dir.strpath)

    yield root_dir

    os.chdir(cwd)


@pytest.fixture
def simpleharrier(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    p = tmpworkdir.join('harrier.yml')
    p.write("""\
root: .
target:
  build:
    path: build""")
    _config = load_config('harrier.yml')
    _config.setup('build')

    class Tmp:
        tmpdir = tmpworkdir
        config = _config
    return Tmp
