from unittest.mock import patch
from harrier.serve import HarrierEventHandler, serve


def test_serve_watch_handler(simpleharrier):
    event_handler = HarrierEventHandler(simpleharrier.config)
    event_handler.build()
    assert simpleharrier.tmpdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_serve_start(simpleharrier):

    with patch.object(HarrierEventHandler, 'wait') as mock_method:
        serve(simpleharrier.config)

    assert mock_method.called
