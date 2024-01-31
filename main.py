'''

Written by: Amelia Wietting
Date: 20240124
For: FTC Team 19415
'''

from CONFIG.WIFI_CONFIG import SSID, PSK, COUNTRY
from CONFIG.MQTT_CONFIG import MQTT_USERNAME, MQTT_PASSWORD, MQTT_SERVER, MQTT_TOPIC, MQTT_CLIENT_ID
from CONFIG.FTC_TEAM_CONFIG import TEAM_ASSIGNED
from network_manager import NetworkManager
import uasyncio
import time
import urequests
from machine import Pin, reset
import network
from umqtt.simple import MQTTClient
import json
import plasma
from plasma import plasma_stick

current_color = "AA0000"

UPDATE_INTERVAL = 1  # refresh interval in seconds
UPDATE_INTERVAL_BLINKIES = 0.25  # refresh interval for blinkies in seconds
BRIGHTNESS = 0.75
NUM_LEDS = 23

current_leds = [[0] * 3 for _ in range(NUM_LEDS)]
target_leds = [[0] * 3 for _ in range(NUM_LEDS)]

# Set up the Pico W's onboard LED and NeoPixel LEDs
pico_led = Pin('LED', Pin.OUT)
led_strip = plasma.WS2812(NUM_LEDS, 0, 0, plasma_stick.DAT, color_order=plasma.COLOR_ORDER_GRB)
led_strip.start()

# Asynchronous tasks management
animation_task = None
quit_animation = False

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def make_leds_color(color_hex="FF0000"):
    global current_color
    global quit_animation
    quit_animation = True
    current_color = color_hex
    r, g, b = hex_to_rgb(color_hex)
    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, r, g, b)

async def alternating_blinkies(color=1):
    global current_color
    hue_1, hue_2 = (100, 220) if color == "1" else (0, 45) if color == "2" else (150, 180)
    for _ in range(10):
        for i in range(NUM_LEDS):
            hue = hue_1 if i % 2 == 0 else hue_2
            led_strip.set_hsv(i, hue / 360, 1.0, BRIGHTNESS)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)
        for i in range(NUM_LEDS):
            hue = hue_2 if i % 2 == 0 else hue_1
            led_strip.set_hsv(i, hue / 360, 1.0, BRIGHTNESS)
        await uasyncio.sleep(UPDATE_INTERVAL_BLINKIES)
    make_leds_color(current_color)
    
async def rainbows():
    global quit_animation
    quit_animation = False
    SPEED = 20
    UPDATES = 60
    offset = 0.0
    countdown = 0
    while not quit_animation:
        SPEED = min(255, max(1, SPEED))
        offset += float(SPEED) / 2000.0
        for i in range(NUM_LEDS):
            hue = float(i) / NUM_LEDS
            led_strip.set_hsv(i, hue + offset, 1.0, 1.0)
        await uasyncio.sleep(1.0 / UPDATES)
        countdown += 1.0 / UPDATES


async def run_animation(animation_name, color):
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
    if topic == b'color_change':
        make_leds_color(msg_string)
    elif topic == b'scores':
        data = msg_string.split(",")
        game_outcome = data[1]
        team = data[0]
        if team == TEAM_ASSIGNED:
            uasyncio.create_task(run_animation("alternating_blinkies", "1" if game_outcome == "win" else "2"))
    elif topic == b'animate':
        data = msg_string.split(",")
        animation_string = data[0]
        color_blinkies = data[1] if len(data) > 1 else None
        uasyncio.create_task(run_animation(animation_string, color_blinkies))

async def mqtt_task(client):
    while True:
        try:
            client.check_msg()
            await uasyncio.sleep(0)
        except Exception as e:
            print(f"Errors checking messages: {e}")
            reset()


def status_handler(mode, status, ip):
    # reports wifi connection status
    print(mode, status, ip)
    print('Connecting to wifi...')
    
    # flash while connecting
    for i in range(NUM_LEDS):
        led_strip.set_rgb(i, 100, 100, 100)
        time.sleep(0.25)
        if status is not None:
            if status:
                print('Wifi connection successful!')
                make_leds_color(color_hex="FF00FF")
                return True

            else:
                print('Wifi connection failed!')
                make_leds_color(color_hex="FF0000")

def connectMQTT():
	client = MQTTClient(
		client_id=MQTT_CLIENT_ID,
		server=MQTT_SERVER,
		port=0,
		user=MQTT_USERNAME,
		password=MQTT_PASSWORD,
		keepalive=7200,
		ssl=True,
		ssl_params={'server_hostname':'b0d11619bad64381af076f147cf1cb7c.s1.eu.hivemq.cloud'}
	)
	client.set_callback(sub_cb)
	
	try:
		client.connect()

		client.subscribe(b'color_change')
		print('Connected to %s MQTT broker, subscribed to %s topic' % (MQTT_SERVER, "color_change"))
		client.subscribe(b'scores')
		print('Connected to %s MQTT broker, subscribed to %s topic' % (MQTT_SERVER, "scores"))
		client.subscribe(b'animate')
		print('Connected to %s MQTT broker, subscribed to %s topic' % (MQTT_SERVER, "animate"))
	
	except Exception as e:
		print('Error subscribing to %s MQTT broker, %s topic! %s'% (MQTT_SERVER, MQTT_TOPIC, e))
		
	return client


def setup():


	# set up wifi
	try:
		network_manager = NetworkManager(COUNTRY, status_handler=status_handler)
		uasyncio.get_event_loop().run_until_complete(network_manager.client(SSID, PSK))
		make_leds_color(color_hex="0000ff")
	except Exception as e:
		print(f'Wifi connection failed! {e}')
		# if no wifi, then you get...
		make_leds_color()
	
	print("Attempting to connect to MQTT broker...")
	try:
		client = connectMQTT()
		make_leds_color(color_hex="00FF00")
		return client

	except Exception as e:
		print("Failed to connect to MQTT: %s" % e)
		make_leds_color(color_hex="FF0000")
		
client = setup()
uasyncio.run(mqtt_task(client))

    

