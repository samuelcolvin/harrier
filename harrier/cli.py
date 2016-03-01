import click
import logging

from harrier import VERSION
from .build import build
from .config import load_config
from .common import logger, HarrierKnownProblem
from .serve import serve

config_help = 'Provide a specific harrier config yml file path.'
dev_address_help = 'IP address and port to serve documentation locally (default: localhost:8000).'
target_help = 'choice from targets in harrier.yml, defaults to same value as action eg. build or serve.'
site_dir_help = 'The directory to output the result of the documentation build.'
reload_help = 'Enable and disable the live reloading in the development server.'
verbose_help = 'Enable verbose output.'


class ClickHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'blue',
        logging.INFO: 'green',
        logging.WARN: 'yellow',
    }

    def emit(self, record):
        log_entry = self.format(record)
        colour = self.colours.get(record.levelno, 'red')
        click.secho(log_entry, fg=colour)


def setup_logging(verbose=False):
    for h in logger.handlers:
        if isinstance(h, ClickHandler):
            return
    handler = ClickHandler()
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


@click.command()
@click.version_option(VERSION, '-V', '--version')
@click.argument('action', type=click.Choice(['serve', 'build']))
@click.argument('config-file', type=click.Path(exists=True), required=False)
@click.option('-t', '--target', help=dev_address_help)
@click.option('-a', '--dev-addr', help=dev_address_help, metavar='<IP:PORT>')
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def cli(action, config_file, target, dev_addr, verbose):
    """
    harrier - Jinja2 & sass/scss aware site builder
    """
    setup_logging(verbose)
    try:
        config = load_config(config_file)
        target = target or action
        config.setup(target)
        if action == 'serve':
            serve(config)
        else:
            assert action == 'build'
            build(config)
    except HarrierKnownProblem as e:
        msg = 'Error: {}'
        if not verbose:
            msg += ', use "--verbose" for more details'
        click.secho(msg.format(e), fg='cyan', err=True)
