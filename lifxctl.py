import sys
import lifx
from time import sleep

# Helper functions
# Human readable MAC
def MACstr(addr):
	return ':'.join(reversed([hex(addr)[i:i+2].upper() for i in range(2, len(hex(addr)), 2)]))
# Decode string32
def label(data):
	return data.rstrip(b'\x00').decode('utf-8')

# Encode/Decode floats, ints, bools for range [0-65535]
def c(val):
	return int(65535 * val)
def d(data):
	return data / 65535


# Examples
def list_devices():
	for (_, _, dev, *_), (service, _) in lifx.get(lifx.GetService, lifx.StateService):
		if service == 1:
			print(MACstr(dev))

def power_on():
	lifx.post(lifx.LightSetPower, c(True), 0)

def power_status():
	for (_, _, dev, *_), (power,) in lifx.get(lifx.LightGetPower, lifx.LightStatePower):
		print(MACstr(dev), ':', 'On' if power else 'Off')

def toggle_power():
	for (_, _, dev, *_), (power,) in lifx.get(lifx.LightGetPower, lifx.LightStatePower):
		lifx.post(lifx.LightSetPower, c(1 - d(power)), 0, device=dev)

def set_print(): # Set power with res_requested - NOTE: delay of set
	for (_, _, dev, *_), (power,) in lifx.get(lifx.LightSetPower, lifx.LightStatePower, c(True), 2000, res=1):
		print(MACstr(dev), ':', 'On' if power else 'Off')

def list_status():
	output = list()
	for _, data in lifx.get(lifx.LightGet, lifx.LightState):
		output.append('{} ({})\n\tHue: {:.2f}%\n\tSaturation: {:.2f}%\n\tBrightness: {:.0f}%\n\tKelvin: {}K'.format(
		label(data[6]), 'On' if data[5] else 'Off',
		360 * d(data[0]), 100 * d(data[1]), 100 * d(data[2]), data[3]))
	print(*sorted(output), sep='\n\n')

def set_level(level):
    assert level >= 1 and level <= 6
    if level == 1:
        lifx.post(lifx.LightSetPower, c(False), 0)
        print('Turned off')
    else:
        assert level >= 0
        level_p = (level-2)/4
        brightness = 0.02 + level_p*0.98    # 0.02 to 1.00
        temperature = 1500 + (level-2)*1125 # 1500 to 6000


        for (_, _, dev, *_), (power,) in lifx.get(lifx.LightGetPower, lifx.LightStatePower):
            print('setting', dev)
#             if not power:
#                 lifx.post(lifx.LightSetPower, c(True), 0, device=dev)
#                 print('Turned on')
#                 sleep(0.05)
            lifx.post(lifx.LightSetColor,
                0,                  # Reserved
                0,                  # H
                0,                  # S
                c(brightness),      # B
                temperature,        # K (temperature)
                0,                  # duration
                device=dev)



if __name__ == "__main__":
    if len(sys.argv) == 2:
        level = int(sys.argv[1])
        set_level(level)
    else:
        list_devices()
        print()
        list_status()
