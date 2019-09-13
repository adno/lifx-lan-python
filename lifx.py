"""
A low-level python wrapper around the LIFX LAN v2 API.

Adam Nohejl, 2019/9/8: Forked from https://github.com/marcushultman/\
lifx-lan-python/, updated according to the current version of LIFX LAN v2 API
and fixed a small bug.

The `lifxctl` module/command line tool provides a slightly higher-level
interface built on top of this.
"""

import socket
import uuid
import struct

DEFAULT_PORT		= 56700
BROADCAST_ADDRESS	= '255.255.255.255'

# Socket
_csoc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_csoc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
_csoc.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
_csoc.settimeout(0.5)
_csoc.bind(('', DEFAULT_PORT))

# Internal data
_src = uuid.uuid1().node % 4294967296
_sequence = 0
_messageQueue = dict()

# Network interface
def post(Message, *payload, device=0, port=DEFAULT_PORT, address=None):
	for __ in get(Message, None, *payload, device=device, port=port, address=address):
		pass

def get(
	Message, Response, *payload,
	device=0, ack=0, res=0,
	timeout=0.5, limit=None, port=DEFAULT_PORT,
	address=None, get_address=False
	):
	"""
	Send a message and receive responses. Yields the responses as
	(optional address, header, message data) pair/triples.

	Use post() if you do not need a response.

	Typical usage:
	1. service discovery:
	   get(GetService, StateService, get_address=True)
	2. communication with a particular device (unicast, preferred)
	   get(msg, svc, *payload, device=..., port=..., address=...)
	3. communication with a particular device (broadcast)
	   get(msg, svc, *payload, device=..., port=...)

    Parameters:
    - `Message` -- message struct for the message payload
    - `Response` -- message struct for the expected response (or None, if no
      response is expected)
    - `payload` -- payload to formatted via Message and sent
	- `device` and `port` -- use defaults for discovery via GetService
	  (broadcast: address=None), then use the device and port from the response
	  to GetService (unicast to a specific address)
	- `ack`, `res` -- request acknowledgement/response
	  TODO: we should have special code for managing both at the same time
	- `timeout` -- timeout
	- `limit` -- limit the number of responses accepted
	- `address` -- an IP address for unicast (broadcast if None),
	  use `get_address` to determine
	- `get_address` -- if True get the device's IP address as the first item
	  in the first item of the yielded tuple
	"""
	# Send packet
	global _sequence
	seq = _sequence = (_sequence + 1) % 256
	data = Message.pack(_src, seq, device, ack, res, *payload)
	_csoc.sendto(data, (address or BROADCAST_ADDRESS, port))
	if Response is None:
	    return
	# Receive response
	mKey = (seq, Response.type)
	while Response and (limit is None or limit > 0):
		q = _messageQueue.setdefault(mKey, list())
		try:
			_csoc.settimeout(timeout)
			data_sender = q.pop(0) if q else _csoc.recvfrom(256)
		except socket.error:
			break
		else:
			data, sender = data_sender
			header = Header.unpack(data)
			rKey = header[3:5]
			if rKey == mKey:
				if get_address:
					# Do not return port (sender[0])
					yield sender[0], header, Response.unpack(data[Header.size:])
				else:
					yield header, Response.unpack(data[Header.size:])
				if limit is not None:
					limit -= 1
			elif rKey != (seq, Message.type): # our own broadcasted message
				_messageQueue.setdefault(rKey, list()).append(data_sender)

# Data structures
class Header():
	_struct = struct.Struct('<HHIQIHBBQHH')
	size = _struct.size
	def pack(type, payloadSize, source, sequence, device=0, ack=0, res=0):
		return Header._struct.pack(
			# Frame
			Header.size + payloadSize,
			(0 if device else 0x2000) + 0x1400,
			source,
			# Frame Address
			device,
			0x00000000, 0x0000,
			ack * 0x02 + res * 0x01,
			sequence,
			# Protocol
			0x0000000000000000,
			type,
			0x0000
		)
	def unpack(data):
		# Unpack header values, keep the relevant
		(size, _, source, target, _, _, _, sequence, _, type, _
			) = Header._struct.unpack(data[:Header.size])
		return (size, source, target, sequence, type)

class DeviceMessage(struct.Struct):
	def __init__(self, type, format=''):
		super(DeviceMessage, self).__init__('<' + format)
		self.type = type
	def pack(self, source, sequence, device=0, ack=0, res=0, *payload):
		return Header.pack(self.type, self.size, source, sequence,
			device, ack, res) + super(DeviceMessage, self).pack(*payload)


# Device messages
GetService 			= DeviceMessage(2)
StateService 		= DeviceMessage(3, 'BI')
GetHostInfo 		= DeviceMessage(12)
StateHostInfo 		= DeviceMessage(13, 'fIIh')
GetHostFirmware 	= DeviceMessage(14)
StateHostFirmware 	= DeviceMessage(15, 'QQHH')
GetWifiInfo 		= DeviceMessage(16)
StateWifiInfo 		= DeviceMessage(17, 'fIIh')
GetWifiFirmware 	= DeviceMessage(18)
StateWifiFirmware 	= DeviceMessage(19, 'QQHH')
GetPower 			= DeviceMessage(20)
SetPower 			= DeviceMessage(21, 'H')
StatePower 			= DeviceMessage(22, 'H')
GetLabel 			= DeviceMessage(23)
SetLabel 			= DeviceMessage(24, '32s')
StateLabel 			= DeviceMessage(25, '32s')
GetVersion 			= DeviceMessage(32)
StateVersion 		= DeviceMessage(33, '3I')
GetInfo 			= DeviceMessage(34)
StateInfo 			= DeviceMessage(35, '3Q')
Acknowledgement 	= DeviceMessage(45)
GetLocation 		= DeviceMessage(48)
StateLocation 		= DeviceMessage(50, '16s32sQ')
GetGroup 			= DeviceMessage(51)
StateGroup 			= DeviceMessage(53, '16s32sQ')
EchoRequest 		= DeviceMessage(58, '64s')
EchoResponse 		= DeviceMessage(59, '64s')

# Light messages
LightGet 		= DeviceMessage(101)
LightSetColor 	= DeviceMessage(102, 'B4HI')
LightState 		= DeviceMessage(107, '4HhH32sQ')
LightGetPower 	= DeviceMessage(116)
LightSetPower 	= DeviceMessage(117, 'HI')
LightStatePower = DeviceMessage(118, 'H')
LightSetWaveform 			= DeviceMessage(103, 'Bb4HIfsB')
LightSetWaveformOptional 	= DeviceMessage(119, 'Bb4HIfsB4b')
LightGetInfrared 			= DeviceMessage(120)
LightStateInfrared 			= DeviceMessage(121, 'H')
LightSetInfrared 			= DeviceMessage(122, 'H')

# Constants in messages (and responses)
SERVICE_UDP		= 1	# the only service type value provided in response to the GetService message
USHRT_MAX		= 65535
POWER_OFF		= 0
POWER_ON		= USHRT_MAX
KELVIN_MIN		= 1500
KELVIN_MAX		= 9000
