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
