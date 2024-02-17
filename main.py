'''

Written by: Amelia Wietting
Date: 20240124
For: FTC Team 19415
'''

from CONFIG.WIFI_CONFIG import SSID, PSK, COUNTRY, MAX_WIFI_CONNECT_TIMEOUT
from CONFIG.MQTT_CONFIG import MQTT_USERNAME, MQTT_PASSWORD, MQTT_SERVER, MQTT_CLIENT_ID
from CONFIG.FTC_TEAM_CONFIG import TEAM_ASSIGNED
import uasyncio
import time
import utime
import urequests
from machine import Pin, reset
import network
from umqtt.simple import MQTTClient
import sys
import json
import plasma
from led_manager import NUM_LEDS, LED_PIN

# Audio reactive constants
BASS_COLOR = (255, 0, 0)  # Red for bass
TREBLE_COLOR = (0, 0, 255)  # Blue for treble

current_color = "AA0000"

UPDATE_INTERVAL_BLINKIES = 0.25  # refresh interval for blinkies in seconds
BRIGHTNESS = 0.50
MAX_SOLID_BRIGHTNESS = 255 # Max Solid Color Brightness


current_leds = [[0] * 3 for _ in range(NUM_LEDS)]
target_leds = [[0] * 3 for _ in range(NUM_LEDS)]

# Set up the Pico W's onboard LED and NeoPixel LEDs
pico_led = Pin('LED', Pin.OUT)
led_strip = plasma.WS2812(NUM_LEDS, 0, 0, LED_PIN, color_order=plasma.COLOR_ORDER_GRB)
led_strip.start()

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

def handle_time_message(msg):
    global SECOND_HAND_POS, LAST_UPDATE, MINUTE_HAND_POS, HOUR_HAND_POS
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
        print("Handled time message, SECOND_HAND_POS:", SECOND_HAND_POS)
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
    
    r, g, b = hex_to_rgb(color_hex)

    # Normalize the color
    r, g, b = normalize_color(r, g, b)

    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, r, g, b)


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

def hue_offset(index, offset, divisor = 2):
    return (float(index) / (NUM_LEDS // divisor) + offset) % 1.0
async def set_leds(led_settings):
    """
    Set the LEDs based on a list of settings.
    Each setting in the list should be in the format [LED, H, S, V, SleepTime].
    """
    for setting in led_settings:
        led_index, hue, saturation, value, sleep_time = setting
        led_strip.set_hsv(led_index, hue, saturation, value)
        await uasyncio.sleep(sleep_time)

direction_anticlockwise = False
cycle_count = 0
async def marquee_strip():
    global quit_animation, pause_animation, pause_timeout, led_strip, wifi_connected, mqtt_connected, direction_anticlockwise, cycle_count

    quit_animation = False
    hue = 0
    SPEED = 25
    offset = 0.0
    cycle_count = 0
    led_sleep_time = 1 / 200

    SPEED = max(1, min(255, SPEED))

    # Initialize a list to track the state of each LED (True for on, False for off)
    led_states = [False] * NUM_LEDS
    
    second_width = NUM_LEDS // 30
    
    while not quit_animation:
        if pause_animation:
            print(f"Pausing rainbows for {pause_timeout} seconds")
            await uasyncio.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False

        offset += float(SPEED) / 2000.0
        led_settings = []
        pins_to_skip = set()
        # Logic for clock hands (currently commented out)
        '''
        if mqtt_connected:
            hour_hand_positions = [(HOUR_HAND_POS + offset) % NUM_LEDS for offset in range(-2, 3)]
            minute_hand_positions = [(MINUTE_HAND_POS + offset) % NUM_LEDS for offset in range(-1, 2)]
            second_hand_positions = [SECOND_HAND_POS, (SECOND_HAND_POS + NUM_LEDS // 2) % NUM_LEDS]

            for pos in hour_hand_positions + minute_hand_positions + second_hand_positions:
                complementary_hue = (hue_offset(pos, offset) + 0.5) % 1.0
                led_settings.append([pos, complementary_hue, 1.0, 1.0, led_sleep_time])
                pins_to_skip.add(pos)
        '''

        # Toggle direction based on cycle_count
        if cycle_count % 2 == 0:
            print(f"Tick {cycle_count}")
            for i in range(NUM_LEDS - 1):
                if i not in pins_to_skip:
                    hue = hue_offset(i, offset)
                    led = (i + SECOND_HAND_POS) % NUM_LEDS

                    if not led_states[led]:
                        led_settings.append([led, hue, 1.0, BRIGHTNESS, led_sleep_time])
                        led_states[led] = True

                led_opposite = (led + NUM_LEDS // 2 + 5) % NUM_LEDS
                if led_opposite not in pins_to_skip and led_states[led_opposite]:
                    led_settings.append([led_opposite, 0, 0, 0, led_sleep_time])
                    led_states[led_opposite] = False

        else:
            print(f"Tock {cycle_count}")
            for i in range(NUM_LEDS - 2, -1, -1):
                if i not in pins_to_skip:
                    hue = hue_offset(i, offset)
                    led = (i + SECOND_HAND_POS) % NUM_LEDS

                    if not led_states[led]:
                        led_settings.append([led, hue, 1.0, BRIGHTNESS, led_sleep_time])
                        led_states[led] = True

                led_opposite = (led + NUM_LEDS // 2 + 6) % NUM_LEDS
                if led_opposite not in pins_to_skip and led_states[led_opposite]:
                    led_settings.append([led_opposite, 0, 0, 0, led_sleep_time])
                    led_states[led_opposite] = False
        
        await set_leds(led_settings)
        total_sleep_time = sum(led_sleep_time for _, _, _, _, led_sleep_time in led_settings)
        
        offset_sleep_time = max(0, 1 - total_sleep_time)
        if offset_sleep_time > 0:
            print(f"Sleeping for {offset_sleep_time} to balance loop time")
            await uasyncio.sleep(offset_sleep_time)

        cycle_count += 1



async def rainbows():
    global quit_animation, pause_animation, pause_timeout, led_strip
    global wifi_status_cur_led, wifi_led_on, wifi_status_led_range, wifi_connected, mqtt_connected
    quit_animation = False
    SPEED = 15
    UPDATES = 100
    offset = 0.0

    while not quit_animation:
        if pause_animation:
            print(f"pausing rainbows for {pause_timeout} seconds")
            await uasyncio.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False

        SPEED = max(1, min(255, SPEED))
        offset += float(SPEED) / 2000.0
        
        pins_to_skip = set()
        if not wifi_connected:
            pins_to_skip.update(range(int(wifi_status_led_range[0]), int(wifi_status_led_range[1])))
        if mqtt_connected:
            hour_hand_positions = [(HOUR_HAND_POS + offset) % NUM_LEDS for offset in range(-2, 3)]
            minute_hand_positions = [(MINUTE_HAND_POS + offset) % NUM_LEDS for offset in range(-1, 2)]

            pins_to_skip.update(hour_hand_positions)
            pins_to_skip.update(minute_hand_positions)

            # Setting second hand on both rows
            second_hand_positions = [SECOND_HAND_POS, (SECOND_HAND_POS + NUM_LEDS // 2) % NUM_LEDS]
            second_hand_hue = (hue_offset(SECOND_HAND_POS, offset) + 0.5) % 1.0
            for pos in second_hand_positions:
                led_strip.set_hsv(pos, second_hand_hue, 1.0, 1.0)
                pins_to_skip.add(pos)
            
            # Setting hour and minute hands with offset hue
            for pos in hour_hand_positions + minute_hand_positions:
                complementary_hue = (hue_offset(pos, offset) + 0.5) % 1.0
                led_strip.set_hsv(pos, complementary_hue, 1.0, 1.0)
                pins_to_skip.add(pos)

        for i in range(NUM_LEDS):
            if i in pins_to_skip:
                continue
            hue = hue_offset(i, offset)
            led_strip.set_hsv(i, hue, 1.0, BRIGHTNESS)

        await uasyncio.sleep(1.0 / UPDATES)



async def alternating_blinkies(color=1):
    global current_color
    hue_1, hue_2 = (100, 220) if color == "1" else (0, 45) if color == "2" else (150, 180)
    
    # Assuming BRIGHTNESS is now a value between 0 and 255
    brightness_scale = MAX_SOLID_BRIGHTNESS / 255.0  # Convert to 0-1 scale

    for _ in range(10):
        for i in range(NUM_LEDS):
            hue = hue_1 if i % 2 == 0 else hue_2
            led_strip.set_hsv(i, hue / 360, 1.0, brightness_scale)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)
        for i in range(NUM_LEDS):
            hue = hue_2 if i % 2 == 0 else hue_1
            led_strip.set_hsv(i, hue / 360, 1.0, brightness_scale)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)
    #make_leds_color(current_color)
    animation_task = uasyncio.create_task(rainbows())
    await animation_task


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

async def mqtt_task(client):
    while True:
        try:
            client.check_msg()
            await uasyncio.sleep(0.05)
        except Exception as e:
            print(f"Errors checking messages: {e}")
            reset()

async def connect_to_wifi():
    global wifi_connected
    wifi_connected = False
    # set up wifi
    connection_attempts=0
    try:
        status_handler("Scanning for your wifi network one sec")

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        nets = wlan.scan()
        for net in nets:
            if SSID == net[0].decode('utf-8'):
                print(f'Network found! {SSID}')
                print(f"Attempting to connect to SSID: {SSID}")
                wlan.connect(SSID, PSK)
                while not wlan.isconnected():
                    await status_handler(f"Waiting to connect to the network: {SSID}...")
                    connection_attempts += 1
                    await uasyncio.sleep(1)
                    
                    if connection_attempts > MAX_WIFI_CONNECT_TIMEOUT:
                        print("Exceeded MAX_WIFI_CONNECT_TIMEOUT!!!")
                        break
                        
                wifi_connected = True
                print('WLAN connection succeeded!')
                break
        if not wifi_connected:
            print(f"Unable to find SSID: {SSID}")
    except Exception as e:
        print(f"Setup failed: {e}")

row_one = False
async def status_handler(message):
    global wifi_connected, row_one
    print(message)

    #print(f"Row one? {row_one} {loops}")
    if row_one:
        print(f"Row one")
        for i in range(NUM_LEDS//2):
            #print(f"Turning off LED {i}")
            led_strip.set_rgb(i, 0, 0, 0)
            await uasyncio.sleep(NUM_LEDS //2 * 0.0005)
    else:
        print(f"Row Two!!")

        for i in range(NUM_LEDS//2, NUM_LEDS):
            led_strip.set_rgb(i, 0, 0, 0)
            await uasyncio.sleep(NUM_LEDS // 2 * 0.0005)
    
    row_one = not row_one # Switch from flase to true and vice versa each loop

    if row_one:
        for i in range(NUM_LEDS//2):
            led_strip.set_rgb(i, 100, 100, 100)
            await uasyncio.sleep(NUM_LEDS//2 * 0.001)
    else:
        
        for i in range(NUM_LEDS//2, NUM_LEDS):
            #print(f"Turning ON LED {i}")
            led_strip.set_rgb(i, 100, 100, 100)
            await uasyncio.sleep(NUM_LEDS//2 * 0.001)#
    
    
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

    topics = [b'time',b'color_change', b'scores', b'animate', b'audio_reactive', b'chase']

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
    while True:
        await uasyncio.sleep(0)  # Main loop sleep, to keep the loop alive

uasyncio.run(main())