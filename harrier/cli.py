import logging
import sys
import traceback

import click
from grablib.common import GrablibError
from pydantic import ValidationError

from .common import HarrierProblem, setup_logging
from .main import build as _build
from .main import dev as _dev
from .version import VERSION

target_help = 'choice from targets in harrier.yml, defaults to same value as action eg. build or serve.'
verbose_help = 'Enable verbose output.'
logger = logging.getLogger('harrier')


@click.group()
@click.version_option(VERSION, '-V', '--version', prog_name='harrier')
def cli():
    """
    harrier - yet another static site builder
    """
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True), required=False, default='.')
@click.option('-v/-q', '--verbose/--quiet', 'verbose', default=None)
def build(path, verbose):
    """
    build the site
    """
    setup_logging(verbose)
    try:
        _build(path)
    except (HarrierProblem, ValidationError, GrablibError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        logger.debug(traceback.format_exc())
        logger.error(msg.format(e))
        sys.exit(2)


@cli.command()
@click.argument('path', type=click.Path(exists=True), required=False, default='.')
@click.option('-p', '--port', default=8000, type=int)
@click.option('-v/-q', '--verbose/--quiet', 'verbose', default=None)
def dev(path, port, verbose):
    """
    Serve the site while watching for file changes and rebuilding upon changes.
    """
    setup_logging(verbose, dev=True)
    try:
        _dev(path, port)
    except (HarrierProblem, ValidationError, GrablibError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        logger.debug(traceback.format_exc())
        logger.error(msg.format(e))
        sys.exit(2)
