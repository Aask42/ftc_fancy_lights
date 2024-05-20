import bluetooth
import struct
import time

class BLEScanner:
    def __init__(self, ble, target_namespace_id):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._target_namespace_id = target_namespace_id

    def _irq(self, event, data):
        #if event == 5:  # Event value for _IRQ_SCAN_RESULT
        addr_type, addr, adv_type, rssi, adv_data = data
        namespace_id = ''.join(['{:02X}'.format(b) for b in adv_data[13:23]])

        #if rssi > -10:
        self.print_info(addr, rssi, adv_type, adv_data)

    def start_scan(self, duration_ms=3000):
        self._ble.gap_scan(0, duration_ms, duration_ms)

    def stop_scan(self):
        self._ble.gap_scan(None)

    def print_info(self, addr, rssi, adv_type, adv_data):
        print("Target Device Found - Address: {}, RSSI: {}, Adv. Type: {}".format(
            ':'.join(['{:02X}'.format(b) for b in addr]),
            rssi, adv_type
        ))

        # Extract Namespace ID from bytes 14-23
        namespace_id = ''.join(['{:02X}'.format(b) for b in adv_data[13:23]])

        # Extract Instance ID from bytes 24-29
        instance_id = ''.join(['{:02X}'.format(b) for b in adv_data[23:29]])

        print("  Namespace ID: {}".format(namespace_id))
        print("  Instance ID: {}".format(instance_id))

        # Print the entire advertising data as hex
        print("Raw Advertising Data (Hex):", ' '.join(['{:02X}'.format(b) for b in adv_data]))

def general_ble_scan():
    target_namespace_id = 'BLABLABLABLABLA'  # Replace with your target Namespace ID
    ble = bluetooth.BLE()
    scanner = BLEScanner(ble, target_namespace_id)

    print("Scanning for BLE advertisers with RSSI > -10")
    scanner.start_scan(duration_ms=5000)  # Scan for 15 seconds
    time.sleep(5)
    scanner.stop_scan()