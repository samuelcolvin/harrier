---
title: harrier
---

Static site generator.

## Why

I built harrier because other static site generators like
jekyll, hugo, mkdocs and gatsby didn't cut the mustard.

In particular, harrier:

* builds **fast**, roughly 4x faster than jekyll. In development mode harrier can perform partial rebuilds
  where possible to save even more time.
* automatically **reloads** pages upon changes meaning instant feedback without the need to hit refresh.
* uses **jinja templates**, the most powerful and intuitive template engine around.
* allows **extensions** written in python to override virtually any part of config or the site.
* uses **extended frontmater**, like jekyll's frontmatter but on steroids.
* has **sass** support built in for effortless development and optimised deploys.
* works with **webpack** for 21st century javascript development.
* adds **hashes** to paths of all assets, meaning guarenteed content update after a deploy. These paths
  are reflected in templates and sass using custom lookup functions.


## How

Installation:

```shell
pip install harrier
```
