#!/usr/bin/env python

import	sys
import	binascii
import	getopt
import	struct
import	zlib

game_info = {
	'zelda':	{
		'key':		b'124a3e853c7cd7ba88f92540ba76254446c33c38d4534d3f8911f8d716b0027c17139fc2cc6486deb256cfea5fcfb43b88002b32a9fa2eba469c805bfea4d58b9b259c6b6d6a63e75dad37b936ee90b0',
		'offset':	41578496,
		'length':	7985152,
	},
	'mario':	{
		'key':		b'2bf3702bf54b24df82c8644004bd10b6be1cf6c534327a58c11ae0a4b55a70bf136a8ce0042e1ca2e462e581ae675eff176459fb0cfb04fa255ac68b31bf89258e3162568757b05419f765a7ee3419cc',
		'offset':	44120064,
		'length':	6920192,
	},
	'mm03':		{
		'key':		b'e563ab200ffbfb8e0f2cce9bade0c82f37e25e261eb2169b312cf09f2a3a30f92d372fa2b4b5383fdeadff7b5f8bb51c27a98de145fd518b4cf50e54f23ad894e93615fb58274f7fd5c699a5b3eb05dd',
		'offset':	38205440,
		'length':	4847616,
	},
}


def	extractFile(gameName, adbFilename):
	if (not gameName in game_info):
		print("Game %s not found" % gameName)
		return

	gi = game_info[gameName]
	gikey	= gi['key']
	gioff	= gi['offset']
	gilen	= gi['length']

	key = bytearray(binascii.unhexlify(gikey))
	key_len = len(key)

	# Read in the whole alldata.bin file
	adb_data = open(adbFilename, 'rb').read()

	# Take a RW copy of the entire chunk
	data = bytearray(adb_data[gioff : gioff + gilen])

	# For each byte, XOR in our key
	# +8 = skip the MDF magic + size
	for i in range(len(data) -8):
		data[i +8] ^= key[i % key_len]

	# Decompress the unobfuscated data
	raw_data = zlib.decompress(bytes(data[8:]))

	# Write it out
	open(adbFilename + '.gba', 'wb').write(raw_data)


def	injectFile(gameName, adbFilename, injectName):
	if (not gameName in game_info):
		print("Game %s not found" % gameName)
		return
	
	gi = game_info[gameName]
	gikey	= gi['key']
	gioff	= gi['offset']
	gilen	= gi['length']

	key = bytearray(binascii.unhexlify(gikey))
	key_len = len(key)

	# Read in the rom file we want to inject
	rom_data = bytearray(open(injectName, 'rb').read())

	# Compress the data
	compressed_data = bytearray(zlib.compress(bytes(rom_data), 9))

	# Check it will fit
	if (len(compressed_data) > gilen -8):
		print("Compressed file too large for %s" % injectName)
		return

	# Read in the whole alldata.bin file into a RW array
	adb_data = bytearray(open(adbFilename, 'rb').read())

	# Insert the MDF header
	adb_data[gioff : gioff +4] = b'mdf\0'

	# Insert our injected file size (uncompressed)
	# NOTE - the original is using little-endian! Heathens!
	adb_data[gioff +4 : gioff +8] = struct.pack('<i', len(rom_data))

	# For each byte, XOR in our key
	for i in range(len(compressed_data)):
		adb_data[gioff +8 + i] = compressed_data[i] ^ key[i % key_len]

	# Pad with zeros
	adb_data[gioff +8 + len(compressed_data) : gioff + gilen] = b'\00' * (gilen -8 - len(compressed_data))

	# Write out the modified ADB
	print("Saving as %s.adb" % injectName)
	open(injectName + '.adb', 'wb').write(adb_data)


def	main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hlem:z:", ["help", "list", "extact", "mario=", "mm03=", "zelda="])
	except getopt.GetoptError as err:
		print(str(err))
		sys.exit(2)

	showList	= False
	extract		= False
	gameName	= ""
	adbFilename	= ""
	for o, a in opts:
		if o in ("-h", "--help"):
			print(
"""

Usage: inject_gba.py [-h] [-l] [-m path/to/mmss/alldata.bin | -z path/to/zelda/alldata.bin] [-e] [romfile] [romfile]

-h	--help		Print this message.
-l	--list		List known base games.

-m	--mario		Set the path to your Mario & Luigi Superstar Saga alldata.bin file
-z	--zelda		Set the path to your Zelda Minish Cap alldata.bin file
	--mm03		Set the path to your Megaman Zero 3 alldata.bin file

-e	--extract	Extract rom from the base game alldata.bin file to alldata.bin.gba
[romfile]		Path to one or more uncompressed .gba files.

You must specify either -m or -z
The alldata.bin containing the injected file will be written to the same location as the .gba file

The ROM must compress to < 8M.
Some 16M roms work, some don't.

I can confirm C.O. Nell looks hawt on the big screen.

""")
			sys.exit(2)
		elif o in ("-e", "--extract"):
			extract = True
		elif o in ("-l", "--list"):
			showList = True
		elif o in ("-m", "--mario"):
			gameName	= 'mario'
			adbFilename	= a
		elif o in ("-z", "--zelda"):
			gameName	= 'zelda'
			adbFilename	= a
		elif o in ("--mm03"):
			gameName	= 'mm03'
			adbFilename	= a
		else:
			assert False, "unhandled option"

	if (showList):
		for gi_name in game_info.keys():
			print("Name %s"		% gi_name)
			print("Key %s"		% game_info[gi_name]['key'])
			print("Offset %d"	% game_info[gi_name]['offset'])
			print("Length %d"	% game_info[gi_name]['length'])

	if (len(gameName) and len(adbFilename)):
		if (extract):
			extractFile(gameName, adbFilename)

		for injectName in args:
			injectFile(gameName, adbFilename, injectName)

if __name__ == "__main__":
	main()
