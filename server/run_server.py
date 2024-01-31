import paho.mqtt.client as mqtt
import ssl
from SERVER_CONFIG import MQTT_SERVER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_PASSWORD

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully.")
    else:
        print(f"Connected with result code {rc}")


def publish_message(topic, message):
    client.publish(topic, message)

def main_menu():
    print("\nMQTT Publisher")
    print("1. Publish to color_change")
    print("2. Publish to score")
    print("3. Publish to animate")
    print("4. Cycle the rainbows")
    print("0. Exit")
    choice = input("Enter your choice: ")
    return choice

def handle_color_change():
    color = input("Enter Hex color for RGB (e.g., #FF5733): ")
    publish_message("color_change", color)

def handle_score():
    team_number = input("Enter team number: ")
    result = input("Enter win or lose: ")
    message = f"{team_number},{result}"
    publish_message("scores", message)

def handle_animate():
    animation = input("Select 1 for 'rainbows' or 2 for 'alternating_blinkies': ")

    if animation == "2": # If we want alternating blinkies
        color_choice = input("Enter 1 for blue, 2 for red: ")
        animation += f",{color_choice}"
    if animation == "1": # If we want rainbows
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

    
# MQTT setup
mqtt_server = MQTT_SERVER#input("Enter MQTT server address: ")
mqtt_port = MQTT_PORT  # Typically, the port is 1883 for MQTT
mqtt_client_id = MQTT_CLIENT_ID #input("Enter MQTT client ID: ")
mqtt_username = MQTT_USERNAME #input("Enter MQTT username: ")
mqtt_password = MQTT_PASSWORD #input("Enter MQTT password: ")

client = mqtt.Client(client_id=mqtt_client_id)
client.on_connect = on_connect

# Set the username and password
client.username_pw_set(mqtt_username, mqtt_password)

# Enable SSL/TLS support
client.tls_set()  # Add certfile, keyfile, ca_certs as arguments if needed

# Connect to the HiveMQ server
try:
    client.connect(mqtt_server, mqtt_port, 60)
except Exception as e:
    print(f"Error connecting to MQTT server: {e}")
    exit(1)

client.loop_start()

run_loop = bool(True)
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
    elif choice == '0':
        print('Quitting Command n Control Server ^_^')
        print('Thank you for using the FTC MQTT Fancy Light Utility')
        print('An Aask Labs Product - 2024')
        run_loop = False
        break
    else:
        print("Invalid choice. Please try again.")

client.loop_stop()
client.disconnect()
