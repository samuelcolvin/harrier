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


class ClickHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'blue',
        logging.INFO: 'green',
        logging.WARN: 'orange',
    }

    def emit(self, record):
        log_entry = self.format(record)
        colour = self.colours.get(record.levelno, 'red')
        click.secho(log_entry, fg=colour)


def setup_logging(verbose=False):
    handler = ClickHandler()
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


@click.command()
@click.version_option(VERSION, '-V', '--version')
@click.argument('action', type=click.Choice(['serve', 'build']))
@click.argument('config-file', type=click.Path(exists=True), required=False)
@click.option('-a', '--dev-addr', help=dev_address_help, metavar='<IP:PORT>')
@click.option('--reload/--no-reload', default=True, help=reload_help)
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def cli(action, config_file, dev_addr, reload, verbose):
    """
    harrier - Jinja2 & sass/scss aware site builder builder
    """
    setup_logging(verbose)
    try:
        config = load_config(config_file)
        if action == 'serve':
            config.setup('live')  # FIXME
            watch(config)
        else:
            assert action == 'build'
            config.setup('build')  # FIXME
            build(config)
    except HarrierKnownProblem as e:
        click.secho('Error: {}'.format(e), fg='red', err=True)
