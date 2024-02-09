import plasma
from plasma import plasma_stick
import time


"""
This is code written by Amelia Wietting for team 19415 C3 Robotics
"""

# Set how many LEDs you have
NUM_LEDS = 86
current_led = 1

# Pick two hues from the colour wheel (from 0-360°, try https://www.cssscript.com/demo/hsv-hsl-color-wheel-picker-reinvented/ )
HUE_1 = 175
HUE_2 = 220
# Set up brightness (between 0 and 1)
BRIGHTNESS = 1

# Set up speed (wait time between colour changes, in milliseconds)
speed = 100

direction = False

# WS2812 / NeoPixel™ LEDs
led_strip = plasma.WS2812(NUM_LEDS, 0, 0, plasma_stick.DAT, color_order=plasma.COLOR_ORDER_RGB)

# Start updating the LED strip
led_strip.start()

led_data = {}

for i in range(NUM_LEDS):
    led_data[i] = {
        "color":190,
        "brightness":0
        }

def fade_surrounding_brightness(center_led, center_led_brightness):
    # Drop the brightness of the surrounding LEDS

    led_data[center_led]['brightness'] = center_led_brightness
    width = 10
    for i in range(1,width):
        target_led_lower = center_led - i
        
        target_led_high = center_led + i
        
        operator = 1
        if direction:
            operator = -1
        
        if target_led_high in led_data:
            led_data[target_led_high]['brightness'] = led_data[center_led]['brightness'] - (1/width * i)
        if target_led_high + 1 in led_data:
            led_data[target_led_high]['color'] = led_data[target_led_high - operator]['color'] - (5 * i * operator)
        
        if target_led_lower in led_data:
            led_data[target_led_lower]['brightness'] = led_data[center_led]['brightness'] - (1/width * i)
        if target_led_lower - 1 in led_data:
            led_data[target_led_lower]['color'] = led_data[target_led_lower - operator]['color'] - (5 * i * operator)






def light_leds():
    for led in range(NUM_LEDS):
        led_strip.set_hsv(led, led_data[led]['color'] / 360, 1.0, led_data[led]['brightness'])

while True:

    if direction:
        current_led += 1
        speed -= 2
    else:
        current_led -= 1
        speed += 2
    
    fade_surrounding_brightness(current_led, 0.5)
    light_leds()
    
    
    if current_led == NUM_LEDS - 1:
        direction = False
    if current_led == 0:
        direction = True

            
    time.sleep(speed / 1000)

