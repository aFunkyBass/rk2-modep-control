#!/usr/bin/python3
import sys, signal
import time
import rtmidi
import evdev
import subprocess
import board
import neopixel


#
## Definizione dei 7 controlli a pulsante
## Stato, N. CC, Valore off, Valore on
#
aFootControls = [
      [ # STATE_BANK_0
        [False, 20, 0, 127],
        [False, 21, 0, 127],
        [False, 22, 0, 127],
        [False, 23, 0, 127],
        [False, 24, 0, 127],
        [False, 25, 0, 127],
        [False, 26, 0, 127]
      ],
      [ # STATE_BANK_0
        [False, 102, 0, 127],
        [False, 103, 0, 127],
        [False, 104, 0, 127],
        [False, 105, 0, 127],
        [False, 106, 0, 127],
        [False, 107, 0, 127],
        [False, 26, 0, 127]
      ]
    ]

#
## Definizione dei 3 controlli a pedale
## CC, Valore minimo ingresso, Valore massimo in ingresso, valore minimo rimappato, valore massimo rimappato
#
aVariableControls = [
        [27, 190, 1500, 0, 127],
        [28, 190, 1600, 0, 127],
        [29, 190, 1600, 0, 127]]

BTN_HOLD_TIMEOUT  = 1000
SWITCH_PRESET_TIMEOUT = 10000

STATE_BANK_0    = 0
STATE_BANK_1    = 1
STATE_SWITCH_PRESET  = 2

KEY_SWITCH_BANK    = 2  # Pedale da tenere premuto per il cambio banco
KEY_SWITCH_PRESET = 1  # Pedale da tenere premuto per il cambio preset

nCurState = STATE_BANK_0
nOldState = STATE_BANK_0

tStartPressed = 0
tStartSwitchPreset = 0
nBtnHold = -1

nCurPedalboard = 0

bAllowKeyUp = True

# Pin di collegamento dei LED
pixel_pin = board.D18

# Numero di LED
num_pixels = 6
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(pixel_pin, num_pixels, brightness=1, auto_write=False, pixel_order=ORDER)

aColors = [
            [(0, 0, 25), (200, 0, 0)],
            [(0, 25, 0), (200, 0, 0)],
            [(25, 25, 25), (200, 0, 0)]
          ]

# Funione di rimappatura del valore letto dal controller ai valori MIDI
def remap(val, from_min, from_max, to_min, to_max):
  nNewVal = (to_max - to_min)*(val - from_min) / (from_max - from_min) + to_min
  if nNewVal < to_min:
    nNewVal = to_min

  if nNewVal > to_max:
    nNewVal = to_max

  return(nNewVal)

def SendKeyEvent(nButton):
  global midiout, aMessage, aFootControls, nCurState, STATE_BANK_0, STATE_BANK_1

  # Assegna al messaggio il numero di CC MIDI associato al bottone
  aMessage[1] = aFootControls[nCurState][nButton][1]

  # inverte lo stato del bottone
  aFootControls[nCurState][nButton][0] = not aFootControls[nCurState][nButton][0]

  # Prepara il valore da inviate
  if aFootControls[nCurState][nButton][0]:
    aMessage[2] = aFootControls[nCurState][nButton][3]
  else:
    aMessage[2] = aFootControls[nCurState][nButton][2]

  # Invio del messaggio MIDI
  midiout.send_message(aMessage)
  UpdateLeds()
  

def ResetValues():
  for i in range(len(aFootControls)):
    for j in range(len(aFootControls[i])):
      aFootControls[i][j][0] = False
  
def SwitchPedalBoard(nButton):
  global nCurPedalboard
  
  nCurPedalboard = nButton
#  print("Cambio pedaliera: " + str(nButton))
  ResetValues()
  UpdateLeds()
  subprocess.call(['/usr/modep/scripts/modep-ctrl.py', 'index',  str(nButton)], shell=False)
  

def millis():
  return(int(round(time.time() * 1000)))

def Btn2Led(n):
  if n <= 2:
    nRet = n
  else:
    nRet = (num_pixels - n) + 2
 
  return(nRet)
  

def UpdateLeds():
  if nCurState != STATE_SWITCH_PRESET:
    for i in range(0, num_pixels):
      nLedState = int(aFootControls[nCurState][i][0])
      pixels[Btn2Led(i)] = aColors[nCurState][nLedState]
  else:
    for i in range(0, num_pixels):
      nLedState = (i == nCurPedalboard)
      pixels[Btn2Led(i)] = aColors[nCurState][nLedState]

  pixels.show()
  return

def signal_handler(signal, frame):
    global pixels, midiout, device
    
    print("\nprogram exiting gracefully")
    del midiout
    pixels.deinit()
    del pixels
    del device

    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

#print(evdev.util.list_devices())

device = evdev.InputDevice('/dev/input/event0')

#print(device)

# Apre la porta Midi
midiout = rtmidi.MidiOut()
available_ports = midiout.get_ports()

if available_ports:
    midiout.open_port(0)
else:
    midiout.open_virtual_port("GuidoPort")

UpdateLeds()

event = None

with midiout:
    aMessage = [0xB0, 0, 0] # Canale 1
    try:
      while True:
        #Controlla se siamo in stato di cambio banco
        if nCurState == STATE_SWITCH_PRESET and tStartSwitchPreset > 0 and millis() - tStartSwitchPreset > SWITCH_PRESET_TIMEOUT:  
          nCurState = nOldState
          tStartSwitchPreset = 0
          UpdateLeds()
#          print("Stato normale")
          
        
        # Controlla se c'e' un pulsante in HOLD cambia lo stato della pedaliera
        if tStartPressed > 0 and millis() - tStartPressed > BTN_HOLD_TIMEOUT:
          # Controlla lo stato attuale
          if nCurState == STATE_BANK_0 or nCurState == STATE_BANK_1:  
            if nBtnHold == KEY_SWITCH_BANK:      # Se e' stato premuto il bottone per il cambio banco
              nCurState = (nCurState + 1) % 2
              UpdateLeds()
            elif nBtnHold == KEY_SWITCH_PRESET:  # Se e' stato premuto il bottone per il cambio preset
              tStartSwitchPreset = millis()
              nOldState = nCurState
              nCurState = STATE_SWITCH_PRESET
              UpdateLeds()
#              print("Stato switch preset")
            
          bAllowKeyUp = False
          tStartPressed = 0
          nBtnHold = -1

        # legge se e presente un evento (tastiera o joystick)
        event = device.read_one()
        if event != None:
          # Premuto un bottone sulla pedaliera
          if event.type == evdev.ecodes.EV_KEY:

            # Acquisisce il numero del bottone
            nButton = int(event.code) - 2

            # Controlla che il bottone sia nel range dei 7 bottoni della pedaliera
            if nButton < 0 or nButton > 6:
              continue

            # KEY DOWN
            if int(event.value) == 1:

              if nCurState == STATE_SWITCH_PRESET:
                tStartSwitchPreset = millis()
                SwitchPedalBoard(nButton)
                continue

              if nButton == KEY_SWITCH_BANK or nButton == KEY_SWITCH_PRESET:
                tStartPressed = millis()
                nBtnHold = nButton
              else:
                SendKeyEvent(nButton)

              continue

            # KEY UP Se stato rilasciato il bottone
            if int(event.value) == 0:
              if bAllowKeyUp == False:
                bAllowKeyUp = True
                continue 

              if nButton != KEY_SWITCH_BANK and nButton != KEY_SWITCH_PRESET:
                continue

              if millis() - tStartPressed < BTN_HOLD_TIMEOUT:
                tStartPressed = 0
                SendKeyEvent(nButton)

          elif event.type == evdev.ecodes.EV_ABS:
              absevent = evdev.categorize(event)

              if absevent.event.code > len(aVariableControls):
                continue

              if nCurState == STATE_SWITCH_PRESET:
                continue

              # Rimappa il valore MIDI
              nNewVal = remap(absevent.event.value, aVariableControls[absevent.event.code][1], aVariableControls[absevent.event.code][2],
                              aVariableControls[absevent.event.code][3], aVariableControls[absevent.event.code][4]);

              if absevent.event.code < 0 or absevent.event.code > 2:
                continue

              # Assegna al messaggio il numero di CC MIDI associato al bottone
              aMessage[1] = aVariableControls[absevent.event.code][0]
              aMessage[2] = nNewVal

              # Invio del messaggio MIDI
              midiout.send_message(aMessage)

        time.sleep(0.002)

    except (EOFError, KeyboardInterrupt):
      print('Fine')



