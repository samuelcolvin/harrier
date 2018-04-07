import asyncio
import logging
from pathlib import Path

from pytest_toolbox import gettree, mktree
from watchgod import Change

from harrier.dev import update_site
from harrier.main import dev


def test_dev_simple(tmpdir, mocker, loop):
    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('pages/foobar.md')))}
        yield {(Change.modified, str(tmpdir.join('pages/features/whatever.md')))}
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}
        yield {(Change.added, str(tmpdir.join('theme/sass/main.scss')))}

    asyncio.set_event_loop(loop)
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
            'features': {
                'whatever.md': '## Foo'
            }
        },
        'theme': {
            'templates': {
                'main.jinja': 'main:\n {{ content }}'
            }
        },
        'harrier.yml': f'dist_dir: {tmpdir.join("dist")}'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)

    assert not tmpdir.join('dist').check()

    dev(str(tmpdir), 8000)

    # debug(gettree(tmpdir.join('dist')))
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': 'main:\n <h1>hello</h1>\n',
        },
        'features': {
            'whatever': {
                'index.html': 'main:\n <h2>Foo</h2>\n',
            },
        },
    }


def test_dev_delete(tmpdir, mocker, loop):
    async def awatch_alt(*args, **kwargs):
        yield {(Change.deleted, str(tmpdir.join('pages/features/whatever.md')))}

    asyncio.set_event_loop(loop)
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
            'features': {
                'whatever.md': '## Foo'
            }
        },
        'theme': {
            'templates': {
                'main.jinja': 'main:\n {{ content }}'
            }
        },
        'harrier.yml': f'dist_dir: {tmpdir.join("dist")}'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)

    assert not tmpdir.join('dist').check()

    dev(str(tmpdir), 8000)

    # debug(gettree(tmpdir.join('dist')))
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': 'main:\n <h1>hello</h1>\n',
        },
        'features': {
            'whatever': {},
        },
    }


class MockServer:
    def __init__(self, *args, **kwargs):
        pass

    async def start(self):
        pass

    async def shutdown(self):
        pass


def test_mock_executor(tmpdir, mocker):
    foobar_path = str(tmpdir.join('pages/foobar.md'))

    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}
        yield {(Change.modified, foobar_path)}
        yield {(Change.modified, str(tmpdir.join('theme/assets/main.png')))}
        yield {(Change.modified, str(tmpdir.join('theme/sass/main.scss')))}
        yield {(Change.modified, str(tmpdir.join('theme/templates/main.jinja')))}

    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
        },
        'theme': {
            'templates': {
                'main.jinja': 'main:\n {{ content }}'
            }
        },
        'harrier.yml': f'dist_dir: {tmpdir.join("dist")}'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)
    mocker.patch('harrier.dev.Server', return_value=MockServer())

    loop = asyncio.new_event_loop()
    f = asyncio.Future(loop=loop)
    f.set_result(None)
    mock_run_in_executor = mocker.patch.object(loop, 'run_in_executor', return_value=f)
    asyncio.set_event_loop(loop)

    assert not tmpdir.join('dist').check()

    dev(str(tmpdir), 8000)

    assert gettree(tmpdir.join('dist')) == {}

    assert mock_run_in_executor.call_args_list == [
        mocker.call(mocker.ANY, update_site, '__FB__', True, True, True),
        mocker.call(mocker.ANY, update_site, {(Change.modified, Path(foobar_path))}, False, False, False),
        mocker.call(mocker.ANY, update_site, set(), True, False, False),
        mocker.call(mocker.ANY, update_site, set(), False, True, False),
        mocker.call(mocker.ANY, update_site, set(), False, False, True),
    ]


def test_webpack_terminate(tmpdir, mocker, caplog):
    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}

    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
        },
        'theme': {
            'templates': {
                'main.jinja': 'main:\n {{ content }}'
            }
        },
        'harrier.yml': f'dist_dir: {tmpdir.join("dist")}'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)
    mocker.patch('harrier.dev.Server', return_value=MockServer())

    f = asyncio.Future()
    mock_webpack = mocker.MagicMock()
    mock_webpack.returncode = None
    f.set_result(mock_webpack)
    mocker.patch('harrier.dev.start_webpack_watch', return_value=f)

    assert not tmpdir.join('dist').check()

    with caplog.at_level(logging.DEBUG, logger='harrier.dev'):
        dev(str(tmpdir), 8000)
        assert tmpdir.join('dist').check()
        assert mock_webpack.send_signal.call_count == 1
        assert 'webpack existed badly' not in caplog.text

        mock_webpack.returncode = 0

        dev(str(tmpdir), 8000)
        assert mock_webpack.send_signal.call_count == 1
        assert 'webpack existed badly' not in caplog.text

        mock_webpack.returncode = 1

        dev(str(tmpdir), 8000)
        assert mock_webpack.send_signal.call_count == 1
        assert 'webpack existed badly' in caplog.text
