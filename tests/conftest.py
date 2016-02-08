import os
import pytest


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
