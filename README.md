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

(once it's released)

    pip install harrier

## Usage

    harrier --help

## TODO

* sass variables eg. precision, style
* subprocess support, eg. to user `webpack --watch` in serve mode
* sass import callbacks for bower: https://github.com/dahlia/libsass-python/blob/python/sass.py#L423-L464, see eyeglass, wiredep
* hash name extension
* test coverage, server test
* watch mode as well as serve
* support testing - what can we test?
* html tidy
* switch to aiohttp server with better logging
* jinja minify https://github.com/mitsuhiko/jinja2-htmlcompress
* css map files
* `.min.` and `.map` support
* support harrier serving on one port while another tool runs on anther, this is perhaps not required could work with webpack-dev-server
