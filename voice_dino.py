#!/usr/bin/env python3
"""
Flux de lucru:
    microfon -> pyaudio (chunk-uri int16) -> RMS -> comparație cu prag
             -> (verificare cooldown) -> pyautogui.press("space")


     Programul ascultă microfonul în blocuri de ~23 ms și calculează pentru fiecare bloc volumul (RMS). 
     Dacă volumul depășește un prag și au trecut cel puțin 0,4 s de la ultimul salt, apasă Space.
     Așa sare dinozaurul când fac zgomot
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pyaudio
import pyautogui

#rms = root mean square

 #configurare
@dataclass
class Config:
    """facem ca toate functiile de configurare sa fie aici ca sa le putem modifica fie din cod fie din comenzi"""
    """ o facem clasa separata ca toate valoriile care se pot schimba sa fie intr-un singur loc """

    #parametrii 
    chunk: int = 1024                  #cate esantioane se citesc la o interatie (un chunk: 1024/44100 = 23,2 ms)
    rate: int = 44100                  # frecvența de eșantionare standard (Hz) (Urechea aude până la ~20 kHz, iar conform teoremei Nyquist ai nevoie de minimum 2 × 20 kHz = 40 kHz, deci 44,1 kHz este suficient)
    channels: int = 1                  # mono ca e volum si nu ne trebe stereo
    device_index: Optional[int] = None # None = microfonul implicit al sistemului

    #detectie
    threshold: float = 3000.0          # prag RMS (scara int16: 0 .. ~32768) , aici se mai modifica in functie de microfon si zgomot, cel ok la mine e 1000
    cooldown: float = 0.4              # secunde între două salturi (debouncing)
    key: str = "space"                 # tasta simulată ("space" sau "up")

    #calibrare și afișare
    calibrate: bool = True             # măsoară zgomotul ambiental la start
    calibration_seconds: float = 2.0   # durata calibrării
    start_delay: int = 3               # secunde pentru a da focus pe fereastra Chrome
    show_meter: bool = True            # bară de volum live în terminal


#aplicatia 
class VoiceDino:
    """Citește microfonul și face dinozaurul să sară când volumul depășește pragul."""

    FORMAT = pyaudio.paInt16  # 16 biți cu semn -> valori între -32768 și 32767


    #Pregătește starea: setările, stream-ul (încă închis), momentul ultimului salt și contorul de salturi.
    def __init__(self, config: Config) -> None:
        self.cfg = config
        
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None 
        
        self._last_jump: float = 0.0   #cand sari ultima data
        self.jump_count: int = 0 #contorizeaza sariturile

        # pyautogui are implicit o pauză de 0.1 s după fiecare apel;
        # o anulăm ca să nu adăugăm latență inutilă între sunet și salt.
        pyautogui.PAUSE = 0

    #Deschide microfonul cu PyAudio (16 biți, 44100 Hz, mono, blocuri de 1024).
    def open(self) -> None:
        """Inițializează PyAudio și deschide stream-ul de intrare."""
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=self.FORMAT,
            channels=self.cfg.channels,
            rate=self.cfg.rate,
            input=True,
            input_device_index=self.cfg.device_index,
            frames_per_buffer=self.cfg.chunk,
        )

    #Oprește și închide stream-ul și eliberează PortAudio. Poate fi apelată de mai multe ori fără probleme.
    def close(self) -> None:
        """Este idempotentă și tolerantă la erori, deci poate fi apelată în siguranță
        din blocul `finally`, indiferent la ce pas a apărut problema.
        """
        if self._stream is not None:
            try:
                if self._stream.is_active():
                    self._stream.stop_stream()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    #Primește un bloc audio și returnează volumul lui (RMS).
    @staticmethod
    def compute_rms(data: bytes) -> float:
        """Calculează RMS = sqrt(mean(x^2)) pentru un chunk de bytes int16.

        Convertim în float64 înainte de ridicarea la pătrat, altfel int16
        ar da overflow (ex: 30000^2 nu încape în 16 biți).
        """
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float64)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples ** 2)))

    #Citește un bloc din microfon și îi calculează volumul. Așteaptă ~23 ms, deci ritmează bucla.
    def _read_rms(self) -> float:
        
        assert self._stream is not None, "Stream-ul nu este deschis"
        # exception_on_overflow=False: dacă bucla întârzie, nu aruncăm excepție,
        # ci pur și simplu pierdem câteva eșantioane vechi.
        data = self._stream.read(self.cfg.chunk, exception_on_overflow=False)
        return self.compute_rms(data)

    #Ascultă 2 s de liniște, măsoară zgomotul ambiental și ridică pragul dacă e prea mic pentru încăpere.
    def calibrate(self) -> None:
        n_chunks = max(1, int(self.cfg.rate / self.cfg.chunk * self.cfg.calibration_seconds))
        print(f"[Calibrare] Stai liniștit {self.cfg.calibration_seconds:.0f} s ...")

        levels = [self._read_rms() for _ in range(n_chunks)]
        mean_level = float(np.mean(levels))
        peak_level = float(np.max(levels))

        #pragul trebuie să fie clar peste zgomotul ambiental.
        suggested = max(peak_level * 2.0, mean_level * 4.0, 500.0)

        print(f"[Calibrare] Zgomot ambiental: medie={mean_level:.0f}, maxim={peak_level:.0f}")
        print(f"[Calibrare] Prag sugerat: {suggested:.0f} (prag curent: {self.cfg.threshold:.0f})")

        #Dacă pragul curent e sub nivelul ambiental, ar produce salturi false.
        if self.cfg.threshold <= peak_level * 1.2:
            print("[Calibrare] Pragul curent e prea mic pentru acest mediu -> îl ajustez.")
            self.cfg.threshold = suggested

    #Apasă tasta (Space), memorează momentul și crește contorul.
    def _jump(self, now: float) -> None:

        pyautogui.press(self.cfg.key)
        self._last_jump = now
        self.jump_count += 1

    #Spune dacă au trecut mai puțin de 0,4 s de la ultimul salt
    def _in_cooldown(self, now: float) -> bool:
        return (now - self._last_jump) < self.cfg.cooldown

    #Desenează bara de volum live în terminal, cu marcajul pragului.
    def _draw_meter(self, rms: float, jumped: bool) -> None:
        """Bară de volum într-o singură linie, actualizată cu \\r."""
        width = 40
        scale_max = self.cfg.threshold * 2.0           # pragul e la mijlocul barei
        filled = min(width, int(rms / scale_max * width))
        thr_pos = width // 2
        bar = ["#" if i < filled else "-" for i in range(width)]
        bar[thr_pos] = "|"                              # marcajul pragului
        status = "JUMP!" if jumped else "     "
        sys.stdout.write(
            f"\r[{''.join(bar)}] RMS={rms:7.0f}  prag={self.cfg.threshold:.0f}  "
            f"salturi={self.jump_count:3d}  {status}"
        )
        sys.stdout.flush()

    #Metoda principală: deschide microfonul, calibrează, face countdown și rulează bucla infinită. Oprește curat la Ctrl+C.
    def run(self) -> None:
        try:
            self.open()

            if self.cfg.calibrate:
                self.calibrate()

            # Timp pentru a trece cu focus-ul pe fereastra Chrome.
            for s in range(self.cfg.start_delay, 0, -1):
                print(f"[Start] Dă click în fereastra Chrome cu jocul Dino... {s}", end="\r")
                time.sleep(1)
            print(" " * 70, end="\r")
            print("[Start] Ascult! Fă zgomot pentru a sări. Ctrl+C pentru oprire.\n")

            while True:  # buclă infinită de captare audio
                rms = self._read_rms()
                now = time.monotonic()

                jumped = False
                if rms > self.cfg.threshold and not self._in_cooldown(now):
                    self._jump(now)
                    jumped = True

                if self.cfg.show_meter:
                    self._draw_meter(rms, jumped)

        except KeyboardInterrupt:
            print("\n\n[Oprire] Ctrl+C primit. Închid stream-ul audio...")
        except pyautogui.FailSafeException:
            # pyautogui oprește scriptul dacă mouse-ul e mutat într-un colț al ecranului.
            print("\n\n[Oprire] PyAutoGUI fail-safe activat (mouse în colțul ecranului).")
        finally:
            self.close()
            print(f"[Gata] Total salturi: {self.jump_count}. La revedere!")


#Afișează microfoanele disponibile și indexurile lor (pentru --device).
def list_input_devices() -> None:
    pa = pyaudio.PyAudio()
    try:
        print("Dispozitive de intrare audio:")
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                print(f"  [{i}] {info['name']}  (rate implicit: {int(info['defaultSampleRate'])} Hz)")
    finally:
        pa.terminate()

#Citește opțiunile din linia de comandă (--threshold, --cooldown etc.).
def parse_args() -> argparse.Namespace:
    d = Config()  # valorile implicite sunt preluate din Config
    p = argparse.ArgumentParser(description="Voice Dino - controlează Chrome Dino cu vocea.")
    p.add_argument("--threshold", type=float, default=d.threshold,
                   help=f"prag RMS de declanșare (implicit {d.threshold:.0f})")
    p.add_argument("--cooldown", type=float, default=d.cooldown,
                   help=f"secunde între salturi (implicit {d.cooldown})")
    p.add_argument("--key", choices=["space", "up"], default=d.key,
                   help="tasta simulată (implicit space)")
    p.add_argument("--device", type=int, default=None,
                   help="indexul microfonului (vezi --list-devices)")
    p.add_argument("--no-calibrate", action="store_true",
                   help="sare peste calibrarea zgomotului ambiental")
    p.add_argument("--no-meter", action="store_true",
                   help="ascunde bara de volum din terminal")
    p.add_argument("--list-devices", action="store_true",
                   help="listează microfoanele și iese")
    return p.parse_args()

#Construiește Config din opțiuni, creează VoiceDino și îl pornește.
def main() -> None:
    args = parse_args()

    if args.list_devices:
        list_input_devices()
        return

    config = Config(
        threshold=args.threshold,
        cooldown=args.cooldown,
        key=args.key,
        device_index=args.device,
        calibrate=not args.no_calibrate,
        show_meter=not args.no_meter,
    )
    VoiceDino(config).run()


if __name__ == "__main__":
    main()
