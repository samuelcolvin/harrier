import logging
import sys
import traceback

import click
from grablib.common import GrablibError
from pydantic import ValidationError

from . import main
from .common import HarrierProblem, setup_logging
from .config import Mode
from .version import VERSION

steps_help = 'Build steps to run, multiple values allowed, default: all.'
dev_help = 'Whether to build in development or production mode, default: production.'
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
@click.option('--steps', '-s', multiple=True, type=click.Choice(main.ALL_STEPS), help=steps_help)
@click.option('-d/-p', '--dev/--prod', 'dev_mode', default=None, help=dev_help)
@click.option('-v/-q', '--verbose/--quiet', 'verbose', default=None, help=verbose_help)
def build(path, dev_mode, steps, verbose):
    """
    build the site
    """
    setup_logging(verbose)
    mode = None
    if dev_mode is not None:
        mode = Mode.development if dev_mode else Mode.production

    try:
        main.build(path, set(steps), mode)
    except (HarrierProblem, ValidationError, GrablibError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        logger.debug(traceback.format_exc())
        logger.error(msg.format(e))
        sys.exit(2)


@cli.command()
@click.argument('path', type=click.Path(exists=True), required=False, default='.')
@click.option('-p', '--port', default=8000, type=int, help='port to use for dev server.')
@click.option('-v/-q', '--verbose/--quiet', 'verbose', default=None, help=verbose_help)
def dev(path, port, verbose):
    """
    Serve the site while watching for file changes and rebuilding upon changes.
    """
    setup_logging(verbose, dev=True)
    try:
        main.dev(path, port)
    except (HarrierProblem, ValidationError, GrablibError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        logger.debug(traceback.format_exc())
        logger.error(msg.format(e))
        sys.exit(2)
