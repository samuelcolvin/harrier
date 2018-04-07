import asyncio
import json
import sys

import pytest
from pytest_toolbox import gettree, mktree

from harrier.assets import copy_assets, run_grablib, run_webpack, start_webpack_watch
from harrier.common import HarrierProblem
from harrier.config import get_config

MOCK_WEBPACK = f"""\
#!{sys.executable}
import json
import sys
from pathlib import Path

save_to = Path(__file__).parent.resolve() / 'webpack_args.json'
save_to.write_text(json.dumps(sys.argv))
if 'error' in ' '.join(sys.argv):
    sys.exit(2)
"""


def test_run_webpack(tmpdir):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages': {'foobar.md': '# hello'},
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js': {
                'index.js': '*'
            }
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'dist_dir: {tmpdir.join("dist")}\n'
            f'webpack:\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    run_webpack(config)
    args = json.loads(tmpdir.join('webpack_args.json').read_text('utf8'))
    assert [
        f'{tmpdir}/mock_webpack',
        '--context', f'{tmpdir}',
        '--entry', './theme/js/index.js',
        '--output-path', f'{tmpdir}/dist/theme',
        '--output-filename', 'main.js',
        '--devtool', 'source-map',
        '--mode', 'production',
        '--optimize-minimize',
    ] == args


def test_run_webpack_error(tmpdir):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages': {'foobar.md': '# hello'},
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js': {
                'error.js': '*'
            },
        },
        'webpack_config.js': '*',
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'dist_dir: {tmpdir.join("dist")}\n'
            f'webpack:\n'
            f'  cli: {webpack_path}\n'
            f'  entry: js/error.js\n'
            f'  config: webpack_config.js\n'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    with pytest.raises(HarrierProblem):
        run_webpack(config, mode='development')
    args = json.loads(tmpdir.join('webpack_args.json').read_text('utf8'))
    assert [
        f'{tmpdir}/mock_webpack',
        '--context', f'{tmpdir}',
        '--entry', './theme/js/error.js',
        '--output-path', f'{tmpdir}/dist/theme',
        '--output-filename', 'main.js',
        '--devtool', 'source-map',
        '--mode', 'development',
        '--config', './webpack_config.js'
    ] == args


async def test_start_webpack_watch(tmpdir, loop):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages': {'foobar.md': '# hello'},
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js': {
                'index.js': '*'
            }
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'dist_dir: {tmpdir.join("dist")}\n'
            f'webpack:\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))

    asyncio.set_event_loop(loop)
    p = await start_webpack_watch(config)
    await p.wait()

    assert [
        f'{tmpdir}/mock_webpack',
        '--context', f'{tmpdir}',
        '--entry', './theme/js/index.js',
        '--output-path', f'{tmpdir}/dist/theme',
        '--output-filename', 'main.js',
        '--devtool', 'source-map',
        '--mode', 'development',
        '--watch',
    ] == json.loads(tmpdir.join('webpack_args.json').read_text('utf8'))


def test_grablib(tmpdir):
    mktree(tmpdir, {
        'pages': {'foobar.md': '# hello'},
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'sass': {
                'main.scss': (
                    '@import "DL/demo";'
                    'body {background: $foo}'
                )
            }
        },
        'harrier.yml': (
            f'dist_dir: {tmpdir.join("dist")}\n'
            f'download:\n'
            f"  'https://cdn.rawgit.com/samuelcolvin/ae6d04dadbb4d552d365f440d3ac8015/raw/"
            f"cda04f66c71e4a5f418e78d111d651ae3a2e3784/demo.scss': '_demo.scss'"
        )
    })

    config = get_config(str(tmpdir))
    run_grablib(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'main.css': 'body{background:#BAD}\n',
        },
    }


def test_copy_assets(tmpdir):
    mktree(tmpdir, {
        'pages': {'foobar.md': '# hello'},
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'assets': {
                'image.png': '*'
            }
        },
        'harrier.yml': (
            f'dist_dir: {tmpdir.join("dist")}\n'
        )
    })

    config = get_config(str(tmpdir))
    copy_assets(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'assets': {
                'image.png': '*'
            },
        },
    }
