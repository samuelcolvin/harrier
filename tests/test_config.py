from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest_toolbox import mktree

from harrier.config import get_config


def test_ok(tmpdir):
    mktree(tmpdir, {
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
    })

    config = get_config(tmpdir)
    assert config.pages_dir == Path(tmpdir.join('pages'))
    assert not config.webpack.run


def test_ok_file(tmpdir):
    mktree(tmpdir, {
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
        'harrier.yml': 'foo: bar'
    })

    config = get_config(tmpdir.join('harrier.yml'))
    assert config.pages_dir == Path(tmpdir.join('pages'))
    assert not config.webpack.run


def test_no_theme_dir(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foo.md': '# foo',
            'bar.html': '{{ 4|add_one }} {{ config.dynamic }}',
        },
        'theme': {},
        'harrier.yml': 'default_template: main.jinja'
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'does not exist' in str(exc_info.value)
    assert 'is not a directory' not in str(exc_info.value)


def test_no_pages(tmpdir):
    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'does not exist' in str(exc_info.value)
    assert 'is not a directory' not in str(exc_info.value)


def test_pages_not_dir(tmpdir):
    mktree(tmpdir, {
        'pages': '*',
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'does not exist' not in str(exc_info.value)
    assert 'is not a directory' in str(exc_info.value)


def test_dist_dir_no_parent(tmpdir):
    mktree(tmpdir, {
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
        'harrier.yml': f'dist_dir: {tmpdir.join("foo/bar")}'
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'parent directory does not exist' in str(exc_info.value)
    assert 'is not a directory' not in str(exc_info.value)


def test_dist_dir_not_dir(tmpdir):
    mktree(tmpdir, {
        'dist': 'foobar',
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'is not a directory' in str(exc_info.value)
    assert 'parent directory does not exist' not in str(exc_info.value)


def test_extensions_not_dir(tmpdir):
    mktree(tmpdir, {
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
        'extensions.py': {},
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert '"extensions" should be a python file, not directory' in str(exc_info.value)


def test_webpack_ok(tmpdir, caplog):
    mktree(tmpdir, {
        'pages': {},
        'theme': {
            'templates': {'main.jinja': '{{ content }}'},
            'js/index.js': '*'
        },
        'mock_webpack': '*',
        'harrier.yml': (
            'webpack:\n'
            '  cli: mock_webpack'
        )
    })

    config = get_config(tmpdir)
    assert config.webpack.run
    assert 'webpack entry point' not in caplog.text


def test_webpack_no_entry(tmpdir, caplog):
    mktree(tmpdir, {
        'pages': {},
        'theme/templates/main.jinja': '{{ content }}',
        'mock_webpack': '*',
        'harrier.yml': (
            'webpack:\n'
            '  cli: mock_webpack'
        )
    })

    config = get_config(tmpdir)
    assert not config.webpack.run
    assert 'webpack entry point' in caplog.text


def test_webpack_missing_config(tmpdir):
    mktree(tmpdir, {
        'pages': {},
        'theme': {
            'templates': {'main.jinja': '{{ content }}'},
            'js/index.js': '*'
        },
        'mock_webpack': '*',
        'harrier.yml': (
            'webpack:\n'
            '  cli: mock_webpack\n'
            '  config: missing\n'
        )
    })

    with pytest.raises(ValidationError) as exc_info:
        get_config(tmpdir)
    assert 'webpack config set but does not exist' in str(exc_info.value)
