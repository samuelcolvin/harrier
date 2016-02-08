from harrier.build import build

from harrier.config import load_config


def test_simple_build(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    p = tmpworkdir.join('harrier.yml')
    p.write("""\
root: .
target:
  build:
    path: build""")
    config = load_config('harrier.yml')
    config.setup('build')
    build(config)
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_build_no_config(tmpworkdir):
    js = tmpworkdir.join('test.js')
    js.write('var hello = 1;')
    config = load_config(None)
    config.setup('build')
    build(config)
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert [p.basename for p in tmpworkdir.join('build').listdir()] == ['test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_build_css_js(tmpworkdir):
    tmpworkdir.join('test.js').write('var hello = 1;')
    tmpworkdir.join('styles.scss').write('a { b { color: blue; } }')
    config = load_config(None)
    config.setup('build')
    build(config)
    build_dir = tmpworkdir.join('build')
    assert build_dir.check()
    assert sorted([p.basename for p in tmpworkdir.join('build').listdir()]) == ['styles.css', 'test.js']
    assert tmpworkdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'
    assert tmpworkdir.join('build', 'styles.css').read_text('utf8') == 'a b {\n  color: blue; }\n'


def test_jinja(tmpworkdir):
    tmpworkdir.join('index.html').write('{{ 42 + 5 }}')
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'index.html').read_text('utf8') == '47'


def test_jinja_static(tmpworkdir):
    tmpworkdir.join('foo.txt').write('hello')
    tmpworkdir.join('index.html').write("{{ 'foo.txt'|static }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'index.html').read_text('utf8') == 'foo.txt'


def test_jinja_static2(tmpworkdir):
    tmpworkdir.mkdir('path')
    tmpworkdir.join('path', 'foo.txt').write('hello')
    tmpworkdir.join('path', 'index.html').write("{{ 'foo.txt'|static }}")
    config = load_config(None)
    config.setup('build')
    build(config)
    assert tmpworkdir.join('build', 'path', 'index.html').read_text('utf8') == 'foo.txt'
