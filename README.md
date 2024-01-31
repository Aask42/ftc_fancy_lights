Documentation for FTC Team 19415

This code is designed to control an LED strip in various ways based on messages received over MQTT (a lightweight messaging protocol for small sensors and mobile devices). It's written for use on a microcontroller running MicroPython, a lean and efficient implementation of Python 3.
Key Components:

    Imports:
        The code begins by importing necessary modules for network management, asynchronous operations, handling the LED strip, and MQTT communication.

    Global Variables:
        current_color, UPDATE_INTERVAL, BRIGHTNESS, NUM_LEDS: These variables store the current color of LEDs, refresh intervals, brightness level, and number of LEDs in the strip.
        current_leds, target_leds: Arrays to manage the current and target color states of each LED.
        animation_task: A variable to manage the currently running animation task.

    LED Setup:
        The code sets up the Pico W's onboard LED and a NeoPixel LED strip. It initializes the LED strip and starts it.

    Utility Functions:
        hex_to_rgb(hex_str): Converts a hexadecimal color string to an RGB tuple.
        make_leds_color(color_hex): Sets the entire LED strip to a specified color.

    Asynchronous Animation Functions:
        alternating_blinkies(color): Runs an animation where LEDs blink in alternating colors. The color parameter changes the color scheme.
        rainbows(): Creates a moving rainbow effect across the LED strip.

    Animation Control:
        run_animation(animation_name, color): Starts a new animation based on the provided name and color. If an animation is already running, it stops that animation before starting the new one.

    MQTT Callback and Task:
        sub_cb(topic, msg): Handles incoming MQTT messages, triggering different actions like changing LED colors or starting animations.
        mqtt_task(client): An asynchronous task that checks for MQTT messages and handles disconnections.

    WiFi and MQTT Connection:
        status_handler(mode, status, ip): Reports the WiFi connection status and handles LED indications during connection attempts.
        connectMQTT(): Sets up the MQTT client, connects to the broker, and subscribes to topics.

    Setup and Main Loop:
        The setup() function initializes the WiFi connection and connects to the MQTT broker.
        Finally, the mqtt_task is run in an event loop to continuously check for and handle MQTT messages.

How It Works:

    When the program starts, it first tries to establish a WiFi connection. The LEDs blink while connecting and then show a color indicating success or failure.
    Once connected to WiFi, it attempts to connect to an MQTT broker using the provided credentials and subscribes to specific topics.
    When an MQTT message is received, the sub_cb function is triggered. Depending on the topic and message content, it might change the color of the LEDs, or start an animation like blinking or rainbows.
    The animations are asynchronous, meaning the microcontroller can continue to do other tasks (like receiving more MQTT messages) while the animations are running.

Usage:

    This code can be used in robotics or IoT projects where visual feedback via LEDs is needed.
    MQTT messages can be sent from various sources, like a smartphone app or another microcontroller, to remotely control the LED behavior.

This code is a versatile tool for teams to create visually engaging projects with interactive LED displays controlled over a network.