"""Turning voice off must cut playback while the REPL worker drains a reply."""
import queue
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cli import HermesCLI


def _surface(monkeypatch):
    cli = HermesCLI.__new__(HermesCLI)
    cli._agent_running = True
    cli._voice_lock = threading.Lock()
    cli._voice_mode = cli._voice_tts = cli._voice_continuous = True
    cli._voice_recording = False
    cli._voice_recorder = None
    cli._voice_tts_stop = threading.Event()
    cli._voice_tts_done = threading.Event()
    cli._pending_input = queue.Queue()
    cli._attached_images = []
    cli._inline_pastes = lambda _buf: None
    cli._tts_lease_async = lambda _active: None
    # Exercise the real voice handler after routing, without an agent/transport.
    cli.process_command = cli._handle_voice_command
    playback_stopped = threading.Event()
    monkeypatch.setattr('tools.voice_mode.stop_playback', playback_stopped.set)
    return cli, playback_stopped


@pytest.mark.parametrize('command', ['/voice off', '/VOICE OFF', '/voice   off'])
def test_voice_off_cuts_speech_before_busy_worker_returns(monkeypatch, command):
    cli, playback_stopped = _surface(monkeypatch)
    buffer = MagicMock(text=command)
    event = SimpleNamespace(app=SimpleNamespace(current_buffer=buffer, invalidate=lambda: None))
    cli._tui_submit_buffer(event, buffer)
    assert playback_stopped.is_set()
    assert cli._voice_tts_stop.is_set() and cli._voice_tts_done.is_set()
    assert not cli._voice_mode and not cli._voice_tts and not cli._voice_continuous
    assert cli._agent_running  # disabling speech preserves the text-generation turn
    assert cli._pending_input.empty()


@pytest.mark.parametrize('command', ['/voice on', '/voice tts', '/voice status'])
def test_other_voice_commands_keep_normal_queued_dispatch(monkeypatch, command):
    cli, playback_stopped = _surface(monkeypatch)
    buffer = MagicMock(text=command)
    event = SimpleNamespace(app=SimpleNamespace(current_buffer=buffer, invalidate=lambda: None))
    cli._tui_submit_buffer(event, buffer)
    assert not playback_stopped.is_set()
    assert cli._pending_input.get_nowait() == command
