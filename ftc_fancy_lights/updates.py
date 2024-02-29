from CONFIG.OTA_CONFIG import OTA_HOST, PROJECT_NAME, FILENAMES
from CONFIG.MQTT_CONFIG import MQTT_CLIENT_ID
import uos
import urequests
import micropython as mp
import gc



def update_file_replace(msg_string):
    print(f"Starting update process for {msg_string}...")
    filename = msg_string
    
    mp.mem_info(1)
    gc.collect()
    
    try:
          
        updated = False
        print(f"Updating file {filename}")
        
        for i,item in enumerate(FILENAMES):
            print(f"Seeing if {filename} is in {item}")

            if filename in item:
                file_to_write = item
                print(f"Found filename! Simple name: {filename} Fullly Qualified: {item}")
                try:
                    uos.mkdir('tmp')
                except:
                    pass
                
                updated = False
                file_to_write = FILENAMES[i]
                response = urequests.get(f'{OTA_HOST}/ota_updates/{MQTT_CLIENT_ID}/{filename}', timeout=5)
                response_text = response.text
                response.close()
                #print(f"Found file {filename} with {response_text}")
                # Get the file we need to write
                # Write to a tmp file
                print(f"Going to try to write to tmp/{file_to_write}")

                with open(f'tmp/{filename}', 'w') as source_file:
                    source_file.write(response_text)
                    
                    
                # Overwrite our onboard file               
                with open(f'tmp/{filename}', 'r') as source_file, open(file_to_write, 'w') as target_file:
                    target_file.write(source_file.read())
                
                uos.remove(f'tmp/{filename}')
                    
                try:
                    uos.rmdir('tmp')
                except:
                    pass
                break
    except Exception as e:
        print(f"Exception updating file! {e}")
