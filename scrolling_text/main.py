'''

Written by: Tim Brom and Amelia Wietting
Date: 20240124
For: FTC Team 19415
This update was pushed OTA. Do not change it unless you know what you are doing
'''

from CONFIG.LED_MANAGER import NUM_LEDS, LED_PIN, BRIGHTNESS, STARTING_ANIMATION
import micropython
import uasyncio
import time
import ntptime
import utime
import urequests
from machine import Pin, reset
import network
import sys
import neopixel
import machine
import gc
import espnow
import random

# from micropyGPS.micropyGPS import MicropyGPS
from machine import Pin, UART

# Set up our neopixel LED strip
np = neopixel.NeoPixel(Pin(LED_PIN), 64)

# Create random color array
COLORS = []
for i in range(0, 255):
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)

    if (r + g + b < 50):
        continue
    COLORS.append((r, g, b))
    
# Trans rainbow. Set the COLORS array to the colors you want to display and
# they will be cycles through in order
COLORS = [(91, 206, 250),
          (245, 169, 184),
          (255, 255, 255),
          (245, 169, 184),
          (91, 206, 250)]

# Alphabet
# TODO: Add other letters and symbols
letters = {
    "A": ([0, 3, 12, 15, 16, 17, 18, 19, 28, 31, 33, 34], 4),
    "B": ([0, 1, 2, 12, 15, 16, 17, 18, 19, 28, 31, 32, 33, 34], 4),
    "C": ([1, 2, 3, 15, 16, 31, 33, 34, 35], 4),
    "D": ([0, 1, 2, 12, 15, 16, 19, 28, 31, 32, 33, 34], 4),
    "E": ([0, 1, 2, 3, 15, 16, 17, 18, 19, 31, 32, 33, 34, 35], 4),
    "F": ([0, 15, 16, 17, 18, 19, 31, 32, 33, 34, 35], 4),
    "G": ([1, 2, 12, 15, 16, 18, 19, 31, 33, 34], 4),
    "H": ([0, 3, 12, 15, 16, 17, 18, 19, 28, 31, 32, 35], 4),
    "I": ([0, 1, 2, 14, 17, 30, 32, 33, 34], 3),
    "J": ([1, 13, 15, 18, 29, 33, 34, 35], 4),
    "K": ([0, 3, 13, 15, 16, 17, 29, 31, 32, 35], 4),
    "L": ([0, 1, 2, 3, 15, 16, 31, 32], 4),
    "M": ([0, 4, 11, 13, 15, 16, 18, 20, 27, 28, 30, 31, 32, 36], 5),
    "N": ([0, 3, 12, 15, 16, 18, 19, 28, 30, 31, 32, 35], 4),
    "O": ([1, 2, 3, 11, 15, 16, 20, 27, 31, 33, 34, 35], 5),
    "P": ([0, 15, 16, 17, 18, 28, 31, 32, 33, 34], 4),
    "Q": ([1, 2, 4, 12, 15, 16, 20, 27, 31, 33, 34, 35], 5),
    "R": ([0, 3, 13, 15, 16, 17, 18, 28, 31, 32, 33, 34], 4),
    "S": ([0, 1, 2, 12, 17, 18, 31, 33, 34, 35], 4),
    "T": ([2, 13, 18, 29, 32, 33, 34, 35, 36], 5),
    "U": ([1, 2, 12, 15, 16, 19, 28, 31, 32, 35], 4),
    "V": ([2, 12, 14, 17, 19, 27, 31, 32, 36], 5),
    "W": ([1, 3, 11, 13, 15, 16, 18, 20, 27, 29, 31, 32, 34, 36], 5),
    "X": ([0, 4, 12, 14, 18, 28, 30, 32, 36], 5),
    "Y": ([1, 14, 17, 29, 31, 32, 34], 3),
    "Z": ([0, 1, 2, 3, 15, 17, 29, 32, 33, 34, 35], 4),
    " ": ([18], 4)
}

def draw_letter(letter, pos, np, color):
    """
    Draw letter offset horizontally by <pos> on the NeoPixel
    """
    for point in letter:
        if (point >= 0 and point <= 4):
            point += pos
            if point > 7 or point < 0:
                continue
        elif (point >= 11 and point <= 15):
            point -= pos
            if point < 8 or point > 15:
                continue
        elif (point >= 16 and point <= 20):
            point += pos
            if point > 23 or point < 16:
                continue
        elif (point >= 27 and point <= 31):
            point -= pos
            if point < 24 or point > 31:
                continue
        elif (point >= 32 and point <= 36):
            point += pos
            if point > 39 or point < 32:
                continue
        np[point] = color


def scroll_text(text, np, speed=10, color=None):
    """
    Do the scrolling
    
    Pop letters off the string and move them across the screen till they're
    off the left side.
    
    Randomly color each letter if no color is given.
    """
    text = list(text)
    screen = []  # Letters on the screen
    color_count = 0
    while text or screen:
        if screen:
            if (screen[0]['pos'] + screen[0]['data'][1]) <= 0:
                # letter falls off left side
                screen.pop(0)
            if text and ((screen[-1]['pos'] + screen[-1]['data'][1]) < 9):
                # rightmost letter is all the way on the screen,
                # add another letter if any are left
                screen.append({'data': letters[text.pop(0)], 
                               'pos': 9, 
                               'color': color or COLORS[color_count]})# random.choice(COLORS)})
                color_count += 1
        else:  # nothing on the screen yet
            screen.append({'data': letters[text.pop(0)], 
                           'pos': 9, 
                           'color': color or COLORS[color_count]})# random.choice(COLORS)})
            color_count += 1
        for letter in screen:  # draw the screen
            draw_letter(letter['data'][0], letter['pos'], np, letter['color'])
            letter['pos'] -= 1  # scroll to the left
        np.write() 
        np.fill([0,0,0])
        time.sleep(.2/speed)
        if (color_count >= len(COLORS)):
            color_count = 0


text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
text = "WEVE BEEN TRYING TO REACH YOU ABOUT YOUR TRACTORS EXTENDED WARRANTY"
while True:
    scroll_text(text, np, speed=3)
 
