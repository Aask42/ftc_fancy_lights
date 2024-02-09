import paho.mqtt.client as mqtt
import ssl
import json
import numpy as np
import pyaudio
import wave
import threading
import tkinter as tk
from tkinter import filedialog
from scipy.fft import rfft, rfftfreq
from collections import deque
import math
import wave
from pydub import AudioSegment
import time
from datetime import datetime

# Fetch configurations
from SERVER_CONFIG import MQTT_SERVER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD

# Global variables for audio processing
audio_file = None
audio_thread = None
audio_reactive_mode = False
p = None
audio_stream = None
audio_buffer = deque(maxlen=10)  # Buffer to store audio data

# Audio constants
CHUNK = 1024  # Audio chunk size
FORMAT = pyaudio.paInt16  # Audio format
CHANNELS = 1  # Number of audio channels
RATE = 44100  # Sample rate

# Global variables for peak tracking
peak_bass = 0
peak_treble = 0
decay_factor = 0.05  # You can adjust this value for the rate of decay

class HalfSecondClock:
    def __init__(self):
        self.start_time = time.time()
        self.tick_count = 0
        self.running = True

    def start(self):
        while self.running:
            self.tick()
            time.sleep(1)  # Wait for one second

    def stop(self):
        self.running = False

    def tick(self):
        self.tick_count += 1
        elapsed_time = time.time() - self.start_time
        current_time = datetime.now().strftime("%H:%M:%S")  # Format: Hours:Minutes:Seconds.Milliseconds
        msg = f"{self.tick_count},{current_time}"
        # print(f"Tick: {self.tick_count}, Elapsed Time: {elapsed_time:.2f} seconds")
        publish_message('time', msg)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully.")
    else:
        print(f"Connected with result code {rc}")

def publish_message(topic, message):
    client.publish(topic, message)

def handle_color_change():
    color = input("Enter Hex color for RGB (e.g., #FF5733): ")
    publish_message("color_change", color.upper())

def handle_score():
    team_number = input("Enter team number: ")
    result = input("Enter win or lose: ")
    message = f"{team_number},{result}"
    publish_message("scores", message)

def handle_animate():
    animation = input("Select 1 for 'rainbows' or 2 for 'alternating_blinkies': ")
    if animation == "2":
        color_choice = input("Enter 1 for blue, 2 for red: ")
        animation += f",{color_choice}"
    elif animation == "1":
        animation = "rainbows"
    publish_message("animate", animation)
    
def rgb_to_hex(rgb):
    """Convert an RGB tuple to a hexadecimal color string."""
    return '{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

def interpolate_color(start_color, end_color, step):
    """
    Generator to interpolate between two colors.
    :param start_color: Tuple of (R, G, B) as the start color.
    :param end_color: Tuple of (R, G, B) as the end color.
    :param step: The step size for interpolation.
    :return: Yields a hexadecimal color string.
    """
    delta = [end - start for start, end in zip(start_color, end_color)]

    for t in range(step + 1):
        intermediate_color = [start + delta[i] * t / step for i, start in enumerate(start_color)]
        yield rgb_to_hex(tuple(int(c) for c in intermediate_color))

def fade_colors_about():
    step = 120  # Number of steps in the fade. Increase for smoother transitions.

    red = (255, 0, 0)
    green = (0, 255, 0)
    blue = (0, 0, 255)
    max_cycle = 10
    loop_count = 0
    while max_cycle > loop_count:
        # Fade from red to green
        for color in interpolate_color(red, green, step):
            publish_message("color_change", f"{color}")

        # Fade from green to blue
        for color in interpolate_color(green, blue, step):
            publish_message("color_change", f"{color}")

        # Fade from blue back to red
        for color in interpolate_color(blue, red, step):
            publish_message("color_change", f"{color}")
        loop_count += 1

def select_audio_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select Audio File", filetypes=[("Audio Files", "*.wav *.mp3")])
    root.destroy()
    return file_path


def main_menu():
    print("\nMQTT Publisher")
    print("1. Publish to color_change")
    print("2. Publish to score")
    print("3. Publish to animate")
    print("4. Cycle the rainbows")
    print("5. Toggle Audio Reactive Mode")
    print("0. Exit")
    choice = input("Enter your choice: ")
    return choice
def audio_callback(in_data, frame_count, time_info, status):
    audio_buffer.append(np.frombuffer(in_data, dtype=np.int16))
    return (in_data, pyaudio.paContinue)


def stop_audio_stream():
    global p, audio_stream
    audio_stream.stop_stream()
    audio_stream.close()
    p.terminate()

def process_audio():
    global peak_bass, peak_treble

    while audio_reactive_mode and audio_file:
        data = audio_file.readframes(CHUNK)
        if not data:
            break  # Stop if end of file
        audio_data = np.frombuffer(data, dtype=np.int16)
        # Write data to playback stream for hearing the song
        playback_stream.write(data)
        
        # FFT analysis
        yf = rfft(audio_data)
        xf = rfftfreq(CHUNK, 1 / RATE)

        # Calculate amplitudes
        bass = np.abs(yf[:len(xf) // 2])
        treble = np.abs(yf[len(xf) // 2:])
        bass_amp = np.average(bass)
        treble_amp = np.average(treble)

        # Update peak values or apply decay
        peak_bass = max(bass_amp, peak_bass * (1 - decay_factor))
        peak_treble = max(treble_amp, peak_treble * (1 - decay_factor))

        # Prepare MQTT message with decayed peaks
        max_bass = max(bass) if bass.any() else 1
        max_treble = max(treble) if treble.any() else 1
        num_leds_bass = math.ceil(peak_bass / max_bass * 10)
        num_leds_treble = math.ceil(peak_treble / max_treble * 10)

        message = json.dumps({'bass': num_leds_bass, 'treble': num_leds_treble})
        publish_message("audio_reactive", message)

def convert_to_wav(file_path):
    audio = AudioSegment.from_file(file_path)
    wav_path = file_path.rsplit('.', 1)[0] + '.wav'
    audio.export(wav_path, format='wav')
    return wav_path

def start_audio_stream():
    global p, audio_stream, playback_stream
    p = pyaudio.PyAudio()
    audio_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK, stream_callback=audio_callback)

    # Initialize playback stream
    playback_stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

def stop_audio_stream():
    global p, audio_stream, playback_stream
    audio_stream.stop_stream()
    audio_stream.close()

    # Stop and close the playback stream
    playback_stream.stop_stream()
    playback_stream.close()

    p.terminate()

def handle_audio_reactive_mode():
    global audio_reactive_mode, audio_file
    if audio_reactive_mode:
        audio_reactive_mode = False
        if audio_file:
            audio_file.close()
            audio_file = None
        print("Audio reactive mode stopped")
    else:
        audio_file_path = select_audio_file()
        if audio_file_path:
            wav_file_path = convert_to_wav(audio_file_path)  # Convert to WAV
            audio_file = wave.open(wav_file_path, 'rb')
            audio_reactive_mode = True
            start_audio_stream()
            threading.Thread(target=process_audio).start()
            print("Audio reactive mode started")

# Start our clock

clock = HalfSecondClock()
clock_thread = threading.Thread(target=clock.start)
clock_thread.start()

# MQTT setup
client = mqtt.Client(client_id=MQTT_CLIENT_ID)
client.on_connect = on_connect
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.tls_set()  # Enable SSL/TLS support

# Connect to the MQTT server
try:
    client.connect(MQTT_SERVER, MQTT_PORT, 60)
except Exception as e:
    print(f"Error connecting to MQTT server: {e}")
    exit(1)

client.loop_start()

run_loop = True
while run_loop:
    choice = main_menu()
    if choice == '1':
        handle_color_change()
    elif choice == '2':
        handle_score()
    elif choice == '3':
        handle_animate()
    elif choice == '4':
        fade_colors_about()
    elif choice == '5':
        print("Under Construction")
        #handle_audio_reactive_mode()
        #if not audio_reactive_mode:
        #    stop_audio_stream()
    elif choice == '0':
        print('Quitting Command n Control Server ^_^')
        print('Thank you for using the FTC MQTT Fancy Light Utility')
        print('An Aask Labs Product - 2024')
        clock.stop()
        run_loop = False
    else:
        print("Invalid choice. Please try again.")

client.loop_stop()
client.disconnect()
