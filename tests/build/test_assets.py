from unittest.mock import patch
from subprocess import CompletedProcess

from harrier.build import build
from harrier.config import Config

from ..conftest import gettree, mktree


def test_simple_assets(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'deep/static/path': {
            'styles.css': 'body {color: green}',
        },
        'harrier.yml': """\
root: .
assets:
  active: True"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'var hello = 1;',
        'deep': {'static': {'path': {'styles.css': 'body {color: green}'}}},
        'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "deep/static/path/styles.css": "/deep/static/path/styles.css",
    "test.js": "/test.js"
  }
}
""",
    }


def test_url_root(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
assets:
  url_root: http://www.example.com
  active: True"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'var hello = 1;',
        'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "test.js": "http://www.example.com/test.js"
  }
}
""",
    }


def test_yaml(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
assets:
  file: assets.yaml
  active: True"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'var hello = 1;',
        'assets.yaml': """\
commit: unknown
files:
  test.js: /test.js
""",
    }


def test_git_commit(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'X',
        'harrier.yml': """\
root: .
assets:
  active: True"""
    })

    with patch('harrier.tools.subprocess.run') as mock_run:
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout='commit sha1\n')
        config = Config('harrier.yml')
        config.setup()
        build(config)

    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'X',
        'assets.json': """\
{
  "commit": "commit sha1",
  "files": {
    "test.js": "/test.js"
  }
}
""",
    }
    assert mock_run.called


def test_no_git(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
assets:
  active: True"""
    })
    with patch('harrier.tools.subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError('testing')
        config = Config('harrier.yml')
        config.setup()
        build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'test.js': 'var hello = 1;',
        'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "test.js": "/test.js"
  }
}
""",
    }


def test_assets_blank_subdirectory(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
subdirectory: my_static
assets:
  active: True"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'my_static': {
            'test.js': 'var hello = 1;',
            'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "test.js": "/my_static/test.js"
  }
}
"""}}


def test_url_root_domain_subdirectory(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
subdirectory: my_static
assets:
  active: True
  url_root: http://www.foobar.com"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'my_static': {
            'test.js': 'var hello = 1;',
            'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "test.js": "http://www.foobar.com/my_static/test.js"
  }
}
"""}}


def test_url_root_full_path_subdirectory(tmpworkdir):
    mktree(tmpworkdir, {
        'test.js': 'var hello = 1;',
        'harrier.yml': """\
root: .
subdirectory: my_static
assets:
  active: True
  url_root: https://www.foobar.com/whatever"""
    })
    config = Config('harrier.yml')
    config.setup()
    build(config)
    assert gettree(tmpworkdir.join('build')) == {
        'my_static': {
            'test.js': 'var hello = 1;',
            'assets.json': """\
{
  "commit": "unknown",
  "files": {
    "test.js": "https://www.foobar.com/whatever/test.js"
  }
}
"""}}
