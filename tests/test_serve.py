from unittest.mock import patch
from harrier.serve import build_process, HarrierEventHandler, serve


def test_serve_build(simpleharrier):
    build_process(simpleharrier.config, 0)
    assert simpleharrier.tmpdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_serve_watch_handler(simpleharrier):
    event_handler = HarrierEventHandler(simpleharrier.config)
    p = event_handler.async_build()
    p.join()
    assert simpleharrier.tmpdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_serve_start(simpleharrier):

    with patch.object(HarrierEventHandler, 'wait') as mock_method:
        serve(simpleharrier.config)

    assert mock_method.called
