from unittest.mock import patch

from harrier.serve import serve
from harrier.watch import HarrierEventHandler, watch


def test_serve_watch_handler(simpleharrier):
    event_handler = HarrierEventHandler(simpleharrier.config)
    event_handler.build()
    assert simpleharrier.tmpdir.join('build', 'test.js').read_text('utf8') == 'var hello = 1;'


def test_serve_start(simpleharrier):

    with patch.object(HarrierEventHandler, 'wait') as mock_method:
        watch(simpleharrier.config)

    assert mock_method.called


def test_serve_run(port):
    with patch('harrier.serve.web.run_app') as mock_run_app:
        serve('.', '/', port)

    assert mock_run_app.called
