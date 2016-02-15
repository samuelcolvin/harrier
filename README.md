harrier
=======

[![Build Status](https://travis-ci.org/samuelcolvin/harrier.svg?branch=master)](https://travis-ci.org/samuelcolvin/harrier)
[![codecov.io](https://codecov.io/github/samuelcolvin/harrier/coverage.svg?branch=master)](https://codecov.io/github/samuelcolvin/harrier?branch=master)

**(Named after the hound, not the plane.)**

Jinja2 & sass/scss aware site builder

## What?

Assert generator in the same vane as webpack/gulp & browsify but tailored to sass/scss and Jinja2.
Javascript support via integration with webpack. Harrier also supports arbitrary build steps via 
composable "tools".

## Why?

Well partly because I couldn't find a tools to do what I wanted.

Partly because I'm much happier with everything that doesn't have to be javascript not being python.

## Install

(once it's released)

    pip install harrier

## Usage

    harrier --help

## TODO

* partial rebuilds
* test coverage, server test
* hash name extension
* watch mode as well as serve
* support testing - what can we test?
* html tidy
* switch to aiohttp server with better logging
* jinja minify https://github.com/mitsuhiko/jinja2-htmlcompress
* css map files
* `.min.` and `.map` support
* support harrier serving on one port while another tool runs on anther, this not required
