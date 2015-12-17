#!/usr/bin/env python

import	sys
import	binascii
import	getopt
import	hashlib
import	struct
import	zlib

game_info = (
	{
		'name':		b'Final Fight One',
		'md5':		b'1690b5c5b4e7f00e2011b1fd91ca925d',
		'key':		b'a762bbca183ae6fcb32cccfe58f41ac1562817704674d9e0293f1831809937174a7fbf42b47648c37793690f8faf353d9213e3009e7aecec8f4d2978f6080883e9b8ed1822616aeb18a82fddda046fb1',
		'offset':	31680512,
		'mdf_len':	2459648,
		'rom_len':	4194304,
	},
	{
		'name':		b'Mario & Luigi - Superstar Saga',
		'md5':		b'efb7bf0ae783b1af39d5dc80ea61c4ed',
		'key':		b'2bf3702bf54b24df82c8644004bd10b6be1cf6c534327a58c11ae0a4b55a70bf136a8ce0042e1ca2e462e581ae675eff176459fb0cfb04fa255ac68b31bf89258e3162568757b05419f765a7ee3419cc',
		'offset':	44120064,
		'mdf_len':	6920192,
		'rom_len':	16777216,
	},
	{
		'name':		b'Mega Man Zero',
		'md5':		b'2a57596fbbb46a814231aaf16d8ab603',
		'key':		b'30fb905c1f61c9ab01f92a6c71e2bb24927b7c188e858268105c541f03e0f24f8e7e56c908f1809345789848f80a17bb3c6c4945f10fa2741dd59545f1ce5132b375808e50671485a0013a179d09ddf5',
		'offset':	31289344,
		'mdf_len':	3676160,
		'rom_len':	8388608,
	},
	{
		'name':		b'Mega Man Zero 3',
		'md5':		b'c81a3b4e36762190aaa54ba60d6f5fb9',
		'key':		b'e563ab200ffbfb8e0f2cce9bade0c82f37e25e261eb2169b312cf09f2a3a30f92d372fa2b4b5383fdeadff7b5f8bb51c27a98de145fd518b4cf50e54f23ad894e93615fb58274f7fd5c699a5b3eb05dd',
		'offset':	38205440,
		'mdf_len':	4847616,
		'rom_len':	16777216,
	},
	{
		'name':		b'Mega Man & Bass',
		'md5':		b'49bb5686aa22195e3a682f46d4509cd9',
		'key':		b'35feb2a2c4a6b58db90ac748d434130b14ab3d70355164b1b37392eb881daa35fda5dd11963e7f8060d4087f53772dc16261511de040e5aeba938a2439f001c81468cd05b1b2bd184c11aa689798d414',
		'offset':	32772096,
		'mdf_len':	4806656,
		'rom_len':	8388608,
	},
	{
		'name':		b'Super Ghouls N Ghosts',
		'md5':		b'e27286ad6198e2c75caa07dd51c937f6',
		'key':		b'15070b44ca537ebf19bca19f9fad4f54932ae8b2d54fabb964c8df6e0f5971041f65fa551b3184975333d30a68d524aa87c07dfb3de5ab3fbbc26f50ac2f269835fa0fe63d1efee50a85cb206dc052f9',
		'offset':	32591872,
		'mdf_len':	2291712,
		'rom_len':	4194304,
	},
	{
		'name':		b'Super Mario Advance',
		'md5':		b'e710b59d24961366aa2555f73d1da20e',
		'key':		b'185beca1c044562426c05c1055cee69dc2a1cbae4fbadff752ee632b9437d1ba5bf6724dcfca8020a5455e2a34308c01626c4a253aa66a9f27f949c31e01d2e173bc426a402513ec2c489931e5fda468',
		'offset':	34996224,
		'mdf_len':	2158592,
		'rom_len':	4194304,
	},
	{
		'name':		b'Super Mario Advance 2',
		'md5':		b'068f944ca195e9fc2c7c71b895dbe0e9',
		'key':		b'4223ab619f717c96cb6dfe67d0571b2561e2c58caf00ced7856b72dd320a8b3a544900f55b2ecde723f050bebf75c9ab49d930353c4e2194db247d05ef7ff7e6daea0ebb2fb509267dd6e9d24c9dfe4e',
		'offset':	35704832,
		'mdf_len':	1568768,
		'rom_len':	4194304,
	},
	{
		'name':		b'The Legend of Zelda - The Minish Cap',
		'md5':		b'32fc43935b17a1707a5c8a68b58b495b',
		'key':		b'124a3e853c7cd7ba88f92540ba76254446c33c38d4534d3f8911f8d716b0027c17139fc2cc6486deb256cfea5fcfb43b88002b32a9fa2eba469c805bfea4d58b9b259c6b6d6a63e75dad37b936ee90b0',
		'offset':	41578496,
		'mdf_len':	7985152,
		'rom_len':	16777216,
	},
)

def	getGameInfo(adb_data):
	adb_md5 = hashlib.md5(bytes(adb_data)).hexdigest()
	#print("Info: adb md5 is %s" % adb_md5)

	# Try to match by MD5
	for i in range(len(game_info)):
		gi = game_info[i]
		if (gi['md5'] == adb_md5):
			print("Using %s" % gi['name'])
			return gi
	print("Warning: no matching md5")

def	extractFile(adbFilename):

	# Read in the whole alldata.bin file
	adb_data = open(adbFilename, 'rb').read()
	#print("Read %d bytes" % len(adb_data))

	gi = getGameInfo(adb_data)
	if (not gi):
		return

	gikey	= gi['key']
	gioff	= gi['offset']
	gimdflen	= gi['mdf_len']
	giromlen 	= gi['rom_len']
	#print("Using %s/%d/%d/%d" % (gikey, gioff, gimdflen, giromlen))

	key = bytearray(binascii.unhexlify(gikey))
	key_len = len(key)

	# Take a RW copy of the entire chunk
	data = bytearray(adb_data[gioff : gioff + gimdflen])

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


def	injectFile(adbFilename, injectName):

	# Read in the whole alldata.bin file into a RW array
	adb_data = bytearray(open(adbFilename, 'rb').read())

	gi = getGameInfo(adb_data)
	if (not gi):
		return

	gikey	= gi['key']
	gioff	= gi['offset']
	gimdflen	= gi['mdf_len']
	giromlen	= gi['rom_len']

	key = bytearray(binascii.unhexlify(gikey))
	key_len = len(key)

	# Read in the rom file we want to inject
	new_rom = bytearray(open(injectName, 'rb').read())
	# Check it will fit
	if (len(new_rom) > giromlen):
		print("Uncompressed file %s (%d bytes) too large for injection (max %d bytes)" % (injectName, len(new_rom), giromlen))
		return

	# Pad the new ROM with FFs
	if (len(new_rom) < giromlen):
		new_rom += bytearray(b'\xFF' * (giromlen - len(new_rom)))

	# Compress the new rom
	new_compressed = bytearray(zlib.compress(bytes(new_rom), 9))

	# Check it will fit
	if (len(new_compressed) > gimdflen -8):
		print("Compressed file %s (%d bytes) too large for injection (max %d bytes)" % (injectName, len(new_compressed)+8, gimdflen))
		return

	# Copy in the merged rom, XORed with our key
	for i in range(len(new_compressed)):
		adb_data[gioff +8 + i] = new_compressed[i] ^ key[i % key_len]

	# Zero any space after
	if (len(new_compressed) < gimdflen -8):
		adb_data[gioff +8 + len(new_compressed):gioff + gimdflen] = b'\x00' * (gimdflen - len(new_compressed) -8)

	# Write out the modified ADB
	print("Saving as %s.adb" % injectName)
	open(injectName + '.adb', 'wb').write(adb_data)
	#open(injectName + '.old', 'wb').write(old_rom)
	#open(injectName + '.new', 'wb').write(new_rom)


def	main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hla:e", ["help", "list", "adb=", "extact"])
	except getopt.GetoptError as err:
		print(str(err))
		sys.exit(2)

	showList	= False
	extract		= False
	adbFilename	= ""
	for o, a in opts:
		if o in ("-h", "--help"):
			print(
"""

Usage: inject_gba.py [-h] [-l] [-a path/to/alldata.bin] [-e] [romfile] [romfile]

-h	--help		Print this message.
-l	--list		List known base games.

-a	--adb		Set the path to your alldata.bin file

-e	--extract	Extract rom from the base game alldata.bin file to alldata.bin.gba

[romfile]		Path to one or more uncompressed .gba files to inject.

You must specify the path to the adb file, and the MD5 must match a known file.

The alldata.bin containing the injected file will be written to the same location as the romfile with a .adb suffix
You can then copy the romfile.adb to your content/alldata.bin file.
(Keep a copy of the original!)

The best VC to inject is "The Legend Of Zelda - The Minish Cap"
This takes a 16M rom, with the largest space in the alldata.bin file

I can confirm C.O. Nell looks hawt on the big screen.

""")
			sys.exit(2)
		elif o in ("-a", "--adb"):
			adbFilename	= a
		elif o in ("-e", "--extract"):
			extract = True
		elif o in ("-l", "--list"):
			showList = True
		else:
			assert False, "unhandled option"

	if (showList):
		for i in range(len(game_info)):
			print("Name: %s"	% game_info[i]['name'])
			print("ADB MD5 %s"	% game_info[i]['md5'])
			print("MDF key %s"	% game_info[i]['key'])
			print("MDF offset %d"	% game_info[i]['offset'])
			print("MDF length %d"	% game_info[i]['mdf_len'])
			print("ROM length %d"	% game_info[i]['rom_len'])
			print("")

	if (extract and len(adbFilename)):
		extractFile(adbFilename)

	if (len(adbFilename)):
		for injectName in args:
			injectFile(adbFilename, injectName)

if __name__ == "__main__":
	main()
