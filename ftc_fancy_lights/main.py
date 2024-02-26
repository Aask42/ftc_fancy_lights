'''

Written by: Amelia Wietting
Date: 20240124
For: FTC Team 19415
'''

from CONFIG.WIFI_CONFIG import COUNTRY, MAX_WIFI_CONNECT_TIMEOUT, WIFI_LIST
from CONFIG.MQTT_CONFIG import MQTT_USERNAME, MQTT_PASSWORD, MQTT_SERVER, MQTT_CLIENT_ID
from CONFIG.FTC_TEAM_CONFIG import TEAM_ASSIGNED
from CONFIG.CLOCK_CONFIG import NTP_SERVER, TIMEZONE_OFFSET, DAYLIGHT_SAVING
from CONFIG.LED_MANAGER import NUM_LEDS, LED_PIN, BRIGHTNESS, MAX_SOLID_BRIGHTNESS

import uasyncio
import time
import ntptime
import utime
import urequests
from machine import Pin, reset
import network
from umqtt.simple import MQTTClient
import sys
import json
#import plasma
import neopixel


# Audio reactive constants
BASS_COLOR = (255, 0, 0)  # Red for bass
TREBLE_COLOR = (0, 0, 255)  # Blue for treble

current_color = "AA0000"

UPDATE_INTERVAL_BLINKIES = 0.25  # refresh interval for blinkies in seconds


current_leds = [[0] * 3 for _ in range(NUM_LEDS)]
target_leds = [[0] * 3 for _ in range(NUM_LEDS)]

# Set up the Pico W's onboard LED and NeoPixel LEDs
pico_led = Pin('LED', Pin.OUT)
#led_strip = plasma.WS2812(NUM_LEDS, 0, 0, LED_PIN, color_order=plasma.COLOR_ORDER_GRB)
pin = machine.Pin(LED_PIN)
led_strip = neopixel.NeoPixel(pin, NUM_LEDS)


# Asynchronous tasks management
animation_task = None
quit_animation = False
solid_color_task = False

wifi_connected = False
mqtt_connected = False

# Set up the clock stuffs
SECOND_HAND_POS = 0  # Starting position of the second hand
MINUTE_HAND_POS = 0  # Starting position of the second hand
HOUR_HAND_POS = 0  # Starting position of the second hand

LAST_UPDATE = utime.time()  # Time of the last update
last_drawn_hand = 0

LEDS_PER_CIRCLE = NUM_LEDS//2

timezone_offset_sync = 0

if DAYLIGHT_SAVING:
    timezone_offset_mod = TIMEZONE_OFFSET + 1

def get_time():
    return utime.localtime()

async def set_time():
    global timezone_offset_sync
    ntptime.host = NTP_SERVER
    while True:
        try:
            cur_time = get_time()
            print("Local time before synchronization: %s" % str(get_time()))
            
            # Make sure to have internet connection
            ntptime.settime()
            new_time = get_time()
            if  new_time[6]-cur_time[6] > 1:
                #we got ahead, need to go back
                #adjust things to sync with the offset
                timezone_offset_sync = cur_time[6]-new_time[6]
            else:
                timezone_offset_sync = 0

            print("Local time after synchronization: %s" % str(get_time()))
        except Exception as e:
            print("Error syncing time:", e)
        await uasyncio.sleep(5)
ticked = False
tick_number = 0
def handle_time_message(msg):
    global SECOND_HAND_POS, LAST_UPDATE, MINUTE_HAND_POS, HOUR_HAND_POS, ticked, tick_number
    now = utime.time()

    try:
        # Print the received message for debugging
        #print("Received time message:", msg)

        tick_number_str, time_str = msg.split(',')
        tick_number = int(tick_number_str.strip())  # Convert tick_number to an integer
        time_parts = time_str.split(':')
        
        if len(time_parts) != 3:
            print("Unexpected time format:", time_str)
            return

        hours, minutes, seconds = [int(part.strip()) for part in time_parts]
        # Update minute hand position
        MINUTE_HAND_POS = int((minutes * LEDS_PER_CIRCLE // 60 + LEDS_PER_CIRCLE) % LEDS_PER_CIRCLE) 

        # Update hour hand position (approximation)
        HOUR_HAND_POS = int(((hours % 12) * LEDS_PER_CIRCLE // 12 + minutes // 12) % LEDS_PER_CIRCLE)
        
        #ticks = seconds * 2  
        SECOND_HAND_POS = int((seconds * LEDS_PER_CIRCLE // 60) % LEDS_PER_CIRCLE) #seconds % NUM_LEDS
        #SECOND_HAND_POS = int(SECOND_HAND_POS % LEDS_PER_CIRCLE + LEDS_PER_CIRCLE)
        if SECOND_HAND_POS < NUM_LEDS:
           SECOND_HAND_POS = int(SECOND_HAND_POS + LEDS_PER_CIRCLE)
        if MINUTE_HAND_POS < NUM_LEDS:
           MINUTE_HAND_POS = int(MINUTE_HAND_POS + LEDS_PER_CIRCLE)
        if HOUR_HAND_POS > LEDS_PER_CIRCLE:
           HOUR_HAND_POS = int(HOUR_HAND_POS - LEDS_PER_CIRCLE)

        LAST_UPDATE = utime.time()
        ticked = True
        print(f"Handled time message, {tick_number}, {SECOND_HAND_POS}")
        #print("Handled time message, MINUTE_HAND_POS:", MINUTE_HAND_POS)
        #print("Handled time message, HOUR_HAND_POS:", HOUR_HAND_POS)

    except Exception as e:
        print("Error in handle_time_message:", str(e))

pause_animation = False
lit_led = 1
pause_timeout = 0

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def normalize_color(r, g, b, max_value=MAX_SOLID_BRIGHTNESS):
    max_current = max(r, g, b)
    if max_current <= max_value:
        return r, g, b  # No need to normalize
    scale_factor = max_value / max_current
    return round(r * scale_factor), round(g * scale_factor), round(b * scale_factor)

def make_leds_color(color_hex="FF0000,4"):
    global current_color, pause_animation, pause_timeout
    
    data = color_hex.split(",")
    pause_animation = True
    pause_timeout = float(data[1])
    current_color = data[0]
    
    r, g, b = hex_to_rgb(current_color)  # Make sure to use 'current_color' here

    # Normalize the color if necessary
    # r, g, b = normalize_color(r, g, b)

    for i in range(NUM_LEDS):
        led_strip[i] = (r, g, b)
    led_strip.write()  # Update the strip with new colors



async def handle_audio_data(msg):
    global current_leds, target_leds
    global pause_animation, lit_led
    print(f"triggering audio_reactive {msg} ")
    pause_animation = True
    data = msg.split(",")
    bass_leds = int(data[0])
    treble_leds = int(data[1])
    is_beat = bool(data[2])
    is_same_beat = int(data[3])
    lit_led = 0
    print(f"{is_beat}")
    if is_beat:
        pause_animation = True
        make_leds_color("AA00FF")
        time.sleep(0.5 * is_same_beat);    
        pause_animation = False
        led_strip.set_rgb(lit_led, 255,255,255)
        lit_led += 1 
        lit_led = int(lit_led % NUM_LEDS/2 + NUM_LEDS/2)
        

   

# Set the range of pins we want
width_of_wifi_status_leds = 2
# Figure out where our center LED for the wifi indicator will be
wifi_led_center = NUM_LEDS/2 - NUM_LEDS/4 


wifi_status_cur_led = wifi_led_center
wifi_status_led_range = [wifi_led_center-width_of_wifi_status_leds, wifi_led_center+width_of_wifi_status_leds]

# Start by using the range from the middle of the wifi status indicator to the edge. It'll be 5 wide and pulse back and forth with no more than three on at a time.
# 
wifi_led_on = False

second_changed = False


# Helper function to convert HSV to RGB
def hsv_to_rgb(h, s, v):
    if s == 0.0: return (v, v, v)
    i = int(h * 6.)
    f = (h * 6.) - i
    p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
    i %= 6
    if i == 0: return (v, t, p)
    if i == 1: return (q, v, p)
    if i == 2: return (p, v, t)
    if i == 3: return (p, q, v)
    if i == 4: return (t, p, v)
    if i == 5: return (v, p, q)
def hue_offset(index, offset, divisor = 2):
    return (float(index) / (NUM_LEDS // divisor) + offset) % 1.0

async def set_leds(led_settings):
    global ticked
    """
    Set the LEDs based on a list of settings.
    Each setting in the list should be in the format [LED, H, S, V, SleepTime].
    """
    for setting in led_settings:
        led_index, hue, saturation, value, sleep_time = setting

        # Convert HSV to RGB
        r, g, b = hsv_to_rgb(hue, saturation, value)
        # Convert float RGB values (0 to 1 range) to integer RGB (0 to 255 range)
        r, g, b = int(r * 255), int(g * 255), int(b * 255)

        # Set the LED color
        led_strip[led_index] = (r, g, b)
        led_strip.write()

        await uasyncio.sleep(sleep_time)

        #if ticked:
            #print("Cancel this run!")
            #return False, led_settings  # Return the remaining settings

    return True, None
        
# Global variable for direction change
direction_change = False
loop_count = 0

def update_strip(position, length, cycle):
    # Turn off all LEDs
    for i in range(NUM_LEDS):
        led_strip[i] = (0, 0, 0)

    # Calculate the color based on the cycle value
    hue = cycle / MAX_COLOR_CYCLE
    color = hsv_to_rgb(hue, 1, 0.5)

    # Turn on LEDs in the specified segment
    for i in range(position, position + length):
        idx = (i + loop_count) % NUM_LEDS  # Loop around if index exceeds NUM_LEDS
        led_strip[idx] = color

    led_strip.write()

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
SEGMENT_LENGTH = NUM_LEDS // 2
MAX_COLOR_CYCLE = 144  # Maximum value for the color cycle
async def marquee_strip():
    global direction_change, loop_count, quit_animation, pause_animation, pause_timeout
    position = 0
    direction = 1
    cycle = 1

    while not quit_animation:
        if pause_animation:
            print(f"Pausing rainbows for {pause_timeout} seconds")
            await uasyncio.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False
        
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

previous_last_led = None
cycle_count = 0
async def marquee_strip_old():
    global quit_animation, pause_animation, pause_timeout, led_strip, wifi_connected, mqtt_connected, direction_anticlockwise, cycle_count
    global timezone_offset_sync, ticked, tick_number, second_changed, previous_last_led
    
    quit_animation = False
    hue = 0
    SPEED = 25 # This is how fast the rainbow rotates
    offset = 0.0
    cycle_count = 0
    
    led_sleep_time = NUM_LEDS/120/250

    SPEED = max(1, min(255, SPEED))

    # Initialize a list to track the state of each LED (True for on, False for off)
    led_states = [False] * NUM_LEDS
    
    second_width = NUM_LEDS // 120
    #await set_time()  # Synchronize time
    
    while not quit_animation:
        if pause_animation:
            print(f"Pausing rainbows for {pause_timeout} seconds")
            await uasyncio.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False
        

        current_time = get_time()
        current_second = current_time[5] 
        current_millisecond = current_time[6]  # Assuming this is the millisecond component
        
        # Check if the second has changed within a fudge factor of ±100 ms
        fudge_factor = 50  # 100 ms
        current_millisecond_adjusted = (current_millisecond + fudge_factor) % 1000
        if not second_changed:
            second_changed = current_millisecond_adjusted < (2 * fudge_factor)

        if second_changed:
            #print(f"Second changed (within fudge factor) {current_millisecond_adjusted}, stepping forward")
            ticked = False
            # Perform your stepping forward action here

            offset += float(SPEED) / 2000.0
            led_settings = [] 
            pins_to_skip = set()                
            # Toggle direction based on cycle_count 
            current_time = get_time()
            start = SECOND_HAND_POS

            #if previous_last_led is not None:
            #    start = previous_last_led
            #    previous_last_led = None
            if cycle_count % 2 == 0:
                print(f"Tick {tick_number}")
                for i in range(start, NUM_LEDS + start):
                    if i not in pins_to_skip:
                        hue = hue_offset(i, offset)
                        led = (i) % NUM_LEDS

                        if not led_states[led]:
                            led_settings.append([led, hue, 1.0, BRIGHTNESS, led_sleep_time])
                            led_states[led] = True

                    led_opposite = (led - NUM_LEDS // 2 + 5) % NUM_LEDS
                    if led_opposite not in pins_to_skip and led_states[led_opposite]:
                        led_settings.append([led_opposite, 0, 0, 0, led_sleep_time])
                        led_states[led_opposite] = False

            else:
                print(f"Tock {tick_number}")
                for i in range(NUM_LEDS + start, -1, -1):
                    if i not in pins_to_skip:
                        hue = hue_offset(i, offset)
                        led = (i) % NUM_LEDS

                        if not led_states[led]:
                            led_settings.append([led, hue, 1.0, BRIGHTNESS, led_sleep_time])
                            led_states[led] = True

                    led_opposite = (led - NUM_LEDS // 2) % NUM_LEDS
                    if led_opposite not in pins_to_skip and led_states[led_opposite]:
                        led_settings.append([led_opposite, 0, 0, 0, led_sleep_time])
                        led_states[led_opposite] = False 
            
                # Call set_leds and check the return value
            success, remaining_settings = await uasyncio.create_task(set_leds(led_settings))
            
            # If set_leds was interrupted, handle the remaining settings
            if not success:
                #cycle_count -= 1
                previous_last_led = remaining_settings[-1][0]
                #await uasyncio.create_task(set_leds(remaining_settings))
            else:
                previous_last_led = led_settings[-1][0]
           
            cycle_count += 1


# Function to create a rainbow effect
async def rainbows():
    SPEED = 15
    UPDATES = 100
    offset = 0.0
    quit_animation = False

    while not quit_animation:
        for i in range(NUM_LEDS):
            hue = (i / NUM_LEDS + offset) % 1.0
            r, g, b = hsv_to_rgb(hue, 1.0, BRIGHTNESS)
            led_strip[i] = (int(r * 255), int(g * 255), int(b * 255))

        led_strip.write()
        await uasyncio.sleep(1.0 / UPDATES)
        offset += float(SPEED) / 2000.0

# Function to alternate colors
async def alternating_blinkies():
    for _ in range(10):
        for i in range(NUM_LEDS):
            hue = 0.33 if i % 2 == 0 else 0.66  # Green and Blue
            r, g, b = hsv_to_rgb(hue, 1.0, BRIGHTNESS)
            led_strip[i] = (int(r * 255), int(g * 255), int(b * 255))

        led_strip.write()
        await uasyncio.sleep(0.5)

async def run_animation(animation_name, color=1):
    global quit_animation
    global animation_task

    if animation_task:
        quit_animation = True
        animation_task.cancel()
    if animation_name == "alternating_blinkies":
        animation_task = uasyncio.create_task(alternating_blinkies(color))
    elif animation_name == "rainbows":
        animation_task = uasyncio.create_task(rainbows())
    elif animation_name == "chase":
        animation_task = uasyncio.create_task(marquee_strip())
    await animation_task
    
def update_file_from_mqtt_message(msg_string):
    data = msg_string.split(",")
    filename=data[0]
    field=data[1]
    new_data=data[2]
    print(f"Starting update process for {filename}...")
    update_obj = UpdatePico()
    update_obj.update_file_from_mqtt_message(filename, [field,new_data])


def sub_cb(topic, msg):
    msg_string = msg.decode("UTF-8")
    #print(f"Received message: '{msg_string}' on topic: '{topic}'")  # Debugging output

    if topic == b'color_change':
        print("Changing LED color...")  # Debugging output
        make_leds_color(msg_string)
    elif topic == b'scores':
        print("Processing scores...")  # Debugging output
        data = msg_string.split(",")
        game_outcome = data[1]
        team = data[0]
        print(f"Team: {team}, Game Outcome: {game_outcome}")  # Debugging output
        if team == TEAM_ASSIGNED:
            print("Running alternating blinkies animation...")  # Debugging output
            uasyncio.create_task(run_animation("alternating_blinkies", "1" if game_outcome == "win" else "2"))
    elif topic == b'animate':
        print("Running custom animation...")  # Debugging output
        data = msg_string.split(",")
        animation_string = data[0]
        color_blinkies = data[1] if len(data) > 1 else None
        print(f"Animation: {animation_string}, Color: {color_blinkies}")  # Debugging output
        uasyncio.create_task(run_animation(animation_string, color_blinkies))
    elif topic == b'audio_reactive':
        uasyncio.create_task(handle_audio_data(msg_string))

    elif topic == b'time':
        handle_time_message(msg_string)
    elif topic == b'update':
        UpdatePico(msg_string)

async def mqtt_task(client):
    while True:
        try:
            client.check_msg()
            await uasyncio.sleep(0.1)
        except Exception as e:
            print(f"Errors checking messages: {e}")
            reset()

async def connect_to_wifi():
    global wifi_connected
    wifi_connected = False
    # TODO update this to look for all networks in the list WIFI_LIST=[["WhyFhy","WhyKnot42!"],["IoT","1234567890"]] and try to connect to the ones it finds
 
    # set up wifi
    connection_attempts=0
    try:
        status_handler("Scanning for your wifi network one sec")

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        nets = wlan.scan()
        for net in nets:
            print(f'Network seen: {net}')
            for network_config in WIFI_LIST:
                
                ssid_to_find = network_config[0]
                if ssid_to_find == net[0].decode('utf-8'):
                    print(f'Network found! {ssid_to_find}')
                    print(f"Attempting to connect to SSID: {ssid_to_find}")
                    wlan.connect(ssid_to_find, network_config[1])
                    while not wlan.isconnected():
                        await status_handler(f"Waiting to connect to the network: {ssid_to_find}...")
                        connection_attempts += 1
                        await uasyncio.sleep(1)
                        
                        if connection_attempts > MAX_WIFI_CONNECT_TIMEOUT:
                            print("Exceeded MAX_WIFI_CONNECT_TIMEOUT!!!")
                            break
                            
                    wifi_connected = True
                    print('WLAN connection succeeded!')
                    break
                else:
                     print(f"Unable to find SSID: {ssid_to_find}")
            if wifi_connected:
                break
               
    except Exception as e:
        print(f"Setup failed: {e}")

# Status handler function
row_one = False
async def status_handler(message):
    global wifi_connected, row_one
    print(message)

    if row_one:
        print(f"Row one")
        for i in range(NUM_LEDS//2):
            led_strip[i] = (0, 0, 0)
            await uasyncio.sleep(NUM_LEDS // 2 * 0.0005)
    else:
        print(f"Row Two!!")
        for i in range(NUM_LEDS//2, NUM_LEDS):
            led_strip[i] = (0, 0, 0)
            await uasyncio.sleep(NUM_LEDS // 2 * 0.0005)
    
    led_strip.write()
    row_one = not row_one

    if row_one:
        for i in range(NUM_LEDS//2):
            make_leds_color("008800")
            await uasyncio.sleep(NUM_LEDS//2 * 0.001)
    else:
        for i in range(NUM_LEDS//2, NUM_LEDS):
            led_strip[i] = (100, 100, 100)
            await uasyncio.sleep(NUM_LEDS//2 * 0.001)

    led_strip.write()

    
def connectMQTT():
    global mqtt_connected
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_SERVER,
        port=0,
        user=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        keepalive=0,
        ssl=True,
        ssl_params={'server_hostname':'b0d11619bad64381af076f147cf1cb7c.s1.eu.hivemq.cloud'}
    )
    client.set_callback(sub_cb)

    try:
        client.connect()
        mqtt_connected = True
    except Exception as e:
        print('Error connecting to %s MQTT broker error: %s' % (MQTT_SERVER, e))

    topics = [b'time',b'color_change', b'scores', b'animate', b'audio_reactive', b'chase', b'update']

    for topic in topics:
        try:
            client.subscribe(topic)
            print('Connected to {} MQTT broker, subscribed to {} topic'.format(MQTT_SERVER, topic.decode()))
        except Exception as e:
            print('Error subscribing to %s topic! Error: %s' % (topic.decode(), e))

    return client

def setup():
    global wifi_connected
    # set up wifi
    try:
        uasyncio.get_event_loop().run_until_complete(connect_to_wifi())

        if wifi_connected:
            print('Wifi connection successful!')
            wifi_status = "connected"
            for _ in range(2):  # Flash red three times
                make_leds_color(color_hex="008800,0.75")
                time.sleep(0.5)
                make_leds_color(color_hex="000000,0.75")
                time.sleep(0.5)
            make_leds_color(color_hex="880088,0.75")
        else:
            print(f'Wifi connection failed!')
            wifi_status = "failed"
            for _ in range(4):  # Flash red three times
                make_leds_color(color_hex="990000,0.5")
                time.sleep(.5)
                make_leds_color(color_hex="000000,0.5")
                time.sleep(0.5)
                
                
    except Exception as e:
        print(f'Wifi connection failed! {e}')
        wifi_status = "failed"
        wifi_connected = False
        for _ in range(4):  # Flash red three times
            make_leds_color(color_hex="990000,0.5")
            time.sleep(.5)
            make_leds_color(color_hex="000000,0.5")
            time.sleep(0.5)
        
        # if no wifi, then you get...

    if wifi_connected:
        try:
            print("Attempting to connect to MQTT broker...")
            client = connectMQTT()
            #make_leds_color(color_hex="005500,2")
            return client

        except Exception as e:
            print("Failed to connect to MQTT: %s" % e)
            #make_leds_color(color_hex="FF0000,2")
            
async def main():
    client = setup()
    uasyncio.create_task(run_animation("chase"))

    if wifi_connected:
        uasyncio.create_task(mqtt_task(client))
        uasyncio.create_task(set_time())

    while True:
        await uasyncio.sleep(0)  # Main loop sleep, to keep the loop alive

uasyncio.run(main()) 
    
    



