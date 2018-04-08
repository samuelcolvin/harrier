import asyncio
import logging
import os
import shutil
import subprocess
from time import time

from grablib.build import Builder
from grablib.download import Downloader

from .common import HarrierProblem
from .config import Config

logger = logging.getLogger('harrier.assets')


def run_grablib(config: Config, *, debug=False):
    download_root = config.theme_dir / 'libs'
    if config.download:
        logger.debug('running grablib download...')
        download = Downloader(
            download_root=download_root,
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
            download_root=download_root,
            debug=debug,
        )
        build()


def copy_assets(config: Config):
    in_dir = config.theme_dir / 'assets'
    if not in_dir.is_dir():
        return
    out_dir = config.dist_dir / config.dist_dir_assets
    out_dir.relative_to(config.dist_dir)
    logger.info('copying theme assets from "%s" to "%s"',
                in_dir.relative_to(config.source_dir), out_dir.relative_to(config.dist_dir))
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(in_dir, out_dir)


def webpack_configuration(config: Config, mode: str, watch: bool):
    if not config.webpack or not config.webpack.run:
        return None, None

    wp = config.webpack
    prod = mode == 'production'
    output_filename = wp.prod_output_filename if prod else wp.dev_output_filename
    # ./ is required to satisfy webpack when files are inside the "--context" directory
    args = (
        wp.cli,
        '--context', config.source_dir,
        '--entry', f'./{wp.entry.relative_to(config.source_dir)}',
        '--output-path', wp.output_path,
        output_filename and '--output-filename', output_filename,
        '--devtool', 'source-map',
        '--mode', mode,
        watch and '--watch',
        prod and '--optimize-minimize',
        wp.config and '--config',
        wp.config and f'./{wp.config.relative_to(config.source_dir)}',
    )
    env = dict(**os.environ, **{
        'NODE_ENV': mode,
        # 'HARRIER_CONFIG': json.dumps(config.dict())  # TODO
    })
    return [str(a) for a in args if a], env


def run_webpack(config: Config, *, mode='production'):
    args, env = webpack_configuration(config, mode, False)
    if not args:
        return
    cmd = ' '.join(args)
    kwargs = dict(check=True, cwd=config.source_dir, env=env)
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
        raise HarrierProblem('error running webpack') from e
    else:
        logger.info('webpack completed successfully in %0.2fs', time() - start)


async def start_webpack_watch(config: Config, *, mode='development'):
    args, env = webpack_configuration(config, mode, True)
    if args:
        cmd = ' '.join(args)
        logger.info('running webpack ...')
        logger.debug('webpack command "%s"', cmd)
        return await asyncio.create_subprocess_exec(*args, cwd=config.source_dir, env=env)
