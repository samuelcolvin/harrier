import asyncio
import json
import logging
import sys

import pytest
from pydantic import ValidationError
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import RegexStr

from harrier.assets import assets_grablib, copy_assets, run_grablib, run_webpack, start_webpack_watch
from harrier.common import HarrierProblem
from harrier.config import Mode, get_config

MOCK_WEBPACK = f"""\
#!{sys.executable}
import json, os, sys
from pathlib import Path

this_dir = Path(__file__).parent.resolve()
(this_dir / 'webpack_args.json').write_text(json.dumps(sys.argv))
(this_dir / 'webpack_env.json').write_text(json.dumps(dict(os.environ)))
args = ' '.join(sys.argv)
print('foobar')
if 'js/error.js' in args:
    sys.exit(2)
elif 'js/nojson.js' not in args:
    print(json.dumps(dict(assets=[1, 2, 3])))
"""


def test_run_webpack(tmpdir):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/index.js': '*',
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'webpack:\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    count = run_webpack(config)
    assert count == 3
    args = json.loads(tmpdir.join('webpack_args.json').read_text('utf8'))
    assert [
        f'{tmpdir}/mock_webpack',
        '--context', f'{tmpdir}',
        '--entry', './theme/js/index.js',
        '--output-path', f'{tmpdir}/dist/theme',
        '--output-filename', 'main.[hash].js',
        '--devtool', 'source-map',
        '--mode', 'production',
        '--optimize-minimize',
        '--json',
    ] == args
    webpack_env = json.loads(tmpdir.join('webpack_env.json').read_text('utf8'))
    assert webpack_env['NODE_ENV'] == 'production'


def test_run_webpack_error(tmpdir):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/error.js': '*',
        },
        'webpack_config.js': '*',
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'mode: development\n'
            f'webpack:\n'
            f'  cli: {webpack_path}\n'
            f'  entry: js/error.js\n'
            f'  config: webpack_config.js\n'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    with pytest.raises(HarrierProblem):
        run_webpack(config)
    args = json.loads(tmpdir.join('webpack_args.json').read_text('utf8'))
    assert [
        f'{tmpdir}/mock_webpack',
        '--context', f'{tmpdir}',
        '--entry', './theme/js/error.js',
        '--output-path', f'{tmpdir}/dist/theme',
        '--output-filename', 'main.js',
        '--devtool', 'source-map',
        '--mode', 'development',
        '--config', './webpack_config.js',
        '--json',
    ] == args
    webpack_env = json.loads(tmpdir.join('webpack_env.json').read_text('utf8'))
    assert webpack_env['NODE_ENV'] == 'development'


def test_run_webpack_json_error(tmpdir):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/nojson.js': '*',
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'webpack:\n'
            f'  entry: js/nojson.js\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    count = run_webpack(config)
    assert count == 1


def test_run_webpack_no_capture(tmpdir, caplog):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/index.js': '*',
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'webpack:\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    caplog.set_level(logging.DEBUG)
    config = get_config(str(tmpdir))
    count = run_webpack(config)
    # 1 because capture_output is false so no json is loaded
    assert count == 1


async def test_start_webpack_watch(tmpdir, loop):
    webpack_path = tmpdir.join('mock_webpack')
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/index.js': '*',
        },
        'mock_webpack': MOCK_WEBPACK,
        'harrier.yml': (
            f'webpack:\n'
            f'  cli: {webpack_path}'
        )
    })
    webpack_path.chmod(0o777)

    config = get_config(str(tmpdir))
    config.mode = Mode.development

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
    webpack_env = json.loads(tmpdir.join('webpack_env.json').read_text('utf8'))
    assert webpack_env['NODE_ENV'] == 'development'


def test_run_webpack_cli_wrong(tmpdir, caplog):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/index.js': '*',
        },
        'harrier.yml': (
            f'webpack:\n'
            f'  cli: /foo/bar'
        )
    })

    with pytest.raises(ValidationError):
        get_config(str(tmpdir))


def test_run_webpack_default(tmpdir, caplog):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'js/index.js': '*',
        },
        'node_modules/.bin/webpack-cli': MOCK_WEBPACK,
    })
    tmpdir.join('node_modules/.bin/webpack-cli').chmod(0o777)

    caplog.set_level(logging.DEBUG)
    config = get_config(str(tmpdir))
    assert config.webpack.run is True


def test_grablib(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'sass/main.scss': (
                '@import "DL/demo";'
                'body {background: $foo}'
            ),
        },
        'harrier.yml': (
            f'download:\n'
            f"  'https://cdn.rawgit.com/samuelcolvin/ae6d04dadbb4d552d365f440d3ac8015/raw/"
            f"cda04f66c71e4a5f418e78d111d651ae3a2e3784/demo.scss': '_demo.scss'"
        )
    })

    config = get_config(str(tmpdir))
    run_grablib(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'main.7cc3e19.css': 'body{background:#BAD}\n',
        },
    }


def test_grablib_pygments(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'sass': {
                '_other.scss': 'div {colour: red}',
                'main.scss': (
                    '@import "other";\n'
                    '@import "pygments/default";\n'
                ),
            },
        }
    })

    config = get_config(str(tmpdir))
    run_grablib(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'main.9a9caa6.css': RegexStr('div{colour:red}\.hi \.hll.*'),
        },
    }


def test_sass_url(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'assets/image.png': '*',
            'sass/main.scss': (
                '$background-url: resolve_url("theme/assets/image.png");\n'
                'body {background: url($background-url)}'
            ),
        },
    })

    config = get_config(str(tmpdir))
    assets_grablib(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'assets': {
                'image.3389dae.png': '*',
            },
            'main.a773ef9.css': 'body{background:url("theme/assets/image.3389dae.png")}\n',
        },
    }


def test_grablib_error(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'sass/main.scss': 'foobar',
        },
        'harrier.yml': (
            f'download:\n'
            f"  'https://cdn.rawgit.com/samuelcolvin/ae6d04dadbb4d552d365f440d3ac8015/raw/"
            f"cda04f66c71e4a5f418e78d111d651ae3a2e3784/demo.scss': '_demo.scss'"
        )
    })

    config = get_config(str(tmpdir))
    with pytest.raises(HarrierProblem):
        run_grablib(config)
    assert not tmpdir.join('dist').check()


def test_copy_assets_dev(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'assets/image.png': '*',
        },
    })

    config = get_config(str(tmpdir))
    config.mode = Mode.development
    copy_assets(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'assets': {
                'image.png': '*'
            },
        },
    }


def test_copy_assets_prod(tmpdir):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates': {'main.jinja': 'main:\n {{ content }}'},
            'assets/image.png': '*',
        },
    })

    config = get_config(str(tmpdir))
    config.mode = Mode.production
    copy_assets(config)
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'assets': {
                'image.3389dae.png': '*'
            },
        },
    }
