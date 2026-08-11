# Demo audio fixture

`northstar-demo-60s.wav` is generated locally from deterministic low-volume
tones; it is not a recording of a person and contains no copyrighted audio.
Regenerate it with:

```bash
python samples/generate_northstar_demo.py
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 samples/northstar-demo-60s.wav
```

The output is a 72-second mono PCM WAV. The generated waveform and script are
original project assets released under this repository's MIT license.
