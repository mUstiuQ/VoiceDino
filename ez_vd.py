
import pyaudio
import pyautogui
import struct
import math
import time

#setarile principale
CHUNK = 1024              # cate esantioane citesc odata  (un chunk: 1024/44100 = 23,2 ms)
FORMAT = pyaudio.paInt16  # esantioane pe 16 biti
CHANNELS = 1              # mono pt ca e volum nu trebuoie stereo
RATE = 44100              # esantioane pe secunda
PRAG = 800               # peste valoarea asta sare dinozaurul (asta se schimba in functie de microfon si zgomot)
COOLDOWN = 0.4            # secunde de pauza intre doua salturi
pyautogui.PAUSE = 0       # fara pauza intre apasari


#caculam rms (radical din media patratelor)
def calculeaza_rms(date):
    
    numar = len(date) // 2 #esantionare pe 2 octeti
    esantioane = struct.unpack(str(numar) + "h", date) #facem octetii nr pe 16 biit
    #facem suma
    suma = 0
    for e in esantioane:
        suma = suma + e * e

    # radical din media patratelor
    return math.sqrt(suma / numar)

#loggica microfon 
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

print("Deschide jocul in Google Chrome")
print("TIPAAAAA.")
time.sleep(3)

ultimul_salt = 0

try:
    while True:
        date = stream.read(CHUNK, exception_on_overflow=False)
        volum = calculeaza_rms(date)

        #afisam volumul in timp real
        print("Volum:", int(volum), "      ", end="\r")

        acum = time.time()
        #am creat conditii ca daca volumul depaseste pragul si a trecut suficient timp de la ultimul salt,
        #  sa apese tasta space
        if volum > PRAG and acum - ultimul_salt > COOLDOWN:
            pyautogui.press("space")
            ultimul_salt = acum
            print("SARI BA! (volum =", int(volum), ")      ")

except KeyboardInterrupt:
    print("\nCeaaauuu.")


stream.stop_stream()
stream.close()
p.terminate()
