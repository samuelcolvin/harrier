import pytest

from harrier.build import Builder
from harrier.config import load_config

from .conftest import gettree, mktree


@pytest.fixture
def simple_setup(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.txt': 'c_foo',
            'bar.txt': 'c_bar',
        },
        'harrier.yml': '\nroot: src'
    })
    return tmpworkdir


def test_simple_full_rebuild(simple_setup):
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert str(builder.build()) == '4 tools of which 1 run, 2 files built'
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    simple_setup.join('src').join('foo.txt').write('c_foo changed')
    assert builder.build().status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo changed'}


def test_rebuild_dot(tmpworkdir):
    mktree(tmpworkdir, {
        'foo.txt': 'c_foo',
        'bar.txt': 'c_bar',
    })
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build().status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(tmpworkdir.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    assert builder.build().status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(tmpworkdir.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}


def test_simple_no_change_partial(simple_setup):
    config = load_config()
    config.setup('build')
    builder = Builder(config)

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 0, 'files_built': 0}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}


def test_simple_change_partial(simple_setup):
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    simple_setup.join('src').join('foo.txt').write('c_foo changed')

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 1}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo changed'}
