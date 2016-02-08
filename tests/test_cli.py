from click.testing import CliRunner

from harrier.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'harrier - Jinja2 & sass/scss aware site builder builder' in result.output


def test_simple_build(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    p = tmpworkdir.join('harrier.yml')
    p.write("""\
root: .
target:
  build:
    path: build""")
    runner = CliRunner()
    result = runner.invoke(cli, ['build'])
    assert result.exit_code == 0
    assert result.output == 'Found default config file harrier.yml\nBuilding 1 files with 1 tool\n'
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_build_no_config(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    runner = CliRunner()
    result = runner.invoke(cli, ['build'])
    assert result.exit_code == 0
    assert result.output == ('no config file supplied and none found with expected names: '
                             'harrier.yml, harrier.json, config.yml, config.json. Using default settings.\n'
                             'Building 1 files with 1 tool\n')
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'
