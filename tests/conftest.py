import os
import logging
from copy import deepcopy

import pytest
from py._path.local import LocalPath

from harrier.config import Config
from harrier.common import logger


@pytest.yield_fixture
def tmpworkdir(tmpdir):
    """
    Create a temporary working working directory.
    """
    cwd = os.getcwd()
    os.chdir(tmpdir.strpath)

    yield tmpdir

    os.chdir(cwd)


@pytest.fixture
def simpleharrier(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    _config = Config()
    _config.setup()

    class Tmp:
        tmpdir = tmpworkdir
        config = _config
    return Tmp


@pytest.yield_fixture
def debug_logger():
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    yield

    logger.removeHandler(handler)


def gettree(lp:  LocalPath):
    assert lp.check()
    if lp.isdir():
        return {df.basename: gettree(df) for df in lp.listdir()}
    elif lp.isfile():
        return lp.read_text('utf8')
    else:
        raise Exception('not directory or file: {}'.format(lp))


def mktree(lp: LocalPath, d):
    for name, content in d.items():
        _lp = deepcopy(lp)

        parts = list(filter(bool, name.split('/')))
        for part in parts[:-1]:
            _lp = _lp.mkdir(part)
        _lp = _lp.join(parts[-1])

        if isinstance(content, dict):
            _lp.mkdir()
            mktree(_lp, content)
        else:
            _lp.write(content)


def mtime(lp: LocalPath, path):
    _lp = deepcopy(lp)
    for part in path.split('/'):
        _lp = _lp.join(part)
    return _lp.mtime()
