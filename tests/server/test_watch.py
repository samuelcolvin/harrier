import time
from datetime import datetime
from unittest.mock import patch

from watchdog.events import FileMovedEvent

from harrier.serve import serve
from harrier.watch import HarrierEventHandler, watch, SubprocessController, SubprocessGroupController


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


def test_subprocess_simple_echo(capsys):
    spc = SubprocessController('echo hello')
    time.sleep(0.01)
    assert spc.check() is None
    _, stderr = capsys.readouterr()
    assert stderr == 'subprocess "echo hello" exited\n'
    # should do nothing
    spc.terminate()


def test_subprocess_non_zero_exit(capsys):
    spc = SubprocessController('cat foobar')
    time.sleep(0.01)
    assert spc.check() is None
    _, stderr = capsys.readouterr()
    assert stderr == 'subprocess "cat foobar" exited with errors (1)\n'


def test_subprocess_sleep(capsys):
    spc = SubprocessController('sleep 2')
    assert spc.check() is True
    _, stderr = capsys.readouterr()
    assert stderr == ''
    spc.terminate()
    time.sleep(0.01)
    assert spc.check() is None
    _, stderr = capsys.readouterr()
    assert stderr == 'subprocess "sleep 2" exited with errors (-15)\n'


def test_subprocess_group_good():
    spgc = SubprocessGroupController(['sleep 1', 'sleep 2'])
    assert spgc.check() is True


def test_subprocess_group_bad(capsys):
    spgc = SubprocessGroupController(['cat foobar'])
    time.sleep(0.01)
    assert spgc.check() is False
    _, stderr = capsys.readouterr()
    assert stderr == 'subprocess "cat foobar" exited with errors (1)\n'


class MockHarrierEventHandler(HarrierEventHandler):
    wait_delay = 0.1

    def __init__(self):
        self.build_count = 0
        self.build_check_count = 0
        self._build_time = datetime(2000, 1, 1)
        self._passing = True

    def build(self):
        self.build_count += 1

    def check_build(self):
        self.build_check_count += 1


def test_on_any_event_built1():
    e_handler = MockHarrierEventHandler()
    assert e_handler.build_count == 0
    e_handler.on_any_event('foobar')
    assert e_handler.build_count == 1


def test_on_any_event_built2():
    e_handler = MockHarrierEventHandler()
    e_handler.on_any_event(FileMovedEvent('x', 'y'))
    assert e_handler.build_count == 1


def test_on_any_event_not_built():
    e_handler = MockHarrierEventHandler()
    e_handler.on_any_event(FileMovedEvent('x', 'y.___jb_xxx___'))
    assert e_handler.build_count == 0


def test_handler_wait():
    c = 0

    def mock_extra_check():
        nonlocal c
        c += 1
        return c != 2

    e_handler = MockHarrierEventHandler()
    assert e_handler.build_check_count == 0
    e_handler.wait(mock_extra_check)
    assert e_handler.build_check_count == 2
