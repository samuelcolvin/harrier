from importlib.machinery import SourceFileLoader
from pathlib import Path
from setuptools import setup

description = 'Static site generator'
THIS_DIR = Path(__file__).resolve().parent
try:
    long_description = '\n\n'.join([THIS_DIR.joinpath('README.md').read_text()])
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
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    keywords='css,sass,scss,jinja,jinja2,build,static,static site generator',
    author='Samuel Colvin',
    author_email='s@muelcolvin.com',
    url='https://github.com/samuelcolvin/harrier',
    license='MIT',
    packages=['harrier'],
    python_requires='>=3.8',
    zip_safe=True,
    entry_points="""
        [console_scripts]
        harrier=harrier.cli:cli
    """,
    install_requires=[
        'aiohttp>=3.8',
        'aiohttp-devtools>=1.1',
        'click>=7',
        'devtools>=0.11',
        'grablib>=0.8',
        'Jinja2>=3',
        'libsass>=0.21',
        'misaka>=2.1',
        'pillow>=10.0',
        'pydantic>=2.1.1',
        'Pygments>=2.15',
        'ruamel.yaml>=0.17',
        'watchfiles>=0.19.0',
    ]
)
