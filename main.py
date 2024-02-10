'''

Written by: Amelia Wietting
Date: 20240124
For: FTC Team 19415
'''

from CONFIG.WIFI_CONFIG import SSID, PSK, COUNTRY
from CONFIG.MQTT_CONFIG import MQTT_USERNAME, MQTT_PASSWORD, MQTT_SERVER, MQTT_CLIENT_ID
from CONFIG.FTC_TEAM_CONFIG import TEAM_ASSIGNED
from network_manager import NetworkManager
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
BRIGHTNESS = 0.45
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

# Set up the clock stuffs
SECOND_HAND_POS = 0  # Starting position of the second hand
MINUTE_HAND_POS = 0  # Starting position of the second hand
HOUR_HAND_POS = 0  # Starting position of the second hand

LAST_UPDATE = utime.time()  # Time of the last update
last_drawn_hand = 0

LEDS_PER_CIRCLE = NUM_LEDS/2

def handle_time_message(msg):
    global SECOND_HAND_POS, LAST_UPDATE, MINUTE_HAND_POS, HOUR_HAND_POS
    now = utime.time()

    try:
        # Print the received message for debugging
        print("Received time message:", msg)

        tick_number_str, time_str = msg.split(',')
        tick_number = int(tick_number_str.strip())  # Convert tick_number to an integer
        time_parts = time_str.split(':')
        
        if len(time_parts) != 3:
            print("Unexpected time format:", time_str)
            return

        hours, minutes, seconds = [int(part.strip()) for part in time_parts]
        # Update minute hand position
        MINUTE_HAND_POS = int((minutes * LEDS_PER_CIRCLE // 60) % LEDS_PER_CIRCLE)

        # Update hour hand position (approximation)
        HOUR_HAND_POS = int(((hours % 12) * LEDS_PER_CIRCLE // 12 + minutes // 12) % LEDS_PER_CIRCLE)
        
        #ticks = seconds * 2  
        SECOND_HAND_POS = int((seconds * LEDS_PER_CIRCLE // 60) % LEDS_PER_CIRCLE) #seconds % NUM_LEDS
        #SECOND_HAND_POS = int(SECOND_HAND_POS % LEDS_PER_CIRCLE + LEDS_PER_CIRCLE)
        if SECOND_HAND_POS < NUM_LEDS:
           SECOND_HAND_POS = int(SECOND_HAND_POS + LEDS_PER_CIRCLE)
        
        if MINUTE_HAND_POS > LEDS_PER_CIRCLE:
           MINUTE_HAND_POS = int(MINUTE_HAND_POS - LEDS_PER_CIRCLE)
        if HOUR_HAND_POS > LEDS_PER_CIRCLE:
           HOUR_HAND_POS = int(HOUR_HAND_POS - LEDS_PER_CIRCLE)

        LAST_UPDATE = utime.time()
        print("Handled time message, SECOND_HAND_POS:", SECOND_HAND_POS)
        print("Handled time message, MINUTE_HAND_POS:", MINUTE_HAND_POS)
        print("Handled time message, HOUR_HAND_POS:", HOUR_HAND_POS)

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

    data = msg.split(",")
    bass_leds = int(data[0])
    treble_leds = int(data[1])
    is_beat = bool(data[2])
    is_same_beat = int(data[3])
    print(f"{is_beat}")
    if is_beat:
        # pause_animation = True
        #make_leds_color("AA00FF")
        #time.sleep(0.5 * is_same_beat);    
        #pause_animation = False
        led_strip.set_rgb(lit_led, 255,255,255)
        lit_led = 96
        lit_led = int(lit_led % NUM_LEDS/2 + NUM_LEDS/2)
        

        '''
    # Reset current LED states
    for i in range(NUM_LEDS):
        current_leds[i] = (0, 0, 0)

    # Set bass LEDs
    for i in range(bass_leds):
        if i < NUM_LEDS:
            current_leds[i] = BASS_COLOR

    # Set treble LEDs
    for i in range(NUM_LEDS - treble_leds, NUM_LEDS):
        current_leds[i] = TREBLE_COLOR

    # Update LED strip
    for i in range(NUM_LEDS):
        r, g, b = current_leds[i]
        led_strip.set_rgb(i, r, g, b)
'''

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
    make_leds_color(current_color)

    
async def rainbows():
    global quit_animation, pause_animation, pause_timeout
    
    quit_animation = False
    SPEED = 10
    UPDATES = 60
    offset = 0.0
    offset_2 = 10.0
    countdown = 0
    while not quit_animation:
        if pause_animation:
            print(f"pausing rainbows for {pause_timeout} seconds")
            time.sleep(pause_timeout)
            pause_timeout = 0
            pause_animation = False

        SPEED = min(255, max(1, SPEED))
        offset += float(SPEED) / 2000.0
        offset_2 += float(SPEED) / 2000.0
        for i in range(NUM_LEDS // 2):
            hue = float(i) / (NUM_LEDS // 2)  # Calculate hue based on half the number of LEDs
            
            led_strip.set_rgb(MINUTE_HAND_POS + 1, 255,255,255)
            led_strip.set_rgb(MINUTE_HAND_POS -1, 255,255,255)
            led_strip.set_rgb(MINUTE_HAND_POS, 255,255,255)
            
            led_strip.set_rgb(HOUR_HAND_POS, 0,0,255)
            led_strip.set_rgb(HOUR_HAND_POS + NUM_LEDS//2, 0,0,255)
            row_2 = (i + (NUM_LEDS // 2))
            if not HOUR_HAND_POS == SECOND_HAND_POS:
                led_strip.set_rgb(SECOND_HAND_POS, 255,255,255)
                if row_2 == SECOND_HAND_POS:
                    continue
            #led_strip.set_rgb(HOUR_HAND_POS, 0,0,0)
            
            if i < NUM_LEDS:
                if i == MINUTE_HAND_POS or i == MINUTE_HAND_POS + 1 or i == MINUTE_HAND_POS -1 or i == HOUR_HAND_POS:
                    continue
            if i > NUM_LEDS:
                if row_2 == MINUTE_HAND_POS or row_2 == MINUTE_HAND_POS + 1 or row_2 == MINUTE_HAND_POS - 1 or row_2 == HOUR_HAND_POS + NUM_LEDS//2:
                    continue
                

            led_strip.set_hsv(i, hue + offset, 1.0, BRIGHTNESS)
            led_strip.set_hsv(i + (NUM_LEDS // 2), hue + offset_2, 1.0, BRIGHTNESS)  # Mirror the color on the second half
            
        await uasyncio.sleep(1.0 / UPDATES)
        countdown += 1.0 / UPDATES


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
            await uasyncio.sleep(0)
        except Exception as e:
            print(f"Errors checking messages: {e}")
            reset()


def status_handler(mode, status, ip):
    print(mode, status, ip)
    print('Connecting to wifi...')
    
    for i in range(NUM_LEDS//2):
        led_strip.set_rgb(i % NUM_LEDS, 100, 100, 100)
        time.sleep(0.1)

    if status is not None:
        if status:
            print('Wifi connection successful!')
            make_leds_color(color_hex="FF00FF,2")
            uasyncio.create_task(run_animation("rainbows"))
            return True
        else:
            print('Wifi connection failed!')
            make_leds_color(color_hex="FF0000,4")
            return False

        

def connectMQTT():
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
    except Exception as e:
        print('Error connecting to %s MQTT broker error: %s' % (MQTT_SERVER, e))

    topics = [b'time',b'color_change', b'scores', b'animate', b'audio_reactive']

    for topic in topics:
        try:
            client.subscribe(topic)
            print('Connected to {} MQTT broker, subscribed to {} topic'.format(MQTT_SERVER, topic.decode()))
        except Exception as e:
            print('Error subscribing to %s topic! Error: %s' % (topic.decode(), e))

    return client

def setup():
	# set up wifi
	try:
        
		network_manager = NetworkManager(COUNTRY, status_handler=status_handler)
		uasyncio.get_event_loop().run_until_complete(network_manager.client(SSID, PSK))
		make_leds_color(color_hex="0000ff,2")
	except Exception as e:
		print(f'Wifi connection failed! {e}')
		# if no wifi, then you get...
		make_leds_color(color_hex="FF0000,2")
	
	print("Attempting to connect to MQTT broker...")
	try:
		client = connectMQTT()
		make_leds_color(color_hex="00FF00,2")
		return client

	except Exception as e:
		print("Failed to connect to MQTT: %s" % e)
		make_leds_color(color_hex="FF0000,2")
		
async def main():
    client = setup()
    uasyncio.create_task(mqtt_task(client))
    while True:
        await uasyncio.sleep(0)  # Main loop sleep, to keep the loop alive

uasyncio.run(main())
    
    


