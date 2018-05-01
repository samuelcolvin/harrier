from click.testing import CliRunner
from pytest_toolbox import gettree, mktree
from pytest_toolbox.comparison import RegexStr

from harrier.cli import cli
from harrier.common import HarrierProblem


def test_blank():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert 'harrier' in result.output
    assert 'build the site' in result.output


def test_build(tmpdir, mocker):
    mktree(tmpdir, {
        'pages/foobar.md': 'hello',
        'theme/templates/main.jinja': 'main:\n {{ content }}',
        'harrier.yml': (
            'webpack: {run: false}\n'
            'default_template: main.jinja\n'
        )
    })
    mock_mod = mocker.patch('harrier.main.apply_modifiers', side_effect=lambda obj, mod: obj)

    assert not tmpdir.join('dist').check()
    result = CliRunner().invoke(cli, ['build', str(tmpdir)])
    assert result.exit_code == 0
    assert '1          pages built ' in result.output
    assert 'Config:' not in result.output

    assert tmpdir.join('dist').check()
    assert gettree(tmpdir.join('dist')) == {
        'foobar': {
            'index.html': 'main:\n <p>hello</p>\n',
        },
    }
    assert mock_mod.call_count == 2


def test_build_bad(tmpdir):
    mktree(tmpdir, {
        'harrier.yml': 'whatever: whatever:\n'
    })
    assert not tmpdir.join('dist').check()
    result = CliRunner().invoke(cli, ['build', str(tmpdir)])
    assert result.exit_code == 2
    assert 'error loading' in result.output
    assert 'for more details' in result.output
    assert not tmpdir.join('dist').check()


def test_build_bad_verbose(tmpdir):
    mktree(tmpdir, {
        'harrier.yml': 'whatever: whatever:\n'
    })
    result = CliRunner().invoke(cli, ['build', str(tmpdir), '-v'])
    assert result.exit_code == 2
    assert 'error loading' in result.output
    assert 'for more details' not in result.output


def test_dev(mocker):
    mock_dev = mocker.patch('harrier.cli.main.dev')

    result = CliRunner().invoke(cli, ['dev'])
    assert result.exit_code == 0
    assert mock_dev.called


def test_dev_bad(mocker):
    mocker.patch('harrier.cli.main.dev', side_effect=HarrierProblem())

    result = CliRunner().invoke(cli, ['dev'])
    assert result.exit_code == 2
    assert 'for more details' in result.output


def test_dev_bad_verbose(mocker):
    mocker.patch('harrier.cli.main.dev', side_effect=HarrierProblem())

    result = CliRunner().invoke(cli, ['dev', '--verbose'])
    assert result.exit_code == 2
    assert 'for more details' not in result.output


def test_dev_bad_quiet(mocker):
    mocker.patch('harrier.cli.main.dev', side_effect=HarrierProblem())

    result = CliRunner().invoke(cli, ['dev', '--quiet'])
    assert result.exit_code == 2
    assert 'for more details' in result.output


def test_steps_pages(tmpdir, mocker):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme/templates/main.jinja': 'main:\n {{ content }}',
    })
    mock_mod = mocker.patch('harrier.main.apply_modifiers', side_effect=lambda obj, mod: obj)

    result = CliRunner().invoke(cli, ['build', str(tmpdir), '-v', '-s', 'pages'])
    assert result.exit_code == 0
    assert 'Built site object model with 1 files, 1 files to render' in result.output
    assert 'Config:' in result.output

    assert tmpdir.join('dist').check()
    assert mock_mod.call_count == 0


def test_steps_sass_dev(tmpdir, mocker):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates/main.jinja': '{{ content }}',
            'sass/main.scss': 'body {width: 10px + 10px;}',
        },
    })
    mock_mod = mocker.patch('harrier.main.apply_modifiers', side_effect=lambda obj, mod: obj)

    result = CliRunner().invoke(cli, ['build', str(tmpdir), '-s', 'sass', '-s', 'extensions', '--dev'])
    print(result.output)
    assert result.exit_code == 0
    assert 'Built site object model with 1 files, 1 files to render' not in result.output
    assert 'Config:' not in result.output
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'main.css': (
                'body {\n'
                '  width: 20px; }\n'
                '\n'
                '/*# sourceMappingURL=main.css.map */'
            ),
            'main.css.map': RegexStr('{.*'),
            '.src': {
                'main.scss': 'body {width: 10px + 10px;}',
            },
        },
    }
    assert mock_mod.call_count == 2


def test_steps_sass_prod(tmpdir, mocker):
    mktree(tmpdir, {
        'pages/foobar.md': '# hello',
        'theme': {
            'templates/main.jinja': '{{ content }}',
            'sass/main.scss': 'body {width: 10px + 10px;}',
        },
    })

    result = CliRunner().invoke(cli, ['build', str(tmpdir), '-s', 'sass'])
    assert result.exit_code == 0
    assert 'Built site object model with 1 files, 1 files to render' not in result.output
    assert 'Config:' not in result.output
    assert gettree(tmpdir.join('dist')) == {
        'theme': {
            'main.a1ac3a7.css': 'body{width:20px}\n',
        },
    }
