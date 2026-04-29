# Audio Capture Plugin

A plugin for Multimodal Observer that records audio from a microphone and saves it as a timestamped WAV file.

## Features

- Captures audio from any available input device
- Saves data in `.wav` format (PCM 16-bit)
- Configurable microphone selection and sample rate via plugin properties
- Supports pause and resume during a recording session

## Configuration Options

| Property | Description | Default |
|----------|-------------|---------|
| `option_microphone` | Input device to record from | First available input device |
| `SR` | Sample rate in Hz (4000 – 200000) | `44100` |

## Output Format

The plugin produces a single WAV file per session:

```
session_file.wav
```

The file descriptor returned by the plugin contains:

```json
{
  "type": "audio",
  "format": "wav",
  "samplerate": 44100,
  "channels": 1
}
```

- `type` — always `"audio"`
- `format` — always `"wav"`
- `samplerate` — the sample rate configured for the session
- `channels` — number of recorded channels (mono by default)

## How It Works

- Uses `sounddevice.InputStream` to open the selected microphone at the configured sample rate
- Each incoming audio block is passed to a callback that enqueues it only when the plugin is actively recording and not paused
- A dedicated loop drains the queue and writes each chunk to a WAV file via `soundfile`
- Pause and resume are handled through threading events, which stop and restart enqueuing without closing the audio stream
- On stop, any remaining buffered audio is flushed to disk before the file is closed
