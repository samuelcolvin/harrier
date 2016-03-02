from time import sleep

import pytest

from harrier.build import Builder
from harrier.config import load_config

from ..conftest import gettree, mktree, mtime


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


def test_change_sensitive_jinja_other_change(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.txt': 'c_foo',
            'bar.html': 'c_bar',
            'spam.html': '{{ 42 + 5 }}',
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 2, 'files_built': 3}
    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo', 'bar.html': 'c_bar', 'spam.html': '47'}

    tmpworkdir.join('src').join('foo.txt').write('c_foo2')

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 1}
    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo2', 'bar.html': 'c_bar', 'spam.html': '47'}


def test_change_sensitive_jinja_change(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.txt': 'c_foo',
            'bar.html': 'c_bar',
            'spam.html': '{{ 42 + 5 }}',
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 2, 'files_built': 3}
    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo', 'bar.html': 'c_bar', 'spam.html': '47'}
    foo_t = mtime(tmpworkdir, 'build/foo.txt')
    bar_t = mtime(tmpworkdir, 'build/bar.html')
    spam_t = mtime(tmpworkdir, 'build/spam.html')

    tmpworkdir.join('src').join('bar.html').write('c_bar2')

    sleep(0.002)  # required for mtime change
    tool_chain = builder.build(partial=True)
    assert tool_chain.status == {'tools': 4, 'tools_run': 1, 'files_built': 1}

    # only one files has been built (bar.html), but we check thant spam.html was also created
    assert set(tool_chain.get_tool('Jinja').to_build) == {'./bar.html', './spam.html'}

    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo', 'bar.html': 'c_bar2', 'spam.html': '47'}
    assert foo_t == mtime(tmpworkdir, 'build/foo.txt')
    assert bar_t != mtime(tmpworkdir, 'build/bar.html')
    assert spam_t == mtime(tmpworkdir, 'build/spam.html')


def test_add_file(simple_setup):
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    simple_setup.join('src').join('waffle.txt').write('c_waffle')

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 1}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo', 'waffle.txt': 'c_waffle'}


def test_delete_file(simple_setup):
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 1, 'files_built': 2}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar', 'foo.txt': 'c_foo'}

    simple_setup.join('src').join('foo.txt').remove()

    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 0, 'files_built': 0}
    assert gettree(simple_setup.join('build')) == {'bar.txt': 'c_bar'}


def test_delete_jinja(tmpworkdir):
    mktree(tmpworkdir, {
        'src': {
            'foo.txt': 'c_foo',
            'bar.html': 'c_bar',
            'spam.html': '{{ 42 + 5 }}',
        },
        'harrier.yml': '\nroot: src'
    })
    config = load_config()
    config.setup('build')
    builder = Builder(config)
    assert builder.build(partial=True).status == {'tools': 4, 'tools_run': 2, 'files_built': 3}
    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo', 'bar.html': 'c_bar', 'spam.html': '47'}

    tmpworkdir.join('src').join('bar.html').remove()

    tool_chain = builder.build(partial=True)
    assert tool_chain.status == {'tools': 4, 'tools_run': 0, 'files_built': 0}

    assert gettree(tmpworkdir.join('build')) == {'foo.txt': 'c_foo', 'spam.html': '47'}
