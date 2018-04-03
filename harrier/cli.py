import logging
import re

import click
from pydantic import ValidationError

from .build import build
from .common import HarrierProblem, logger
from .version import VERSION

target_help = 'choice from targets in harrier.yml, defaults to same value as action eg. build or serve.'
verbose_help = 'Enable verbose output.'


class ClickHandler(logging.Handler):
    colours = {
        logging.DEBUG: 'white',
        logging.INFO: 'green',
        logging.WARN: 'yellow',
    }

    def emit(self, record):
        log_entry = self.format(record)
        colour = self.colours.get(record.levelno, 'red')
        m = re.match('^(\[.*?\])', log_entry)
        if m:
            time = click.style(m.groups()[0], fg='magenta')
            msg = click.style(log_entry[m.end():], fg=colour)
            click.echo(time + msg)
        else:
            click.secho(log_entry, fg=colour)


def setup_logging(verbose=False, times=False):
    for h in logger.handlers:
        if isinstance(h, ClickHandler):
            return
    handler = ClickHandler()
    fmt = '[%(asctime)s] %(message)s' if times else '%(message)s'
    formatter = logging.Formatter(fmt, datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


@click.command()
@click.version_option(VERSION, '-V', '--version')
@click.argument('action', type=click.Choice(['serve', 'build']))
@click.argument('config-file', type=click.Path(exists=True), required=False, default='.')
@click.option('-v', '--verbose', is_flag=True, help=verbose_help)
def cli(action, config_file, verbose):
    """
    harrier - Jinja2 & sass/scss aware site builder
    """
    is_live = action == 'serve'
    setup_logging(verbose, times=is_live)
    try:
        build(config_file)
    except (HarrierProblem, ValidationError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        click.secho(msg.format(e), fg='red', err=True)
