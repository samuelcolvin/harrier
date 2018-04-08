from click.testing import CliRunner
from pytest_toolbox import gettree, mktree

from harrier.cli import cli
from harrier.common import HarrierProblem


def test_blank():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert 'harrier' in result.output
    assert 'build the site' in result.output


def test_build(tmpdir):
    mktree(tmpdir, {
        'pages': {
            'foobar.md': '# hello',
        },
        'theme': {
            'templates': {
                'main.jinja': 'main:\n {{ content }}'
            }
        },
        'harrier.yml': (
            'webpack: {run: false}\n'
        )
    })

    assert not tmpdir.join('dist').check()
    result = CliRunner().invoke(cli, ['build', str(tmpdir)])
    assert result.exit_code == 0
    assert 'Built site object model with 1 files, 1 files to render' in result.output

    assert tmpdir.join('dist').check()
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': 'main:\n <h1>hello</h1>\n',
        },
    }


def test_build_bad(tmpdir):
    mktree(tmpdir, {
        'harrier.yml': (
            f'whatever: whenver:\n'
        )
    })
    assert not tmpdir.join('dist').check()
    result = CliRunner().invoke(cli, ['build', str(tmpdir)])
    assert result.exit_code == 2
    assert 'error loading' in result.output
    assert not tmpdir.join('dist').check()


def test_dev(mocker):
    mock_dev = mocker.patch('harrier.cli.main.dev')

    result = CliRunner().invoke(cli, ['dev'])
    assert result.exit_code == 0
    assert mock_dev.called


def test_dev_bad(mocker):
    mocker.patch('harrier.cli.main.dev', side_effect=HarrierProblem())

    result = CliRunner().invoke(cli, ['dev'])
    assert result.exit_code == 2
