import click
import logging

from harrier import VERSION
from .build import build
from .config import load_config
from .common import logger, HarrierKnownProblem
from .watch import watch

config_help = 'Provide a specific harrier config yml file path'
dev_address_help = 'IP address and port to serve documentation locally (default: localhost:8000)'
site_dir_help = 'The directory to output the result of the documentation build.'
reload_help = 'Enable and disable the live reloading in the development server.'
verbose_help = 'Enable verbose output'


def verbose_option(f):
    def callback(ctx, param, value):
        if value:
            logger.setLevel(logging.DEBUG)

    return click.option('-v', '--verbose', is_flag=True, expose_value=False, help=verbose_help, callback=callback)(f)


@click.group()
@click.version_option(VERSION, '-V', '--version')
@verbose_option
def cli():
    """
    harrier - Jinja2 & sass/scss aware site builder builder
    """


@cli.command(name='live')
@click.option('-a', '--dev-addr', help=dev_address_help, metavar='<IP:PORT>')
@click.option('--reload/--no-reload', default=True, help=reload_help)
@click.argument('config-file', type=click.Path(exists=True), required=False)
def live_command(config_file, dev_addr, reload):
    """
    Serve files locally for development. Reload server on file changes.
    """
    try:
        config = load_config(config_file)
        config.setup('live')
        watch(config)
    except HarrierKnownProblem as e:
        click.secho('Error: {}'.format(e), fg='red', err=True)


@cli.command(name='build')
@click.argument('config-file', type=click.Path(exists=True), required=False)
def build_command(config_file):
    """
    Build for deployment.
    """
    try:
        config = load_config(config_file)
        config.setup('build')
        build(config)
    except HarrierKnownProblem as e:
        click.secho('Error: {}'.format(e), fg='red', err=True)
