import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import unittest
import queue
import threading
import time
from unittest.mock import MagicMock, patch

sys.modules['sounddevice'] = MagicMock()
sys.modules['soundfile'] = MagicMock()
sys.modules['numpy'] = MagicMock()

import audio_recorder.main as main
from audio_recorder.main import AudioRecorderPlugin


class MockSettings:
    def __init__(self, data=None):
        self._data = data or {}
    def get_setting(self, key):
        return self._data.get(key)

class CaptureData:
    def __init__(self, timestamp, data):
        self.timestamp = timestamp
        self.data = data


def make(settings=None):
    p = AudioRecorderPlugin()
    p.settings = MockSettings(settings or {})
    p.load()
    return p


class TestMain(unittest.TestCase):

    def active(self):
        p = make()
        p.capture_event.set()
        p.paused_event.set()
        return p

    def run_start(self, p, on_data=None):
        if on_data is None:
            on_data = MagicMock()
        done = threading.Event()
        t = threading.Thread(target=lambda: [p.start(1.0, MagicMock(return_value=1.0), on_data), done.set()])
        t.daemon = True
        t.start()
        time.sleep(0.05)
        p.capture_event.clear()
        done.wait(timeout=2.0)
        return p

    def test_load_events_cleared(self):
        p = make()
        self.assertFalse(p.capture_event.is_set())
        self.assertFalse(p.paused_event.is_set())

    def test_load_queue_empty(self):
        p = make()
        p.audio_queue.put(b'x')
        p.load()
        self.assertTrue(p.audio_queue.empty())

    def test_load_defaults(self):
        p = make()
        self.assertEqual(p.output_path, "")
        self.assertEqual(p.pause_intervals, [])
        self.assertIsNone(p.last_pause)
        self.assertEqual(p.samplerate, 44100)

    def test_unload_clears_events(self):
        p = make()
        p.capture_event.set()
        p.paused_event.set()
        p.unload()
        self.assertFalse(p.capture_event.is_set())
        self.assertFalse(p.paused_event.is_set())

    def test_unload_closes_soundfile(self):
        p = make()
        sf = MagicMock()
        p.soundfile = sf
        p.unload()
        sf.close.assert_called_once()

    def test_unload_no_soundfile_ok(self):
        p = make()
        p.soundfile = None
        p.unload()

    def test_unload_soundfile_exception_swallowed(self):
        p = make()
        sf = MagicMock()
        sf.close.side_effect = IOError("close failed")
        p.soundfile = sf
        p.unload()

    @patch('os.makedirs')
    def test_prepare_default_settings(self, mk):
        p = make()
        p.prepare('/out', 'rec')
        self.assertEqual(p.output_path, os.path.join('/out', 'rec.wav'))
        self.assertEqual(p.samplerate, 44100)
        self.assertIsNone(p.device_index)

    @patch('os.makedirs')
    def test_prepare_custom_settings(self, mk):
        p = make({'SR': 22050, 'option_microphone': 3})
        p.prepare('/out', 'rec')
        self.assertEqual(p.samplerate, 22050)
        self.assertEqual(p.device_index, 3)

    @patch('os.makedirs')
    def test_prepare_paused_event_set(self, mk):
        p = make()
        p.prepare('/out', 'rec')
        self.assertTrue(p.paused_event.is_set())

    @patch('os.makedirs')
    def test_prepare_intervals_reset(self, mk):
        p = make()
        p.pause_intervals = [(1, 2)]
        p.prepare('/out', 'rec')
        self.assertEqual(p.pause_intervals, [])

    @patch('os.makedirs')
    def test_prepare_makedirs_called(self, mk):
        p = make()
        p.prepare('/out', 'rec')
        mk.assert_called_once_with('/out', exist_ok=True)

    def test_callback_adds_data(self):
        p = self.active()
        indata = MagicMock()
        indata.copy.return_value = b'data'
        p.audio_callback(indata, 1024, None, None)
        self.assertEqual(p.audio_queue.get_nowait(), b'data')

    def test_callback_skips_not_capturing(self):
        p = make()
        p.capture_event.clear()
        p.paused_event.set()
        p.audio_callback(MagicMock(), 1024, None, None)
        self.assertTrue(p.audio_queue.empty())

    def test_callback_skips_paused(self):
        p = make()
        p.capture_event.set()
        p.paused_event.clear()
        p.audio_callback(MagicMock(), 1024, None, None)
        self.assertTrue(p.audio_queue.empty())

    def test_callback_skips_none_indata(self):
        p = self.active()
        p.audio_callback(None, 1024, None, None)
        self.assertTrue(p.audio_queue.empty())

    def test_pause_clears_event(self):
        p = self.active()
        p.pause(10.0)
        self.assertFalse(p.paused_event.is_set())
        self.assertEqual(p.last_pause, 10.0)

    def test_pause_not_capturing(self):
        p = self.active()
        p.capture_event.clear()
        p.pause(10.0)
        self.assertTrue(p.paused_event.is_set())

    def test_pause_already_paused(self):
        p = self.active()
        p.paused_event.clear()
        p.pause(10.0)
        self.assertIsNone(p.last_pause)

    def test_resume_sets_event_and_records_interval(self):
        p = self.active()
        p.pause(10.0)
        p.resume(20.0)
        self.assertTrue(p.paused_event.is_set())
        self.assertIn((10.0, 20.0), p.pause_intervals)
        self.assertIsNone(p.last_pause)

    def test_resume_not_paused(self):
        p = self.active()
        p.resume(20.0)
        self.assertEqual(p.pause_intervals, [])

    def test_resume_multiple_cycles(self):
        p = self.active()
        p.pause(10.0)
        p.resume(20.0)
        p.pause(30.0)
        p.resume(40.0)
        self.assertEqual(p.pause_intervals, [(10.0, 20.0), (30.0, 40.0)])

    def test_resume_not_capturing(self):
        p = self.active()
        p.capture_event.clear()
        p.paused_event.clear()
        p.resume(20.0)
        self.assertEqual(p.pause_intervals, [])

    def test_stop_clears_capture_event(self):
        p = self.active()
        p.stop(100.0)
        self.assertFalse(p.capture_event.is_set())

    def test_stop_records_stop_ts(self):
        p = self.active()
        p.stop(100.0)
        self.assertEqual(p.recording_stop, 100.0)

    def test_stop_active_pause_records_interval(self):
        p = self.active()
        p.last_pause = 50.0
        p.stop(100.0)
        self.assertIn((50.0, 100.0), p.pause_intervals)
        self.assertIsNone(p.last_pause)

    def test_stop_sets_paused_event(self):
        p = make()
        p.capture_event.set()
        p.paused_event.clear()
        p.stop(100.0)
        self.assertTrue(p.paused_event.is_set())

    def test_save_end_of_data_clears_path(self):
        p = make()
        p.output_path = '/tmp/t.wav'
        p.save([], end_of_data=True)
        self.assertIsNone(p.output_path)

    def test_save_keeps_path(self):
        p = make()
        p.output_path = '/tmp/t.wav'
        p.save([], end_of_data=False)
        self.assertEqual(p.output_path, '/tmp/t.wav')

    def test_save_data_does_not_raise(self):
        p = make()
        cd = CaptureData(1.0, b'audio')
        p.save([cd], end_of_data=False)

    def test_extension(self):
        self.assertEqual(make().get_file_extension(), 'wav')

    def test_descriptor_fields(self):
        p = make()
        p.samplerate = 44100
        p.channels = 1
        d = p.get_output_descriptor()
        self.assertEqual(d['type'], 'audio')
        self.assertEqual(d['format'], 'wav')
        self.assertEqual(d['samplerate'], 44100)
        self.assertEqual(d['channels'], 1)

    def test_descriptor_has_all_keys(self):
        p = make()
        p.samplerate = 22050
        p.channels = 2
        d = p.get_output_descriptor()
        for k in ('type', 'format', 'samplerate', 'channels'):
            self.assertIn(k, d)

    def test_start_sets_recording_start(self):
        p = make()
        p.output_path = ""
        p = self.run_start(p)
        self.assertEqual(p.recording_start, 1.0)

    def test_start_opens_soundfile(self):
        p = make()
        p.output_path = "/tmp/test.wav"
        main.sf.SoundFile.reset_mock()
        self.run_start(p)
        main.sf.SoundFile.assert_called_once()

    def test_start_opens_input_stream(self):
        p = make()
        p.output_path = "/tmp/test.wav"
        main.sd.InputStream.reset_mock()
        self.run_start(p)
        main.sd.InputStream.assert_called_once()

    def test_start_soundfile_closed_in_finally(self):
        p = make()
        p.output_path = "/tmp/test.wav"
        mock_sf = MagicMock()
        main.sf.SoundFile.return_value = mock_sf
        self.run_start(p)
        mock_sf.close.assert_called()

    def test_start_writes_queued_audio(self):
        p = make()
        p.output_path = "/tmp/test.wav"
        mock_sf = MagicMock()
        main.sf.SoundFile.return_value = mock_sf
        done = threading.Event()
        t = threading.Thread(target=lambda: [p.start(1.0, MagicMock(return_value=1.0), MagicMock()), done.set()])
        t.daemon = True
        t.start()
        time.sleep(0.02)
        p.audio_queue.put(b"audio_chunk")
        time.sleep(0.05)
        p.capture_event.clear()
        done.wait(timeout=2.0)
        mock_sf.write.assert_called()


if __name__ == '__main__':
    unittest.main()
