'''

Written by: Amelia Wietting
Date: 20240124
For: FTC Team 19415
This update was pushed OTA. Do not change it unless you know what you are doing
'''

from CONFIG.WIFI_CONFIG import COUNTRY, MAX_WIFI_CONNECT_TIMEOUT, WIFI_LIST
from CONFIG.MQTT_CONFIG import MQTT_USERNAME, MQTT_PASSWORD, MQTT_SERVER, MQTT_CLIENT_ID
from CONFIG.FTC_TEAM_CONFIG import TEAM_ASSIGNED
from CONFIG.CLOCK_CONFIG import NTP_SERVER, TIMEZONE_OFFSET, DAYLIGHT_SAVING
from CONFIG.LED_MANAGER import NUM_LEDS, LED_PIN, BRIGHTNESS, STARTING_ANIMATION
from CONFIG.OTA_CONFIG import OTA_HOST, PROJECT_NAME, FILENAMES

from updates import update_file_replace
from helper import hsv_to_rgb
import micropython
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
import neopixel
import uos
import machine
import gc
from micropyGPS.micropyGPS import MicropyGPS
from machine import Pin, UART


#led = Pin(25, Pin.OUT)

GPS_SCAN_TIMEOUT_SECONDS = 5

# TODO: Old vaieable, should clean this up
current_color = "AA0000"

# TODO: Make it more clear what this does
UPDATE_INTERVAL_BLINKIES = 0.0001  # refresh interval for blinkies in seconds


current_leds = [[0] * 3 for _ in range(NUM_LEDS)]
target_leds = [[0] * 3 for _ in range(NUM_LEDS)]

# Set up our neopixel LED strip
led_strip = neopixel.NeoPixel(Pin(LED_PIN), NUM_LEDS)


# Asynchronous tasks management
animation_task = None
quit_animation = False

wifi_connected = False
mqtt_connected = False

STANDALONE_MODE = False

# Set up the clock stuffs
SECOND_HAND_POS = 0  # Starting position of the second hand
MINUTE_HAND_POS = 0  # Starting position of the second hand
HOUR_HAND_POS = 0  # Starting position of the second hand

LAST_UPDATE = utime.time()  # Time of the last update
last_drawn_hand = 0

LEDS_PER_CIRCLE = NUM_LEDS//2

timezone_offset_sync = 0
network_list = None

if DAYLIGHT_SAVING:
    timezone_offset_mod = TIMEZONE_OFFSET + 1

        
gps_loc = []

GPS_SCAN_TIMEOUT_SECONDS = 5
WIFI_SCAN_TIMEOUT_SECONDS = 10
segment_len = NUM_LEDS//3 * 2
network_list = None

async def wifi_scan():
    global network_list, segment_len
    
    while True:
        networks = wlan.scan()
        if networks is not None:
            #print(f"GPS: {gps_string}")
            #if gps_string is None:
            #gps_string = "None"
            print("WiFi Network Count:", len(networks))
            if not network_list:
                network_list = []
            segment_len = len(networks)
            for network in networks:
                if network not in network_list:
                    network_list.append(network)
                #ssid = network[0]
                #print("WiFi Network:", ssid)
                #print(f"Network obj: {network}")
                #network_string = str(network)
                
        await uasyncio.sleep(WIFI_SCAN_TIMEOUT_SECONDS)

# Setup timer interrupt
#wifi_scan_timer = machine.Timer(-1)
#wifi_scan_timer.init(period=10000, mode=machine.Timer.PERIODIC, callback=wifi_scan)

def convert_coordinates(sections):
    if sections[0] == 0:  # sections[0] contains the degrees
        return None

    # sections[1] contains the minutes
    data = sections[0] + (sections[1] / 60.0)

    # sections[2] contains 'E', 'W', 'N', 'S'
    if sections[2] == 'S':
        data = -data
    if sections[2] == 'W':
        data = -data

    data = '{0:.6f}'.format(data)  # 6 decimal places
    return str(data)

## GPS scan task
async def gps_scan():
    global gps_loc
    gps_module = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
    time_zone = -3
    gps = MicropyGPS(time_zone)

    while True:
        
        #print("Checking for GPS updates")
        length = gps_module.any()
        if length > 0:
            data = gps_module.read()
            gps_loc.append(f"{data}\n")
            print(data)
            for byte in data:
                message = gps.update(chr(byte))

            latitude = convert_coordinates(gps.latitude)
            longitude = convert_coordinates(gps.longitude)

            if latitude is None or longitude is None:
                continue
            print('Lat: ' + latitude)
            print('Lon: ' + longitude)            
            
        await uasyncio.sleep(GPS_SCAN_TIMEOUT_SECONDS)

# TODO: Explain better batching up our MQTT messages to be shipped off for power saving. See if we can save a local file to pick up on restart
async def publish_list_of_mqtt_messages():
    global network_list, gps_loc
    while True:
        if network_list is not None:
            for network in network_list:
                publish_to_mqtt("wifi_data",f"{network},{MQTT_CLIENT_ID}")
                
            network_list = None
        if gps_loc is not None:
            for message in gps_loc:
                message_str = str(message)
                publish_to_mqtt("gps_data",f"{message_str},{MQTT_CLIENT_ID}")
            gps_loc = []
        await uasyncio.sleep(10)
        
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
        await uasyncio.sleep(3600)

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
        #print(f"Handled time message, {tick_number}, {SECOND_HAND_POS}")
        #print(f"Handled time message, {tick_number}, {SECOND_HAND_POS}")

        #print(f"Buzzing haptics!")
        
        #drv2605.set_realtime_input(255)
        #await uasyncio.sleep(0.01)
        #drv2605.set_realtime_input(0)
        #print("Handled time message, MINUTE_HAND_POS:", MINUTE_HAND_POS)
        #print("Handled time message, HOUR_HAND_POS:", HOUR_HAND_POS)

    except Exception as e:
        print("Error in handle_time_message:", str(e))

async def handle_ticking():
    global SECOND_HAND_POS, LAST_UPDATE, MINUTE_HAND_POS, HOUR_HAND_POS, ticked, tick_number
    now = utime.time()
    while True:
    
        # Print the received message for debugging
        #print("Received time message:", msg)

        #tick_number_str, time_str = msg.split(',')
        #tick_number = int(tick_number_str.strip())  # Convert tick_number to an integer
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
        await uasyncio.sleep_ms(1000)


# TODO: Move these to a better place
pause_animation = False
pause_timeout = 0

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def normalize_color(r, g, b, max_value=BRIGHTNESS):
    max_current = max(r, g, b)
    if max_current <= max_value:
        return r, g, b  # No need to normalize
    scale_factor = max_value / max_current
    return round(r * scale_factor), round(g * scale_factor), round(b * scale_factor)

def make_leds_color(color_hex="770000,4"):
    global current_color, pause_animation, pause_timeout
    
    data = color_hex.split(",")
    pause_animation = True
    pause_timeout = float(data[1])
    current_color = data[0]
    
    r, g, b = hex_to_rgb(current_color)  
   
    #print(f"make_leds_color {r},{g},{b}")

    for i in range(NUM_LEDS):

        led_strip[i] = (r, g, b)
    
    led_strip.write()  # Update the strip 

## TODO: Better document and move this section which is for telling you Wifi isn't connected
# Set the range of pins we want
width_of_wifi_status_leds = 2

# Figure out where our center LED for the wifi indicator will be
wifi_led_center = NUM_LEDS/2 - NUM_LEDS/4 


wifi_status_cur_led = wifi_led_center
wifi_status_led_range = [wifi_led_center-width_of_wifi_status_leds, wifi_led_center+width_of_wifi_status_leds]

# Start by using the range from the middle of the wifi status indicator to the edge. It'll be 5 wide and pulse back and forth with no more than three on at a time.
# 


def hue_offset(index, offset, divisor = 2):
    return (float(index) / (NUM_LEDS // divisor) + offset) % 1.0
        
# Global variable for direction change
direction_change = False
loop_count = 0
hue_cache = {}
def update_strip(position, length, cycle, direction, hue_increment):
    global hue_cache
    # Turn off all LEDs
    for i in range(NUM_LEDS):
        led_strip[i] = (0, 0, 0)

    # Base hue adjusted by the cycle for dynamic coloring
    base_hue = (cycle / MAX_COLOR_CYCLE) % 1  # Ensure hue is between 0 and 1

    # Adjust the increment based on the direction of the chase
    hue_increment = hue_increment * (1 if direction == 1 else -1)

    # Turn on LEDs in the specified segment with a trailing rainbow effect
    for offset in range(length):
        # Calculate hue based on direction
        current_hue = (base_hue + offset * hue_increment) % 1  # Wrap around the hue
        color = hsv_to_rgb(current_hue, 1, BRIGHTNESS)
        idx = (position + offset) % NUM_LEDS  # Handle LED index wrap-around
        led_strip[idx] = color

    led_strip.write()


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
        #r,g,b = normalize_color(r,g,b)
        #print(f"set_leds {r},{g},{b}")

        led_strip[led_index] = (r, g, b)
        
        led_strip.write()
        

        #if ticked:
            #print("Cancel this run!")
            #return False, led_settings  # Return the remaining settings

    return True, None


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
    global direction_change, ticked, STANDALONE_MODE
    direction_change = not direction_change
    if STANDALONE_MODE:
        ticked = True

# Setup timer interrupt
timer = machine.Timer(-1)
timer.init(period=500, mode=machine.Timer.PERIODIC, callback=toggle_direction)

SEGMENT_LENGTH = NUM_LEDS//3 #NUM_LEDS // 3
seg_length = 0
MAX_COLOR_CYCLE = 360  # Maximum value for the color cycle
position = 0

async def chase():
    global direction_change, loop_count, quit_animation, pause_animation, pause_timeout, position, ticked, segment_len
    direction = -1  # Start with any direction, -1 or 1
    cycle = 1
    hue_increment = 60.0 / 360

    while not quit_animation:
        if pause_animation:
            # print(f"Pausing chase for {pause_timeout} seconds")
            await uasyncio.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False

        update_strip(position, segment_len, cycle, direction, hue_increment)  # Pass direction to update_strip

        # Update the position and cycle
        position += direction
        cycle += 1
        if cycle > MAX_COLOR_CYCLE:
            cycle = 1

        # Check for direction change
        if ticked:
            direction *= -1
            ticked = False

        await uasyncio.sleep(0.05)  # Non-blocking sleep
    
# TODO: Move this to be by the other time stuff
def get_clock_hand_positions():
    # Get the current time
    t = utime.localtime()
    hour = t.tm_hour % 12  # Convert to 12-hour format
    minute = t.tm_min
    second = t.tm_sec

    # Calculate positions
    hour_pos = int((hour / 12.0) * NUM_LEDS)
    minute_pos = int((minute / 60.0) * NUM_LEDS)
    second_pos = int((second / 60.0) * NUM_LEDS)

    return hour_pos, minute_pos, second_pos

# TODO: Document how the rainbows work
SPEED = 5
UPDATES = 1000
async def rainbows(timeout_mod = 0):
    global SPEED, UPDATES
    offset = 0.0
    run_on_timeout = False
    if timeout_mod > 0:
        run_on_timeout = True

    timeout = 150
    start_time = utime.time()
    print(f"Making it GAY up in here one sec...")
    while True:
        current_time = utime.time()
        if current_time - start_time > timeout and run_on_timeout:
            uasyncio.create_task(run_animation("chase"))

            break

        SPEED = min(255, max(1, SPEED))
        offset += float(SPEED) / 500.0

        pins_to_skip = set()
        if not wifi_connected:
            pins_to_skip.update(range(int(wifi_status_led_range[0]), int(wifi_status_led_range[1])))
        if mqtt_connected:
            hour_hand_positions = [(HOUR_HAND_POS + offset) % NUM_LEDS for offset in range(-2, 3)]
            minute_hand_positions = [(MINUTE_HAND_POS + offset) % NUM_LEDS for offset in range(-1, 2)]

            pins_to_skip.update(hour_hand_positions)
            pins_to_skip.update(minute_hand_positions)

            # Setting second hand on both rows
            second_hand_positions = [SECOND_HAND_POS % NUM_LEDS]
            second_hand_hue = (hue_offset(SECOND_HAND_POS, offset) + 0.5) % 1.0
            complementary_hue = (hue_offset(0, offset) + 0.5) % 1.0
            #hue = float(i) / (NUM_LEDS // 2)
            rgb = hsv_to_rgb(complementary_hue, 1.0, BRIGHTNESS)
            rgb_int = tuple(int(c * 255) for c in rgb)

            for pos in second_hand_positions:
                led_strip[pos] = rgb_int
                
                #led_strip.set_hsv(pos, second_hand_hue, 1.0, 1.0)
                pins_to_skip.add(pos)
            complementary_hue = (hue_offset(pos, offset) + 0.5) % 1.0
            #hue = float(i) / (NUM_LEDS // 2)
            rgb = hsv_to_rgb(complementary_hue, 1.0, BRIGHTNESS)
            rgb_int = tuple(int(c * 255) for c in rgb)
            # Setting hour and minute hands with offset hue
            for pos in hour_hand_positions + minute_hand_positions:
                
                led_strip[pos] = rgb_int
                #led_strip.set_hsv(pos, complementary_hue, 1.0, 1.0)
                pins_to_skip.add(pos)

        for i in range(NUM_LEDS):
            if i in pins_to_skip:
                continue
            hue = hue_offset(i, offset)
            rgb = hsv_to_rgb(hue + offset, 1.0, BRIGHTNESS)
            #rgb_int = tuple(int(c * BRIGHTNESS * 255) for c in rgb)
            r = rgb[0]
            g = rgb[1]
            b = rgb[2]
            #print(f"Rainbows {r},{g},{b}")

            led_strip[i] = rgb
            #led_strip.set_hsv(i, hue, 1.0, BRIGHTNESS)
        

        led_strip.write()
        await uasyncio.sleep(0.01)


async def i_dont_know_why_this_works(color=1):
    global current_color, loop_count
    hue_1, hue_2 = (100, 220) if color == "1" else (0, 45) if color == "2" else (150, 180)
    
    # Assuming BRIGHTNESS is now a value between 0 and 255
    brightness_scale = MAX_SOLID_BRIGHTNESS / 255.0  # Convert to 0-1 scale

    while True:
        for i in range(NUM_LEDS):
            cycle = hue_1 if i % 2 == 0 else hue_2
            update_strip(i, 1, cycle / MAX_COLOR_CYCLE)  # Update each LED individually
        led_strip.write()
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)

        for i in range(NUM_LEDS):
            cycle = hue_2 if i % 2 == 0 else hue_1
            update_strip(i, 1, cycle / MAX_COLOR_CYCLE)  # Update each LED individually
        led_strip.write()
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)

    # Transition to the rainbows animation
    animation_task = uasyncio.create_task(rainbows())
    await animation_task

async def alternating_blinkies(color="1"):
    if color == "1":
        hue_1, hue_2 = 50, 220
    elif color == "2":
        hue_1, hue_2 = 0, 30
    elif color == "3":
        hue_1, hue_2 = 220, 30
    else:
        hue_1, hue_2 = 50, 100

    # Assuming BRIGHTNESS is now a value between 0 and 255
    brightness_scale =  BRIGHTNESS # Convert to 0-1 scale
    start_time = utime.time()
    timeout = 60
    while True:
        current_time = utime.time()
        if current_time - start_time > timeout:
            
            break
  
        # First pattern
        led_settings = []
        for i in range(NUM_LEDS):
            hue = hue_1 if i % 2 == 0 else hue_2
            led_settings.append([i, hue / 360, 1.0, BRIGHTNESS, 0])  # Sleep time is set to 0

        await set_all_leds_once(led_settings)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)

        # Second pattern
        led_settings = []
        for i in range(NUM_LEDS):
            hue = hue_2 if i % 2 == 0 else hue_1
            led_settings.append([i, hue / 360, 1.0, BRIGHTNESS, 0])  # Sleep time is set to 0

        await set_all_leds_once(led_settings)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)

    uasyncio.create_task(run_animation(STARTING_ANIMATION))

async def set_all_leds_once(led_settings):
    for setting in led_settings:
        led_index, hue, saturation, value, _ = setting  # Ignore sleep time here
        r, g, b = hsv_to_rgb(hue, saturation, value)
        r, g, b = int(r * 255), int(g * 255), int(b * 255)
        #r,g,b = normalize_color(r,g,b)
        #print(f"set_all_leds_at_once {r},{g},{b}")
        led_strip[led_index] = (r, g, b)
    
    led_strip.write()


async def run_animation(animation_name, color=1):
    global quit_animation
    global animation_task
    #quit_animation = False
    print(f"Running animation {animation_name}..")

    if animation_task:
        # quit_animation = True
        animation_task.cancel()
    if animation_name == "alternating_blinkies":
        animation_task = uasyncio.get_event_loop().create_task(alternating_blinkies(color))
    elif animation_name == "rainbows":
        animation_task = uasyncio.get_event_loop().create_task(rainbows())
    elif animation_name == "chase":
        animation_task = uasyncio.get_event_loop().create_task(chase())
    elif animation_name == "idk":
        animation_task = uasyncio.get_event_loop().create_task(i_dont_know_why_this_works())
    await animation_task
    


            
def update_file_from_mqtt_message(msg_string):
    print(f"Starting update process for {msg_string}...")
    update_file_replace(msg_string)


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
        result_match = 0
        team = data[0]
        print(f"Team: {team}, Game Outcome: {game_outcome}")  # Debugging output
        if team == TEAM_ASSIGNED:
            print("Running alternating blinkies animation...")  # Debugging output
            if game_outcome == "start":
                uasyncio.create_task(run_animation("rainbows"))
                result_match = "1"
            elif game_outcome == "tie":
                result_match = "3"
            elif game_outcome == "loss":
                result_match = "2"
            elif game_outcome == "win":
                result_match = "1"
            
                
            
            uasyncio.create_task(run_animation("alternating_blinkies", result_match))
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
        print(f"Triggered msg string {msg_string}") 
        #update_file_from_mqtt_message(msg_string)

async def mqtt_task(client):
    while True:
        try:
            client.check_msg()
            await uasyncio.sleep(0.5)
        except Exception as e:
            print(f"Errors checking messages: {e}")
            reset()

async def connect_to_wifi():
    global wifi_connected
    global wlan
    wifi_connected = False
    # TODO update this to look for all networks in the list WIFI_LIST=[["WhyFhy","WhyKnot42!"],["IoT","1234567890"]] and try to connect to the ones it finds
 
    # set up wifi
    connection_attempts=0
    try:
        #status_handler("Scanning for your wifi network one sec")
        # This is being moved to setup so wifi scanning will still work in the background
        # Setup should be done globally now oops
        #wlan = network.WLAN(network.STA_IF)
        #wlan.active(True)
        nets = wlan.scan()
        for net in nets:
            print(f'Network seen: {net}')
            for network_config in WIFI_LIST:
                
                ssid_to_find = network_config[0]
                if ssid_to_find == net[0].decode('utf-8'):
                    print(f'Network found! {ssid_to_find}')
                    print(f"Attempting to connect to SSID: {ssid_to_find}")
                    if len(network_config) == 0:
                        wlan.connect(ssid_to_find)
                    else:
                        wlan.connect(ssid_to_find, network_config[1])
                    while not wlan.isconnected():
                        #await status_handler(f"Waiting to connect to the network: {ssid_to_find}...")
                        connection_attempts += 1
                        #await uasyncio.sleep(1)
                        
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
        keepalive=0
    )
    client.set_callback(sub_cb)

    try:
        client.connect()
        mqtt_connected = True
    except Exception as e:
        print('Error connecting to %s MQTT broker error: %s' % (MQTT_SERVER, e))

    topics = [b'time',b'color_change', b'scores', b'animate', b'audio_reactive', b'chase', b'update']
    if mqtt_connected:
        for topic in topics:
            try:
                client.subscribe(topic)
                print('Connected to {} MQTT broker, subscribed to {} topic'.format(MQTT_SERVER, topic.decode()))
            except Exception as e:
                print('Error subscribing to %s topic! Error: %s' % (topic.decode(), e))

    return client 
def publish_to_mqtt(topic, message):
    try:
        client.publish(topic, message)
        #print('Message published to topic {}: {}'.format(topic, message))
    except Exception as e:
        print(f'Error publishing message to topic {topic}: {message}, {e}')

async def setup_wireless():
    global wifi_connected
    global mqtt_connected
    global wlan
    
    try:
        if not wifi_connected:
            for i in range(0, 3):
                await connect_to_wifi()

                if wifi_connected:
                    print('Wifi connection successful!')
                    wifi_status = "connected"
                    for _ in range(2):  # Flash red green times
                        make_leds_color(color_hex="000900,0.25")
                        time.sleep(0.5)
                        make_leds_color(color_hex="000000,0.25")
                        time.sleep(0.5)
                    make_leds_color(color_hex="09000F,0.25")
                    break
                else:
                    print(f'Wifi connection failed!')
                    wifi_status = "failed"
                    for _ in range(2):  # Flash red three times
                        make_leds_color(color_hex="090000,0.25")
                        time.sleep(.5)
                        make_leds_color(color_hex="000000,0.25")
                        time.sleep(0.5)
                    
                
    except Exception as e:
        print(f'Wifi connection failed! {e}')
        wifi_status = "failed"
        wifi_connected = False
        for _ in range(4):  # Flash red three times
            make_leds_color(color_hex="090000,0.25")
            time.sleep(.5)
            make_leds_color(color_hex="000000,0.25")
            time.sleep(0.5)
        
        # if no wifi, then you get...

    if wifi_connected:
        set_time()
        counter = 0
        for i in range(0,5):
            try:
                await uasyncio.sleep(2)
                print("Attempting to connect to MQTT broker...")
                client = connectMQTT()
                if mqtt_connected:
                    for _ in range(2):  # Flash red green times
                        make_leds_color(color_hex="000F0F,0.25")
                        time.sleep(0.25)
                        make_leds_color(color_hex="000000,0.25")
                        time.sleep(0.25)
                        make_leds_color(color_hex="000F0F,0.25")
                    mqtt_connected = True
                else:
                    print(f'MQTT connection failed!')
                    wifi_status = "failed"
                    for _ in range(2):  # Flash red three times
                        make_leds_color(color_hex="080000,0.25")
                        time.sleep(.5)
                        make_leds_color(color_hex="000000,0.25")
                        time.sleep(0.5)
                    mqtt_connected = False
                #make_leds_color(color_hex="005500,2")
                return client

            except Exception as e:
                
                print("Failed to connect to MQTT: %s" % e)
                #make_leds_color(color_hex="FF0000,2")
#
async def check_connections():
    global wifi_connected, mqtt_connected
    while True:
        if not wlan.isconnected():
            mqtt_connected = False
            print('WiFi disconnected, attempting to reconnect WiFi and MQTT...')
            await setup_wireless()
        
        await uasyncio.sleep(10)  # Check connection status every 10 seconds
def start_wifi_card():
    global wlan
    print("Kicking on the wifi card one sec..")

    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        print("WiFi card initialized")
    except:
        print("Errors initializing WiFi")


        
async def main():
    global wifi_connected, mqtt_connected
    global client, stand_alone
    
    # Run our beginning animation
    print(f"Turning on the starting animation: {STARTING_ANIMATION}")

    uasyncio.create_task(run_animation(STARTING_ANIMATION))
    
    # Start the Wifi Card
    start_wifi_card()
    # Since GPS uses UART there's no reason to NOT load it up. 
    uasyncio.create_task(gps_scan())
    uasyncio.create_task(handle_ticking())
    # If we're not in standalone mode IE No WiFi mode go ahead and try to connect to a network
    if not STANDALONE_MODE:

        max_attempts = 3
        for x in range(0,3):
        
            if not wifi_connected or not mqtt_connected:
                client = await setup_wireless()
            else:
                break      

        if wifi_connected:
            # Enable if you want to scan for wifi
            #uasyncio.create_task(wifi_scan())
            
            # This is janky, need to make it work better
            uasyncio.create_task(check_connections())
            
            # This will reach out to the interwebs to grab the time remotely every hour
            uasyncio.create_task(set_time())
            
            # This is how you check in with my server for updates!
            if mqtt_connected:
                uasyncio.create_task(mqtt_task(client))
                uasyncio.create_task(publish_list_of_mqtt_messages())
    while True:
        await uasyncio.sleep_ms(1)

uasyncio.run(main())




