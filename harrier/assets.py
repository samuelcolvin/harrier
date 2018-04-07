import asyncio
import logging
import shutil
import subprocess
from time import time

from grablib.build import Builder
from grablib.download import Downloader

from .common import HarrierProblem
from .config import Config

logger = logging.getLogger('harrier.assets')


def run_grablib(config: Config, *, debug=False):
    if config.download:
        logger.info('running grablib download...')
        download = Downloader(
            download_root=config.download_root,
            download=config.download,
            aliases=config.download_aliases,
            lock=config.theme_dir / '.grablib.lock',
        )
        download()

    sass_dir = config.theme_dir / 'sass'
    if sass_dir.is_dir():
        logger.info('running sass build...')
        build = Builder(
            build_root=config.dist_dir,
            build={
                'sass': {
                    str(config.dist_dir_sass): str(sass_dir)
                }
            },
            download_root=config.download_root,
            debug=debug,
        )
        build()


def copy_assets(config: Config):
    in_dir = config.theme_dir / 'assets'
    if not in_dir.exists():
        return
    if not in_dir.is_dir():
        raise HarrierProblem(f'assert directory "{in_dir}" is not a directory')
    out_dir = config.dist_dir / config.theme_assets_dir
    logger.info('copying theme assets from "%s" to "%s"',
                in_dir.relative_to(config.source_dir), out_dir.relative_to(config.dist_dir))
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(in_dir, out_dir)


def webpack_args(config: Config, mode: str, watch: bool):
    if not config.webpack or not config.webpack.run:
        return

    # ./ is required to satisfy webpack when files are inside the "--context" directory
    args = (
        config.webpack.cli,
        '--context', config.source_dir,
        '--entry', f'./{config.webpack.entry.relative_to(config.source_dir)}',
        '--output-path', config.webpack.output_path,
        '--output-filename', config.webpack.output_filename,
        '--devtool', 'source-map',
        '--mode', mode,
        watch and '--watch',
        mode == 'production' and '--optimize-minimize',
        config.webpack.config and '--config',
        config.webpack.config and f'./{config.webpack.config.relative_to(config.source_dir)}',
    )
    return [str(a) for a in args if a]


def run_webpack(config: Config, *, mode='production'):
    args = webpack_args(config, mode, False)
    if not args:
        return
    cmd = ' '.join(args)
    kwargs = dict(check=True, cwd=config.source_dir)
    logger.info('running webpack...')
    logger.debug('webpack command "%s"', cmd)
    if not logger.isEnabledFor(logging.DEBUG):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    start = time()
    try:
        subprocess.run(args, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.warning('error running webpack "%s", returncode %s\nstdout: %s\nstderr: %s',
                       cmd, e.returncode, e.output, e.stderr)
        raise HarrierProblem('error running webpack')
    else:
        logger.info('webpack completed successfully in %0.2fs', time() - start)


async def start_webpack_watch(config: Config, *, mode='development'):
    args = webpack_args(config, mode, True)
    if args:
        cmd = ' '.join(args)
        logger.info('running webpack ...')
        logger.debug('webpack command "%s"', cmd)
        return await asyncio.create_subprocess_exec(*args)
