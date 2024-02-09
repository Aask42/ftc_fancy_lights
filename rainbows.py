import plasma
from plasma import plasma_stick
import time

"""
Make some rainbows!
"""

# Set how many LEDs you have
NUM_LEDS = 144


# How many times the LEDs will be updated per second
UPDATES = 100

# WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, 0, 0, 28, color_order=plasma.COLOR_ORDER_RGB)

# Start updating the LED strip
led_strip.start()

SPEED = 3

offset = 0.0


while True:
    SPEED = min(255, max(1, SPEED))
    offset += float(SPEED) / 500.0

    for i in range(NUM_LEDS // 2):
        hue = float(i) / (NUM_LEDS // 2)  # Calculate hue based on half the number of LEDs
        led_strip.set_hsv(i, hue + offset, 1.0, 0.75)
        led_strip.set_hsv(i + (NUM_LEDS // 2), hue + offset, 1.0, 0.75)  # Mirror the color on the second half





