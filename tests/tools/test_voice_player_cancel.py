"""Stopping a player ends the attempt chain; an unavailable player still falls back."""
import sys
import threading
from types import SimpleNamespace

from tests.waiting import wait_until
from tools import voice_mode


def _players(monkeypatch, tmp_path, first):
    source = tmp_path / 'speech.ogg'
    source.write_bytes(b'player lifecycle fixture')
    fallback = tmp_path / 'fallback-started'
    second = [sys.executable, '-c', f'from pathlib import Path; Path({str(fallback)!r}).touch()']
    monkeypatch.setattr(voice_mode, '_system_player_candidates', lambda _path: [first, second])
    monkeypatch.setattr(voice_mode, '_import_audio', lambda: (SimpleNamespace(stop=lambda: None), None))
    return source, fallback


def test_explicit_stop_does_not_replay_audio_with_another_player(monkeypatch, tmp_path):
    source, fallback = _players(monkeypatch, tmp_path,
                                [sys.executable, '-c', 'import threading; threading.Event().wait(60)'])
    worker = threading.Thread(target=voice_mode.play_audio_file, args=(str(source),))
    worker.start()
    try:
        wait_until(lambda: voice_mode._active_playback is not None, timeout=3)
        voice_mode.stop_playback()
        worker.join(timeout=3)
        assert not worker.is_alive()
        assert not fallback.exists()
    finally:
        voice_mode.stop_playback()
        worker.join(timeout=3)


def test_unavailable_player_still_tries_the_next_candidate(monkeypatch, tmp_path):
    source, fallback = _players(monkeypatch, tmp_path, [sys.executable, '-c', 'raise SystemExit(1)'])
    assert voice_mode.play_audio_file(str(source))
    assert fallback.exists()
