import subprocess
from pathlib import Path

from grablib.download import Downloader
from grablib.build import Builder

from .common import Config, logger


def download_assets(config: Config):
    if not config.download:
        return
    download = Downloader(
        download_root=config.download_root,
        download=config.download,
        aliases=config.download_aliases,
        lock=config.theme_dir / '.grablib.lock',
    )
    download()


def build_sass(config: Config, debug=False):
    sass_dir = config.theme_dir / 'sass'
    if not sass_dir.is_dir():
        return
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


def build_webpack(config: Config, mode='production'):
    if not config.webpack_run:
        return

    if not config.webpack_cli.exists():
        logger.info('webpack cli path "%s" does not exist, not running webpack', config.webpack_cli)
        return

    entry_path = (config.theme_dir / config.webpack_entry).resolve()
    if not entry_path.exists():
        logger.info('webpack entry point "%s" does not exist, not running webpack', entry_path)
        return

    output_path = (config.theme_dir / config.webpack_output_path).resolve()
    args = config.webpack_cli, '--entry', entry_path, '--output-path', output_path, '--mode', mode

    if config.webpack_config:
        config_path = (config.source_dir / config.webpack_config).resolve()
        if not config_path.exists():
            logger.warning('webpack config set but does not exist "%s", not running webpack', config_path)
            return
        args += '--config', config_path

    args = [str(a) for a in args]
    logger.info('running webpack "%s"...', ' '.join(args))
    subprocess.run(args, check=True, cwd=config.source_dir)
