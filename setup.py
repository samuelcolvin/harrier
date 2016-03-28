from setuptools import setup
from harrier import VERSION

description = 'Jinja2 & sass/scss aware site builder'


def check_livereload_js():
    import hashlib
    from pathlib import Path
    live_reload_221_hash = 'a451e4d39b8d7ef62d380d07742b782f'
    live_reload_221_url = 'https://raw.githubusercontent.com/livereload/livereload-js/v2.2.1/dist/livereload.js'

    path = Path(__file__).absolute().parent.joinpath('harrier/livereload.js')
    if path.is_file():
        with path.open('rb') as fr:
            file_hash = hashlib.md5(fr.read()).hexdigest()
        if file_hash == live_reload_221_hash:
            return

    import urllib.request

    print('downloading livereload:\nurl:  {}\npath: {}'.format(live_reload_221_url, path))
    with urllib.request.urlopen(live_reload_221_url) as r:
        with path.open('wb') as fw:
            fw.write(r.read())

check_livereload_js()


setup(
    name='harrier',
    version=str(VERSION),
    description=description,
    long_description=description,
    classifiers=[
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='css,sass,scss,jinja,jinja2,build,static,static site generator',
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/harrier',
    license='MIT',
    packages=['harrier'],
    zip_safe=True,
    include_package_data=True,
    entry_points="""
        [console_scripts]
        harrier=harrier.cli:cli
    """,
    install_requires=[
        'Jinja2>=2.8',
        'PyYAML>=3.11',
        'click>=6.2',
        'libsass>=0.10.1',
        'watchdog>=0.8.3',
        'aiohttp>=0.21.2',
    ]
)
