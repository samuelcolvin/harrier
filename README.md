harrier
=======

[![Build Status](https://travis-ci.org/samuelcolvin/harrier.svg?branch=master)](https://travis-ci.org/samuelcolvin/harrier)
[![codecov.io](https://codecov.io/github/samuelcolvin/harrier/coverage.svg?branch=master)](https://codecov.io/github/samuelcolvin/harrier?branch=master)

**(Named after the hound, not the plane.)**

Jinja2 & sass/scss aware site builder

## What?

Asset generator in the same vane as webpack/gulp & browsify but tailored to sass/scss and Jinja2.
Javascript support via integration with webpack, also supports arbitrary build steps via 
composable "tools".

## Why?

Well partly because I couldn't find a tools to do what I wanted.

Partly because I'm much happier with everything that doesn't have to be javascript not being javascript.

## Install

    pip install -e git+git@github.com:samuelcolvin/harrier.git#egg=harrier

## Usage

    harrier --help

## TODO

* sass variables eg. precision, style
* sass import callbacks for bower: https://github.com/dahlia/libsass-python/blob/python/sass.py#L423-L464, see eyeglass, wiredep
* subprocess options, eg. names, optional start, quiet
* test coverage, server test
* deploy command including "flip-flop" deploys
* complementary package for getting the url of files by looking up assets file
* hash name extension
* html tidy
* jinja minify https://github.com/mitsuhiko/jinja2-htmlcompress
* catch jinja errors and display nicely with relevant traceback
* watch mode as well as serve
* css map files
* `.min.` and `.map` support
* subprocess build support, eg. to user `webpack --watch` in serve mode, can this be done sensibly?
