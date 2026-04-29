import os
import threading
import time
import queue
import traceback
import soundfile as sf
from typing import Callable, Optional
import numpy as np
import sounddevice as sd

from mo.core import load_metadata_json
from mo.modules.capture.plugins.capture_plugin import CaptureData, CapturePlugin

@load_metadata_json(rel_path="../..")
class AudioRecorderPlugin(CapturePlugin):

    """Audio capture plugin using sounddevice and soundfile to 
    record audio from the microphone and save it as a WAV file."""
    
    def __init__(self):
        super().__init__()
        self.on_data_callback: Optional[Callable[[CaptureData], None]] = None
        self.get_timestamp_fn: Optional[Callable[[], float]] = None
        self.soundfile: Optional[sf.SoundFile] = None
        self.audio_queue = queue.Queue()

    def load(self):
        self.capture_event = threading.Event()
        self.paused_event = threading.Event()
        self.pause_lock = threading.Lock()
        self.output_path = ""
        self.samplerate = 44100
        self.device_index = None
        self.channels = 1
        self.recording_start = None
        self.recording_stop = None
        self.pause_intervals = []
        self.last_pause = None
        
        while not self.audio_queue.empty():
            self.audio_queue.get()

    def unload(self):
        self.capture_event.clear()
        self.paused_event.clear()
        if self.soundfile:
            try:
                self.soundfile.close()
            except:
                pass

    def prepare(self, path: str, file_name: str):
        microphone = self.settings.get_setting("option_microphone")
        if microphone is not None:
            self.device_index = microphone
        else:
            self.device_index = None
            
        samplerate = self.settings.get_setting("SR")
        if samplerate is not None:
            self.samplerate = samplerate
        else:
            self.samplerate = 44100
            
        os.makedirs(path, exist_ok=True)
        self.output_path = os.path.join(path, f"{file_name}.wav")  
        self.paused_event.set()
        self.pause_intervals = []
        self.last_pause = None
        self.recording_start = None
        self.recording_stop = None
        self.soundfile = None

    def audio_callback(self, indata, frames, time_info, status):
        if self.capture_event.is_set() and self.paused_event.is_set():
            if indata is not None:
                self.audio_queue.put(indata.copy())

    def start(self, start_ts: float, get_timestamp: Callable[[], float], on_data: Callable[[CaptureData], None]):
        self.recording_start = start_ts
        self.capture_event.set()
        self.get_timestamp_fn = get_timestamp
        self.on_data_callback = on_data  
        self.soundfile = sf.SoundFile(self.output_path, mode='w', samplerate=self.samplerate, channels=self.channels, subtype='PCM_16')
        
        with sd.InputStream(samplerate=self.samplerate, device=self.device_index, channels=self.channels, dtype='int16', callback=self.audio_callback):
            while self.capture_event.is_set():
                try:
                    data = self.audio_queue.get(timeout=0.05)
                    self.soundfile.write(data)
                except queue.Empty:
                    continue

        while not self.audio_queue.empty():
            try:
                data = self.audio_queue.get_nowait()
                if self.soundfile: self.soundfile.write(data)
            except:
                break

        if self.soundfile:
            self.soundfile.flush()
            self.soundfile.close()
            self.soundfile = None

    def save(self, data: list[CaptureData], end_of_data: bool = False):
        if end_of_data:
            self.output_path = None
        return 

    def pause(self, pause: float):
        if not self.capture_event.is_set() or not self.paused_event.is_set():
            return
        self.paused_event.clear()
        self.last_pause = pause
    
    def resume(self, resume: float):
        if not self.capture_event.is_set() or self.paused_event.is_set():
            return
        self.paused_event.set()
        with self.pause_lock:
            if self.last_pause is not None:
                self.pause_intervals.append((self.last_pause, resume))
                self.last_pause = None

    def stop(self, stop_ts: float):
        self.capture_event.clear()
        self.paused_event.set()
        
        with self.pause_lock:
            if self.last_pause is not None:
                self.pause_intervals.append((self.last_pause, stop_ts))
                self.last_pause = None
        self.recording_stop = stop_ts

    def get_file_extension(self) -> str:
        return "wav"

    def get_output_descriptor(self):
        return {
            "type": "audio",
            "format": "wav",
            "samplerate": self.samplerate,
            "channels": self.channels
        }