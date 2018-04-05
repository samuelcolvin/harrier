from grablib.download import Downloader
from grablib.build import Builder

from .common import Config


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
                str(config.dist_dir_sass): str(sass_dir)
            }
        },
        download_root=config.download_root,
        debug=debug,
    )
    build()
