import traceback

import click
from grablib.common import GrablibError
from pydantic import ValidationError

from .build import build
from .common import HarrierProblem, logger, setup_logging
from .version import VERSION

target_help = 'choice from targets in harrier.yml, defaults to same value as action eg. build or serve.'
verbose_help = 'Enable verbose output.'


@click.command()
@click.version_option(VERSION, '-V', '--version')
@click.argument('action', type=click.Choice(['serve', 'build']))
@click.argument('config-file', type=click.Path(exists=True), required=False, default='.')
@click.option('-v/-q', '--verbose/--quiet', 'verbose', default=None)
def cli(action, config_file, verbose):
    """
    harrier - Jinja2 & sass/scss aware site builder
    """
    if verbose is True:
        log_level = 'DEBUG'
    elif verbose is False:
        log_level = 'WARNING'
    else:
        assert verbose is None
        log_level = 'INFO'
    setup_logging(log_level)
    try:
        build(config_file)
    except (HarrierProblem, ValidationError, GrablibError) as e:
        msg = 'Error: {}'
        if not verbose:
            msg += '\n\nUse "--verbose" for more details'
        logger.debug(traceback.format_exc())
        logger.error(msg.format(e))
