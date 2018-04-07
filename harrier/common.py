import logging.config

import click


class HarrierProblem(RuntimeError):
    pass


class GrablibHandler(logging.Handler):
    formats = {
        logging.DEBUG: {'fg': 'white', 'dim': True},
        logging.INFO: {'fg': 'white', 'dim': True},
        logging.WARN: {'fg': 'yellow'},
    }

    def get_log_format(self, record):
        return self.formats.get(record.levelno, {'fg': 'red'})

    def emit(self, record):
        log_entry = self.format(record)
        click.secho(log_entry, **self.get_log_format(record))


def log_config(verbose: bool, dev) -> dict:
    if verbose is True:
        log_level = 'DEBUG'
    elif verbose is False:
        log_level = 'WARNING'
    else:
        assert verbose is None
        log_level = 'INFO'
    return {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {
                'format': '%(message)s'
            },
            'server': {
                'format': '[%(asctime)s] %(message)s',
                'datefmt': '%H:%M:%S',
            },
        },
        'handlers': {
            'default': {
                'level': log_level,
                'class': 'grablib.common.ClickHandler',
                'formatter': 'default'
            },
            'build': {
                'level': 'DEBUG' if verbose else ('WARNING' if dev else 'INFO'),
                'class': 'grablib.common.ClickHandler',
                'formatter': 'default'
            },
            'grablib': {
                'level': 'INFO' if verbose else 'WARNING',
                'class': 'harrier.common.GrablibHandler',
                'formatter': 'default'
            },
            'server_logging': {
                'level': log_level,
                'class': 'aiohttp_devtools.runserver.log_handlers.AuxiliaryHandler',
                'formatter': 'server'
            },
        },
        'loggers': {
            'harrier': {
                'handlers': ['default'],
                'level': log_level,
            },
            'harrier.build': {
                'handlers': ['build'],
                'level': log_level,
                'propagate': False,
            },
            'harrier.assets': {
                'handlers': ['build'],
                'level': log_level,
                'propagate': False,
            },
            'grablib': {
                'handlers': ['grablib'],
                'level': log_level,
            },
            'adev.server.aux': {
                'handlers': ['server_logging'],
                'level': log_level,
            },
        },
    }


def setup_logging(verbose, dev=False):
    config = log_config(verbose, dev)
    logging.config.dictConfig(config)
