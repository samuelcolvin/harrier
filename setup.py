from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

description = 'Static site generator'
THIS_DIR = Path(__file__).resolve().parent
try:
    long_description = '\n\n'.join([
        THIS_DIR.joinpath('README.md').read_text(),
        # THIS_DIR.joinpath('HISTORY.md').read_text()
    ])
except FileNotFoundError:
    long_description = description + '.\n\nSee https://harrier.helpmanual.io/ for documentation.'

# avoid loading the package before requirements are installed:
version = SourceFileLoader('version', 'harrier/version.py').load_module()

setup(
    name='harrier',
    version=version.VERSION,
    description=description,
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    keywords='css,sass,scss,jinja,jinja2,build,static,static site generator',
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/harrier',
    license='MIT',
    packages=['harrier'],
    python_requires='>=3.6',
    zip_safe=True,
    entry_points="""
        [console_scripts]
        harrier=harrier.cli:cli
    """,
    install_requires=[
        'Jinja2>=2.8',
        'Pygments>=2.2.0',
        'aiohttp-devtools>=0.10, <=0.11',
        'click>=6.2',
        'devtools>=0.3',
        'grablib>=0.7.4',
        'libsass>=0.14.5',
        'misaka>=2.1.0',
        'pillow>=5.1.0',
        'pydantic==0.20',
        'ruamel.yaml>=0.15.37',
        'watchgod>=0.2.0',
    ]
)
