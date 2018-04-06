import logging
import subprocess
from time import time

from grablib.download import Downloader
from grablib.build import Builder

from .common import Config, HarrierProblem, logger


def run_grablib(config: Config, *, debug=False):
    if config.download:
        download = Downloader(
            download_root=config.download_root,
            download=config.download,
            aliases=config.download_aliases,
            lock=config.theme_dir / '.grablib.lock',
        )
        download()

    sass_dir = config.theme_dir / 'sass'
    if sass_dir.is_dir():
        build = Builder(
            build_root=config.dist_dir,
            build={
                'sass': {
                    str(config.sass_dir): str(sass_dir)
                }
            },
            download_root=config.download_root,
            debug=debug,
        )
        build()


def run_webpack(config: Config, *, watch=False, mode='production'):
    if not config.webpack_run:
        return

    if not config.webpack_cli.exists():
        logger.info('webpack cli path "%s" does not exist, not running webpack', config.webpack_cli)
        return

    entry_path = (config.theme_dir / config.webpack_entry).resolve()
    if not entry_path.exists():
        logger.info('webpack entry point "%s" does not exist, not running webpack', entry_path)
        return

    output_path = (config.dist_dir / config.webpack_output_path).resolve()

    # ./ is required to satisfy webpack when files are inside --context
    args = (
        config.webpack_cli.relative_to(config.source_dir),
        '--context', config.theme_dir,
        '--entry', f'./{entry_path.relative_to(config.theme_dir)}',
        '--output-path', output_path,
        '--output-filename', config.webpack_output_filename,
        '--devtool', 'source-map',
        '--mode', mode,
    )
    if watch:
        args += '--watch',
    if mode == 'production':
        args += '--optimize-minimize',

    if config.webpack_config:
        config_path = (config.source_dir / config.webpack_config).resolve()
        if not config_path.exists():
            logger.warning('webpack config set but does not exist "%s", not running webpack', config_path)
            return
        args += '--config', f'./{config_path.relative_to(config.theme_dir)}'

    args = [str(a) for a in args]
    cmd = ' '.join(args)
    kwargs = dict(check=True, cwd=config.source_dir)
    logger.info('running webpack ...')
    logger.debug('webpack command "%s"', cmd)
    if not logger.isEnabledFor(logging.DEBUG):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    start = time()
    # loop = asyncio.get_event_loop()
    try:
        # loop.run_until_complete(asyncio.create_subprocess_exec(*args, **kwargs))
        subprocess.run(args, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.warning('error running webpack "%s", returncode %s\nstdout: %s\nstderr: %s',
                       cmd, e.returncode, e.output, e.stderr)
        raise HarrierProblem('error running webpack')
    else:
        logger.info('webpack completed successfully in %0.2fs', time() - start)
