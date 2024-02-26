
class UpdatePico():
    def __init__(self):
        print("Starting update process...")
        self.config_file_list = ["CLOCK_CONFIG.py","FTC_TEAM_CONFIG.py", "LED_MANAGER.py", "MQTT_CONFIG.py", "WIFI_CONFIG.py"]

    def update_file_all(self, filename = None, content_to_write=None):
        if content_to_write:
            print(f"Updating file {filename}")
            with open(filename, 'w') as config_file:
                config_file.write(content_to_write)        
    def update_file_replace(self, filename=None, content_to_update=None):
        if content_to_update and filename in self.config_file_list:
            
            field, new_content = content_to_update
            updated = False
            new_lines = []

            print(f"Updating file {filename}")

            # Read the file and modify the specified field
            with open(filename, 'r') as config_file:
                for line in config_file:
                    if line.startswith(field):
                        new_lines.append(f'{field}="{new_content}"\n')
                        updated = True
                    else:
                        new_lines.append(line)

            # If the field was not found in the file, add it
            if not updated:
                new_lines.append(f'{field}="{new_content}"\n')

            # Write the updated content back to the file
            with open(filename, 'w') as config_file:
                config_file.writelines(new_lines)
        else:
            print("Filename or content to update is missing")
     
