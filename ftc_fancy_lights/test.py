import machine, neopixel
import uasyncio

# Constants
NUM_LEDS = 144  # Change this to the number of LEDs in your strip
SEGMENT_LENGTH = NUM_LEDS // 2
MAX_COLOR_CYCLE = 144  # Maximum value for the color cycle

# Setup the LED strip
pin = machine.Pin(28)  # Change the pin number to the one you're using
strip = neopixel.NeoPixel(pin, NUM_LEDS)

# Global variable for direction change
direction_change = False
loop_count = 0

def update_strip(position, length, cycle):
    # Turn off all LEDs
    for i in range(NUM_LEDS):
        strip[i] = (0, 0, 0)

    # Calculate the color based on the cycle value
    hue = cycle / MAX_COLOR_CYCLE
    color = hsv_to_rgb(hue, 1, 0.5)

    # Turn on LEDs in the specified segment
    for i in range(position, position + length):
        idx = (i + loop_count) % NUM_LEDS  # Loop around if index exceeds NUM_LEDS
        strip[idx] = color

    strip.write()

def hsv_to_rgb(h, s, v):
    if s == 0.0: return (v, v, v)
    i = int(h*6.)
    f = (h*6.)-i
    p,q,t = int(255*(v*(1.-s))), int(255*(v*(1.-s*f))), int(255*(v*(1.-s*(1.-f))))
    v = int(255*v)
    i %= 6
    if i == 0: return (v, t, p)
    if i == 1: return (q, v, p)
    if i == 2: return (p, v, t)
    if i == 3: return (p, q, v)
    if i == 4: return (t, p, v)
    if i == 5: return (v, p, q)

# Interrupt handler function
def toggle_direction(timer):
    global direction_change
    direction_change = not direction_change

# Setup timer interrupt
timer = machine.Timer(-1)
timer.init(period=1000, mode=machine.Timer.PERIODIC, callback=toggle_direction)

async def clock_hand_animation():
    global direction_change, loop_count
    position = 0
    direction = 1
    cycle = 1

    while True:
        update_strip(position, SEGMENT_LENGTH, cycle)

        # Update the position and cycle
        position += direction
        cycle += 1
        if cycle > MAX_COLOR_CYCLE:
            cycle = 1

        # Check for direction change
        if direction_change:
            direction *= -1
            direction_change = False
            loop_count += NUM_LEDS // 120

        await uasyncio.sleep(0.01)  # Non-blocking sleep

# Start the animation
uasyncio.run(clock_hand_animation())
