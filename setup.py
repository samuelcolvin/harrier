from setuptools import setup
from harrier import VERSION

description = 'Jinja2 & sass/scss aware site builder'

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
        'Programming Language :: Python :: 3.4',
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
        'livereload>=2.4.1',
    ]
)
