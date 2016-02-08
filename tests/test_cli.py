from click.testing import CliRunner

from harrier.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'harrier - Jinja2 & sass/scss aware site builder builder' in result.output
