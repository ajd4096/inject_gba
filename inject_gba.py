#!/usr/bin/env python

import	sys
import	binascii
import	getopt
import	hashlib
import	struct
import	zlib


game_info = {
	'zelda':	{
		'md5':		b'32fc43935b17a1707a5c8a68b58b495b',
		'key':		b'124a3e853c7cd7ba88f92540ba76254446c33c38d4534d3f8911f8d716b0027c17139fc2cc6486deb256cfea5fcfb43b88002b32a9fa2eba469c805bfea4d58b9b259c6b6d6a63e75dad37b936ee90b0',
		'offset':	41578496,
		'length':	7985152,
	},
	'mario':	{
		'md5':		b'efb7bf0ae783b1af39d5dc80ea61c4ed',
		'key':		b'2bf3702bf54b24df82c8644004bd10b6be1cf6c534327a58c11ae0a4b55a70bf136a8ce0042e1ca2e462e581ae675eff176459fb0cfb04fa255ac68b31bf89258e3162568757b05419f765a7ee3419cc',
		'offset':	44120064,
		'length':	6920192,
	},
	'mm03':		{
		'md5':		b'c81a3b4e36762190aaa54ba60d6f5fb9',
		'key':		b'e563ab200ffbfb8e0f2cce9bade0c82f37e25e261eb2169b312cf09f2a3a30f92d372fa2b4b5383fdeadff7b5f8bb51c27a98de145fd518b4cf50e54f23ad894e93615fb58274f7fd5c699a5b3eb05dd',
		'offset':	38205440,
		'length':	4847616,
	},
	'mm0':		{
		'md5':		b'2a57596fbbb46a814231aaf16d8ab603',
		'key':		b'30fb905c1f61c9ab01f92a6c71e2bb24927b7c188e858268105c541f03e0f24f8e7e56c908f1809345789848f80a17bb3c6c4945f10fa2741dd59545f1ce5132b375808e50671485a0013a179d09ddf5',
		'offset':	31289344,
		'length':	3676160,
	},
	'ff1':	{
		'md5':		b'1690b5c5b4e7f00e2011b1fd91ca925d',
		'key':		b'a762bbca183ae6fcb32cccfe58f41ac1562817704674d9e0293f1831809937174a7fbf42b47648c37793690f8faf353d9213e3009e7aecec8f4d2978f6080883e9b8ed1822616aeb18a82fddda046fb1',
		'offset':	31680512,
		'length':	2459648,
	},
	'mmb':	{
		'md5':		b'49bb5686aa22195e3a682f46d4509cd9',
		'key':		b'35feb2a2c4a6b58db90ac748d434130b14ab3d70355164b1b37392eb881daa35fda5dd11963e7f8060d4087f53772dc16261511de040e5aeba938a2439f001c81468cd05b1b2bd184c11aa689798d414',
		'offset':	32772096,
		'length':	4806656,
	},
	'sma':	{
		'md5':		b'e710b59d24961366aa2555f73d1da20e',
		'key':		b'185beca1c044562426c05c1055cee69dc2a1cbae4fbadff752ee632b9437d1ba5bf6724dcfca8020a5455e2a34308c01626c4a253aa66a9f27f949c31e01d2e173bc426a402513ec2c489931e5fda468',
		'offset':	34996224,
		'length':	2158592,
	},
	'sma2':	{
		'md5':		 b'068f944ca195e9fc2c7c71b895dbe0e9',
		'key':		 b'4223ab619f717c96cb6dfe67d0571b2561e2c58caf00ced7856b72dd320a8b3a544900f55b2ecde723f050bebf75c9ab49d930353c4e2194db247d05ef7ff7e6daea0ebb2fb509267dd6e9d24c9dfe4e',
		'offset':	 35704832,
		'length':	 1568768,
	},
	'sgg': {
		'md5':		b'e27286ad6198e2c75caa07dd51c937f6',
		'key':		b'15070b44ca537ebf19bca19f9fad4f54932ae8b2d54fabb964c8df6e0f5971041f65fa551b3184975333d30a68d524aa87c07dfb3de5ab3fbbc26f50ac2f269835fa0fe63d1efee50a85cb206dc052f9',
		'offset':	32591872,
		'length':	2291712,
	},
}

def	getGameInfo(gameName, adb_data):
	adb_md5 = hashlib.md5(bytes(adb_data)).hexdigest()
	#print("Info: adb md5 is %s" % adb_md5)

	# Try to match by MD5
	for gn in game_info.keys():
		gi = game_info[gn]
		if (gi['md5'] == adb_md5):
			return gi
	print("Warning: no matching md5")

	# Try to match by name
	for gn in game_info.keys():
		if (gn == gameName):
			return game_info[gn]
	print("Error: no matching md5, no matching name")

def	extractFile(gameName, adbFilename):

	# Read in the whole alldata.bin file
	adb_data = open(adbFilename, 'rb').read()
	#print("Read %d bytes" % len(adb_data))

	gi = getGameInfo(gameName, adb_data)
	if (not gi):
		return

	gikey	= gi['key']
	gioff	= gi['offset']
	gilen	= gi['length']
	#print("Using %s/%d/%d" % (gikey, gioff, gilen))

	key = bytearray(binascii.unhexlify(gikey))
	key_len = len(key)

	# Take a RW copy of the entire chunk
	data = bytearray(adb_data[gioff : gioff + gilen])

	# For each byte, XOR in our key
	# +8 = skip the MDF magic + size
	for i in range(len(data) -8):
		data[i +8] ^= key[i % key_len]
	#open(adbFilename + '.gba.x', 'wb').write(data[8:])

	# Decompress the unobfuscated data
	raw_data = zlib.decompress(bytes(data[8:]))

	# Write it out
	print("Writing %d bytes to %s.gba" % (len(raw_data), adbFilename))
	open(adbFilename + '.gba', 'wb').write(raw_data)


def	injectFile(gameName, adbFilename, injectName):

	# Read in the whole alldata.bin file into a RW array
	adb_data = bytearray(open(adbFilename, 'rb').read())

	gi = getGameInfo(gameName, adb_data)
	if (not gi):
		return

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
		opts, args = getopt.getopt(sys.argv[1:], "hla:emz", ["help", "list", "adb=", "extact", "ff1", "mario", "mm0", "mm03", "zelda"])
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

Usage: inject_gba.py [-h] [-l] [-a path/to/alldata.bin] [-m -z] [-e] [romfile] [romfile]

-h	--help		Print this message.
-l	--list		List known base games.

-a	--adb		Set the path to your alldata.bin file
			This will try to guess which key/offset/length to use.

If the adb is not recognised, try using the key/offset/length from
	--ff1		Final Fight One
-m	--mario		Mario & Luigi Superstar Saga
	--mm0		Megaman Zero
	--mm03		Megaman Zero 3
-z	--zelda		Zelda Minish Cap

-e	--extract	Extract rom from the base game alldata.bin file to alldata.bin.gba

[romfile]		Path to one or more uncompressed .gba files to inject.

You must specify the path to the adb file.

If the MD5 of the adb file matches a known file it will use the known key/offset/length.

If the MD5 does not match you can try using one of the known key/offset/length sets.
This will work if you are re-injecting into a modified adb, try using -e to verify.

The alldata.bin containing the injected file will be written to the same location as the .gba file with a .adb suffix

The ROM must compress to < 8M (<4M for mm03, <2M for ff1)
Some 16M roms work, some don't.
The other GBA VC titles are all <4M, so not worth using.

I can confirm C.O. Nell looks hawt on the big screen.

""")
			sys.exit(2)
		elif o in ("-a", "--adb"):
			adbFilename	= a
		elif o in ("-e", "--extract"):
			extract = True
		elif o in ("-l", "--list"):
			showList = True
		elif o in ("--ff1"):
			gameName	= 'ff1'
		elif o in ("-m", "--mario"):
			gameName	= 'mario'
		elif o in ("-z", "--zelda"):
			gameName	= 'zelda'
		elif o in ("--mm0"):
			gameName	= 'mm0'
		elif o in ("--mm03"):
			gameName	= 'mm03'
		else:
			assert False, "unhandled option"

	if (showList):
		for gi_name in game_info.keys():
			print("Name %s"		% gi_name)
			print("Key %s"		% game_info[gi_name]['key'])
			print("Offset %d"	% game_info[gi_name]['offset'])
			print("Length %d"	% game_info[gi_name]['length'])

	if (extract and len(adbFilename)):
		extractFile(gameName, adbFilename)

	if (len(adbFilename)):
		for injectName in args:
			injectFile(gameName, adbFilename, injectName)

if __name__ == "__main__":
	main()
