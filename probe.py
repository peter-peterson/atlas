import io         # used to create file streams
import fcntl      # used to access I2C parameters like addresses

import time       # used for sleep delay and timestamps
import string     # helps parse strings
import datetime as dt
import pandas as pd

class AtlasI2C:
	long_timeout = 1.5         	# the timeout needed to query readings and calibrations
	short_timeout = .5         	# timeout for regular commands
	default_bus = 1         	# the default bus for I2C on the newer Raspberry Pis, certain older boards use bus 0
	default_address = 98     	# the default address for the sensor
	current_addr = default_address
	std_addr = {'DO': 97, 'ORP':98, 'PH':99, 'EC':100, 'RTD':102, 'PMP':103}
	probe_data_store = 'probe_store.h5'

	def __init__(self, addresses=[default_address], bus=default_bus, store_data=True):
		# open two file streams, one for reading and one for writing
		# the specific I2C channel is selected with bus
		# it is usually 1, except for older revisions where its 0
		# wb and rb indicate binary read and write
		self.file_read = io.open("/dev/i2c-"+str(bus), "rb", buffering=0)
		self.file_write = io.open("/dev/i2c-"+str(bus), "wb", buffering=0)

		
		#create dict of connected probes and associated readings(all values start at 0.0
		i2c_devices = self.list_i2c_devices()
		probe_to_reading = {}
		for probe, address in std_addr.iteritems():
			if address in i2c_devices:
				probe_to_reading[probe] = 0.0 # add probe to dict

		# merge two dicts for eventual pd.dataframe
		data_dict = {**{'datetime':[dt.datetime.now()]},
					 **{key:[value] for (key, value) in probe_to_reading}}

		self.probe_dataframe = pd.DataFrame(data_dict, columns = data_dict.keys())
		self.probe_dataframe.index = self.probe_dataframe['datetime']
		del df['datetime']



	def set_i2c_address(self, addr):
		# set the I2C communications to the slave specified by the address
		# The commands for I2C dev using the ioctl functions are specified in
		# the i2c-dev.h file from i2c-tools
		I2C_SLAVE = 0x703
		fcntl.ioctl(self.file_read, I2C_SLAVE, addr)
		fcntl.ioctl(self.file_write, I2C_SLAVE, addr)
		self.current_addr = addr

	def write(self, cmd):
		# appends the null character and sends the string over I2C
		cmd += "\00"
		cmd = cmd.encode()
		self.file_write.write(cmd)

	def read(self, num_of_bytes=31):
		# reads a specified number of bytes from I2C, then parses and displays the result
		res = self.file_read.read(num_of_bytes)         # read from the board
		response = list(filter(lambda x: x != '\x00', res))     # remove the null characters to get the response
		if response[0] == 1:             # if the response isn't an error
			# change MSB to 0 for all received characters except the first and get a list of characters
			char_list = map(lambda x: chr(x & ~0x80), list(response[1:]))
			# NOTE: having to change the MSB to 0 is a glitch in the raspberry pi, and you shouldn't have to do this!
			return "Command succeeded " + ''.join(char_list)     # convert the char list to a string and returns it
		else:
			return "Error " + str(response[0])

	def query(self, string):
		# write a command to the board, wait the correct timeout, and read the response
		self.write(string)

		# the read and calibration commands require a longer timeout
		if((string.upper().startswith("R")) or
			(string.upper().startswith("CAL"))):
			time.sleep(self.long_timeout)
		elif string.upper().startswith("SLEEP"):
			return "sleep mode"
		else:
			time.sleep(self.short_timeout)

		return self.read()

	def read_all_probes(query = "R"):
		'''
			Write to probes(query by defualt) and wait, then read from each address, 
			and update reading(s) dict.  Is there a better/cleaner way to do this...?
		'''
		#start_time = dt.datetime.now()
		for probe, address in std_addr.iteritems():
			self.set_i2c_address(address)
			self.write(query)
		time.sleep(self.long_timeout)
		for probe, address in std_addr.iteritems():
			self.set_i2c_address(address)
			self.probe_to_reading[probe] = self.read()
		#end_time = dt.datetime.now()

		self.store_data()

	def store_data(self, max_samples = 60*60):

		now = dt.datetime.now()
		data = {key:[value] for (key, value) in self.probe_to_reading}
		self.probe_dataframe = self.probe_dataframe.append(pd.DataFrame(data, index = [now]))

		if len(self.probe_dataframe) >= max_samples:
			# we write half data to disk and keep the rest in memory for potential data analysis
			save_frame = self.probe_dataframe.tail(max_samples/2)
			self.probe_dataframe = self.probe_dataframe.head(max_samples/2)
			save_frame.to_hd5(probe_data_store)

	def close(self):
		self.file_read.close()
		self.file_write.close()

	def list_i2c_devices(self):
		prev_addr = self.current_addr # save the current address so we can restore it after
		i2c_devices = []
		for i in range (0,128):
			try:
				self.set_i2c_address(i)
				self.read()
				i2c_devices.append(i)
			except IOError:
				pass
		self.set_i2c_address(prev_addr) # restore the address we were using
		return i2c_devices

	def print_i2c_devices(self):
		device_list = self.list_i2c_devices()
		for device_addr in device_list:
			self.set_i2c_address(device_addr)
			info = str.split(device.query("I"), ",")[1]
			print("{0} : {1}".format(device_addr,info))

def main():

device = AtlasI2C()
device.print_i2c_devices()

while True:

	inputt = input("Enter command: ")

	if inputt.upper().startswith("LIST_ADDR"):
		device.print_i2c_devices()

	# continuous polling command automatically polls the board
	elif inputt.upper().startswith("RUN"):

		try:
			while True:
				device.read_all_probes()
				print(device.probe_to_reading)
		except KeyboardInterrupt: 		# catches the ctrl-c command, which breaks the loop above
			print("Continuous polling stopped")

	# if not a special keyword, pass commands straight to board
	else:
		if len(inputt) == 0:
			print ("Please input valid command.")
		else:
			try:
				print(device.query(inputt))
			except IOError:
				print("Query failed \n - Address may be invalid, use List_addr command to see available addresses")



 
#Stanard Probe Addresses
#EZO DO: 97 (0x61)
#EZO ORP: 98 (0x62)
#EZO pH: 99 (0x63)
#EZO EC: 100 (0x64)
#EZO RTD: 102 (0x66)
#EZO PMP: 103 (0x67)
