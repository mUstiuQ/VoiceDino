#Voice Dino

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

Control the hidden **Dino** game in Google Chrome with your **microphone**. When you raise your voice, shout, or clap, the script presses the `Space` key and the dinosaur jumps.

Built in Python as an exercise in real-time audio capture, simple signal processing (RMS), and keyboard input simulation.

## How it works

```
Microphone → PyAudio (1024-sample chunk) → RMS (volume)
           → RMS > threshold ? → cooldown elapsed ? → pyautogui presses Space → the dino jumps
```

Each audio chunk lasts `1024 / 44100 ≈ 23 ms`, so the reaction to sound is practically instant.

## Features

- continuous real-time audio capture (`pyaudio`, 16-bit, 44100 Hz, mono);
- volume computed as the **RMS** value;
- **configurable threshold** for triggering a jump;
- optional **calibration** of the ambient noise at startup;
- **cooldown** between jumps (prevents repeated key presses while the sound persists);
- live volume meter in the terminal;
- clean shutdown on `Ctrl+C` (the audio stream is closed properly).

## Requirements

- Python 3.9 or newer
- a microphone
- Google Chrome (the game opens at `chrome://dino`)

## Installation

```bash
git clone https://github.com/mUstiuQ/voice-dino.git
cd voice-dino

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### PyAudio-specific steps

`pyaudio` needs the PortAudio library:

| System | What to do |
|---|---|
| **Windows** | `pip install pyaudio` usually works directly. If you get a build error: `pip install pipwin`, then `pipwin install pyaudio`. |
| **macOS** | `brew install portaudio`, then `pip install pyaudio`. Grant your terminal the **Microphone** and **Accessibility** permissions (System Settings → Privacy & Security). |
| **Linux (Debian/Ubuntu)** | `sudo apt install portaudio19-dev python3-dev`, then `pip install pyaudio`. `pyautogui` only works under **X11**, not Wayland. |

## Usage

1. Open Chrome and go to `chrome://dino`.
2. Run the script:

```bash
   python voice_dino.py
```

3. Stay quiet for 2 seconds while it calibrates.
4. During the 3-second countdown, **click inside the Chrome window** (the key press only reaches the focused window).
5. Say "hop", shout, or clap. The terminal bar shows the live volume, and `|` marks the threshold.
6. Stop with `Ctrl+C`.

### Options

| Option | Description | Default |
|---|---|---|
| `--threshold N` | RMS trigger threshold (lower = more sensitive) | `3000` |
| `--cooldown S` | Pause between jumps, in seconds | `0.4` |
| `--key {space,up}` | Simulated key | `space` |
| `--device N` | Microphone index | system default microphone |
| `--no-calibrate` | Skip calibration | calibration on |
| `--no-meter` | Hide the volume bar | bar on |
| `--list-devices` | List available microphones and exit | - |

Examples:

```bash
python voice_dino.py --list-devices
python voice_dino.py --no-calibrate --threshold 800
python voice_dino.py --device 1 --threshold 4000 --cooldown 0.35
```

### Simple version

`voice_dino_simplu.py` is a minimal variant (~60 lines, no classes, no numpy), good for understanding the basic idea. The threshold is changed directly in the code, in the `PRAG` variable.

```bash
python voice_dino_simplu.py
```

## Tuning the sensitivity

RMS values depend on the microphone and on your distance from it. Approximate values on the int16 scale:

| Situation | Typical RMS |
|---|---|
| Quiet room | 100 – 500 |
| Normal speech | 1,500 – 5,000 |
| Shouting, clapping | above 8,000 |

1. Run the script and watch the volume shown while you are quiet and while you say "hop".
2. Pick a threshold between the two values, at least 2 – 3 times above the background noise.
3. If the dino jumps on its own, raise the threshold. If it doesn't react to a quiet voice, lower it (e.g. `--no-calibrate --threshold 800`).

You can also raise the microphone's *Input volume* in your system settings, or use a microphone closer to your mouth.

## How the volume is computed (RMS)

For a block of `N` samples `x_i`:

$$RMS = \sqrt{\frac{1}{N}\sum_{i=0}^{N-1} x_i^2}$$

Example for the samples `1000, −2000, 3000, −4000`:

```
squares = 1,000,000 ; 4,000,000 ; 9,000,000 ; 16,000,000
sum     = 30,000,000
mean    = 30,000,000 / 4 = 7,500,000
RMS     = √7,500,000 ≈ 2,738.6
```

RMS is preferred over the peak value because it measures the average energy of the sound and does not react to a single isolated sample. A plain average cannot be used, because an audio signal oscillates around zero.

The **cooldown** is needed because a 0.3 s sound keeps the volume above the threshold for about `0.3 / 0.0232 ≈ 13` consecutive chunks, i.e. 13 Space presses without a pause.

## Project structure

```
voice-dino/
├── voice_dino.py          # full version (OOP, calibration, CLI options)
├── voice_dino_simplu.py   # minimal version
├── requirements.txt
└── README.md
```

In `voice_dino.py`:

| Component | Role |
|---|---|
| `Config` | Application settings, in one place |
| `VoiceDino` | Main class: opens the microphone, calibrates, runs the loop and triggers the jump |
| `compute_rms()` | Computes the volume of an audio block |
| `calibrate()` | Measures ambient noise and adjusts the threshold if it is too low |
| `run()` | Main loop, with `try / except KeyboardInterrupt / finally` |

## Troubleshooting

| Problem | Fix |
|---|---|
| Jumps on its own / too often | Raise the threshold: `--threshold 5000` |
| Doesn't react to your voice | Lower the threshold or move the microphone closer |
| Jumps twice for one sound | Raise the cooldown: `--cooldown 0.5` |
| Hears the sound but the dino doesn't jump | Chrome isn't focused: click inside the game window |
| `ModuleNotFoundError: pyaudio` | The virtual environment isn't active or pyaudio isn't installed |
| Error opening the microphone | Pick another one with `--list-devices` and `--device N` |
| Script stops when you move the mouse into a screen corner | That's the `pyautogui` fail-safe; just run it again |

## Limitations

- it can't tell a voice from any other loud noise;
- the threshold is fixed (apart from the calibration adjustment);
- the key press only reaches the active window;
- on Linux it only works with X11.

## Ideas for improvement

- adaptive threshold based on a moving average of the ambient noise;
- onset detection (reacting to sudden volume increases);
- high-pass / band-pass filter to favor claps over low-frequency noise;
- Down key for ducking, triggered by a second type of sound;
- graphical interface with a threshold slider.

## Author

**Fodoka David-Andrei** — [@mUstiuQ](https://github.com/mUstiuQ)

Student at the Faculty of Automation and Computer Science, Politehnica University of Timișoara.

## License

Distributed under the MIT License.
