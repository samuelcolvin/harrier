import asyncio
from pathlib import Path

from pytest_toolbox import gettree, mktree
from watchgod import Change

import harrier.dev
from harrier.config import Config
from harrier.dev import HarrierWatcher
from harrier.main import dev


class MockServer:
    def __init__(self, *args, **kwargs):
        pass

    async def start(self):
        pass

    async def shutdown(self):
        pass


def test_dev_simple(tmpdir, mocker, loop):
    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('pages/foobar.md')))}
        yield {(Change.modified, str(tmpdir.join('pages/features/whatever.md')))}
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}
        yield {(Change.added, str(tmpdir.join('theme/sass/main.scss')))}
        tmpdir.join('harrier.yml').write('foo: 2')
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}

    asyncio.set_event_loop(loop)
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello\n {{ site.foo }}',
            'features/whatever.md': '## Foo',
        },
        'harrier.yml': 'foo: 1'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)

    assert not tmpdir.join('dist').check()

    dev(str(tmpdir), 8000)

    # debug(gettree(tmpdir.join('dist')))
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': '<h1>hello</h1>\n\n<p>2</p>\n',
        },
        'features': {
            'whatever': {
                'index.html': '<h2>Foo</h2>\n',
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
            'features/whatever.md': '## Foo',
        },
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)
    mocker.patch('harrier.dev.Server', return_value=MockServer())

    assert not tmpdir.join('dist').check()

    assert dev(str(tmpdir), 8000) == 0

    # debug(gettree(tmpdir.join('dist')))
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': '<h1>hello</h1>\n',
        },
        'features': {
            'whatever': {},
        },
    }


def test_extensions_error(tmpdir, mocker, loop):
    async def awatch_alt(*args, **kwargs):
        tmpdir.join('extensions.py').write('print(xxx)')
        yield {(Change.modified, str(tmpdir.join('extensions.py')))}

    asyncio.set_event_loop(loop)
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
        },
        'theme/templates/main.jinja': 'main:\n {{ content }}',
        'harrier.yml': 'default_template: main.jinja',
        'extensions.py': 'x = 1'
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)
    mocker.patch('harrier.dev.Server', return_value=MockServer())

    assert not tmpdir.join('dist').check()

    assert dev(str(tmpdir), 8000) == 1

    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': 'main:\n <h1>hello</h1>\n',
        },
    }


def test_mock_executor(tmpdir, mocker):
    foobar_path = str(tmpdir.join('pages/foobar.md'))

    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}
        yield {(Change.modified, foobar_path)}
        yield {(Change.modified, str(tmpdir.join('theme/assets/main.png')))}
        yield {(Change.modified, str(tmpdir.join('theme/sass/main.scss')))}
        yield {(Change.modified, str(tmpdir.join('theme/templates/main.jinja')))}
        yield {(Change.modified, str(tmpdir.join('extensions.py')))}

    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates/main.jinja': 'main:\n {{ content }}',
        'harrier.yml': 'foo: bar',
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

    assert [c[0][2].dict(exclude={'config_path'}) for c in mock_run_in_executor.call_args_list] == [
        {
            'pages': '__FB__',
            'assets': False,
            'sass': False,
            'templates': False,
            'extensions': False,
            'update_config': False,
        },
        {
            'pages': set(),
            'assets': False,
            'sass': False,
            'templates': False,
            'extensions': False,
            'update_config': True,
        },
        {
            'pages': {(Change.modified, Path(foobar_path))},
            'assets': False,
            'sass': False,
            'templates': False,
            'extensions': False,
            'update_config': False,
        },
        {
            'pages': set(),
            'assets': True,
            'sass': False,
            'templates': False,
            'extensions': False,
            'update_config': False,
        },
        {
            'pages': set(),
            'assets': False,
            'sass': True,
            'templates': False,
            'extensions': False,
            'update_config': False,
        },
        {
            'pages': set(),
            'assets': False,
            'sass': False,
            'templates': True,
            'extensions': False,
            'update_config': False,
        },
        {
            'pages': set(),
            'assets': False,
            'sass': False,
            'templates': False,
            'extensions': True,
            'update_config': False,
        },
    ]


def test_webpack_terminate(tmpdir, mocker, caplog):
    async def awatch_alt(*args, **kwargs):
        yield {(Change.modified, str(tmpdir.join('harrier.yml')))}

    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates/main.jinja': 'main:\n {{ content }}',
    })
    mocker.patch('harrier.dev.awatch', side_effect=awatch_alt)
    mocker.patch('harrier.dev.Server', return_value=MockServer())

    f = asyncio.Future()
    mock_webpack = mocker.MagicMock()
    mock_webpack.returncode = None
    f.set_result(mock_webpack)
    mocker.patch('harrier.dev.start_webpack_watch', return_value=f)

    assert not tmpdir.join('dist').check()

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


class Entry:
    def __init__(self, path):
        self.path = str(path)
        self.name = self.path.rsplit('/', 1)[1]


def test_harrier_watcher(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates/main.jinja': 'main:\n {{ content }}',
    })
    harrier.dev.CONFIG = Config(source_dir=tmpdir)
    watcher = HarrierWatcher(Path(tmpdir))
    assert not watcher.should_watch_dir(Entry(tmpdir.join('foobar')))
    assert not watcher.should_watch_dir(Entry(tmpdir.join('__pycache__')))
    assert watcher.should_watch_dir(Entry(tmpdir.join('pages')))
    assert watcher.should_watch_dir(Entry(tmpdir.join('pages/whatever')))
    harrier.dev.CONFIG = None
