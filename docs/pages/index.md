---
title: 'harrier | A better static site generator'
description: 'Fast builds with first class jinja, scss, webpack support and CDN compatibility'
---

A better static site generator.

Harrier exists because other static site generators like
*jekyll*, *hugo*, *mkdocs* and *gatsby* didn't suffice.

Some advantages of *harrier*:

* Fast:: roughly 5x faster than jekyll. In development mode harrier can perform partial rebuilds
where possible to save even more time
* Livereload:: on changes meaning instant feedback without the need to hit refresh.
* jinja:: templates, the most powerful and intuitive template engine around.
* extensions:: written in python to override virtually any part of config or the site.
* frontmatter:: extended frontmatter, like jekyll's frontmatter but on steroids.
* sass:: support built in for effortless development and optimised deploys.
* webpack:: for 21st century javascript development.
* url hashes:: all assets ar renamed `whatever.[hash].ext`, meaning good CDN compatibility and guarenteed content
  update after a deploy. These paths are reflected in templates and sass using custom lookup functions.
* simple:: sass, markdown, extensions, webpack just work with no complex faff.


## Installation

Simply

    pip install harrier

## CLI Usage

**TODO** init

For development including rebuild on file change, a development server at `localhost:8000` and livereload in the
browser use

    harrier dev

For a production build_use_x "whatever"

    harrier build

For more information and options append `--help` to any of the above commands.

## Anatomy

In it's very simplest form harrier will build a single file `pages/index.md` to create a site containing one file
`dist/index.html`.

The files required to build a comprehensive site look like this:

    ├── harrier.yml
    ├── extensions.py
    ├── webpack_config.js
    ├── pages
    │   ├── index.md
    │   └── foobar.md
    └── theme
        ├── sass
        │   └── main.scss
        ├── js
        │   └── index.js
        ├── templates
        │   ├── base.jinja
        │   └── main.jinja
        └── assets
            ├── favicon.ico
            └── images
                └── whatever.png

* `harrier.yml`:: contains configuration on how harrier will build the site
* `extensions.py`:: add custom functionality to harrier and modify the site at build time
* `webpack_config.js`:: standard config for webpack, harrier takes care of running webpack during development
  and production builds
* `pages`:: contains `.md` and `.html` files which are built to form the site
* `theme/sass`:: `.sass` and `.scss` files to compile into `.css` files
* `theme/templates`:: jinja templates used to build the site
* `theme/assets`:: any other files used in the site, eg. images. These will be copied into the root of your site

Which will build the following site:

    └── dist
        ├── index.html
        ├── foobar
        │   └── index.html
        ├── favicon.ico
        ├── images
        │   └── whatever.[hash].png
        └── theme
            ├── main.[hash].js
            ├── main.[hash].css
            └── main.[hash].css.map

## Extended frontmatter

### Basic

Simple frontmatter matching *jekyll*:

    ---
    template: main.jinja
    uri: /path-to-page
    ---
    This is the content.

equates to page data

```json
{
  "template": "main.jinja",
  "uri": "/path-to-page"
}
```

and content

```markdown
This is the content
```

### Extended: list

Extended usage creating a list for content, note that frontmatter at the beginning of each section is optional,
it is absent for the third item:

    ---
    template: main.jinja
    ---
    name: name of the first section
    ---
    first item content

    snap
    --- . ---
    whatever: [1, 2, 3]
    ---
    second item content

    crackle
    ---.---
    third item content

    pop

equates to page data

```json
{
  "template": "main.jinja"
}
```

and page content

```json
[
  {
    "content": "first item content\n\nsnap",
    "name": "name of the first section"
  },
  {
    "content": "second item content\n\ncrackle",
    "whatever": [1, 2, 3]
  },
  {
    "content": "third item content\n\npop"
  }
]
```

### Extended: dictionary

Extended usage creating a dict for content, note that that frontmatter at the beginning of each section is optional,
it's absent for the third item:

    ---
    template: main.jinja
    ---
    name: name of the first section
    ---
    first item content
    --- second ---
    whatever: [1, 2, 3]
    ---
    second item content
    --- third ---
    third item content

equates to page data

```json
{
  "template": "main.jinja"
}
```

and page content

```json
{
  "main": {
    "content": "first item content",
    "name": "name of the first section"
  },
  "second": {
    "content": "second item content",
    "whatever": [1, 2, 3]
  },
  "third": {
    "content": "third item content"
  }
}
```

## Templates

...

## Sass (and Scss)

...

## Webpack

...

## Data

...

## Extensions

...

## Extra Config

...
