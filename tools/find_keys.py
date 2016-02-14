#!/usr/bin/env python
# vim: set fileencoding=latin-1
#
# The basic principle:
# plain-text XOR key = cipher-text
# cipher-text XOR plain-text = key
#
# We have the plain text (or very similar).
# They are standard GBA roms compressed with zlib deflate level 9.
# This tool takes an uncompressed GBA rom, compresses it, and XORs it against the cipher-text.
# We then use a few heuristics to look for the key in the output.

import	sys
import	binascii
import	getopt
import	hashlib
import	os
import	struct
import	zlib


def	get_largest_section(filename):
	print("Splitting file %s" % filename)

	# Read in the whole file (zelda alldata.bin is 49M)
	data = bytes(open(filename, 'rb').read())
	
	# Build a list of all the section (offset, length) tuples
	sections = []

	previous_offset = 0
	for offset in range(0, len(data), 1024):
		magic	= struct.unpack('>4s', data[offset: offset +4])[0]
		if (magic == b'MDF\0' or magic == b'mdf\0'):
			if (offset != previous_offset):
				sections.append((previous_offset, offset - previous_offset))
				previous_offset = offset
	else:
		if (offset != previous_offset):
			sections.append((previous_offset, offset - previous_offset))
	
	# Find the largest section
	largest_section = max(sections, key = lambda x: x[1])

	# Print some stats, formatted to paste into inject_gba.py
	print("'md5': b'%s'," % hashlib.md5(data).hexdigest())
	print("'offset': %d," % largest_section[0])
	print("'mdf_len': %d," % largest_section[1])
	print("'adb_len': %d," % len(data))
	# Get the MD5 of the ADB with the largest section zero'd
	adb_copy = bytearray(data)
	adb_copy[largest_section[0] : largest_section[0] + largest_section[1]] = bytearray(b'\x00' * largest_section[1])
	print("'md5z': b'%s'," % hashlib.md5(bytes(adb_copy)).hexdigest())

	return data[largest_section[0] : largest_section[0] + largest_section[1]]


# Find the most common character at each repeated key position
# The plain-text (compressed rom) has more 00 and FF than anything else.
# If the plain text is almost right, the correct key byte is 2x-3x more common than any other character.
# If that fails, try XORing each byte with FF one by one
# This makes the search space 2**80, so far I've been lucky.
def	key_search_most_common(data, search_length):

	# Remove any trailing zeros
	for i in range(len(data) -1, 0, -1):
		if (data[i]):
			break
	trimmed_data = data[:i +1]

	guess_key = [0] * search_length

	for ko in range(search_length):
		count0 = [0] * 256
		for i in range(0, len(trimmed_data), search_length):
			count0[data[ko + i]] += 1
		mc = count0[0]
		for i in range(256):
			if (count0[i] > mc):
				mc = count0[i]
				guess_key[ko] = i

	return guess_key

def	key_search_consecutive_2(data, key_length_min, key_length_max):
	# Look for shortest possible key length
	for possible_length in range(key_length_min, key_length_max +1):
		for co in range(possible_length):
			# If the 1st & 2nd consecutive keys differ, try the next length
			if (data[co] != data[co + possible_length]):
				break
		else:
			return data[:possible_length]

def	key_search_consecutive_3(data, key_length_min, key_length_max):
	# Look for shortest possible key length
	for possible_length in range(key_length_min, key_length_max +1):
		for co in range(possible_length):
			# If the 1st & 2nd consecutive keys differ, try the next length
			if (data[co] != data[co + possible_length]):
				break
			# If the 1st & 3rd consecutive keys differ, try the next length
			if (data[co] != data[co + possible_length *2]):
				break
		else:
			return data[:possible_length]

# Suffix tree sort
# This is robust, but slow
def	key_search_suffix_sort(data, key_length_min, key_length_max):

	# To save time, only search the first N key lengths
	max_search_len = min(len(data), key_length_max * 10)
	max_search_len = len(data) - key_length_max * 3

	# Build a list of starting points
	suffixes = [0] * (max_search_len - key_length_max*3)
	for i in range(0, len(suffixes)):
		suffixes[i] = i

	# Insertion sort the starting points
	for i in range(1, len(suffixes)):
		j = i
		while j > 0:
			this_str = suffixes[j]
			prev_str = suffixes[j-1]
			for co in range(key_length_max):
				if (data[prev_str + co] < data[this_str + co]):
					# previous < this, we can continue the outer loop
					j = 0	# Exit the while loop
					break
				if (data[prev_str + co] > data[this_str + co]):
					# previous > this, we can stop scanning this string and swap them
					(suffixes[j-1], suffixes[j]) = (this_str,prev_str)
					break
			else:
				# Strings are equal up to key_length_max
				# Check for the shortest consecutive keys
				shortest = key_search_consecutive_3(data[this_str:], key_length_min, key_length_max)
				if (shortest):
					# Rotate relative to the start point
					double = shortest + shortest
					start_offset = this_str % len(shortest)
					start = double[start_offset : start_offset +len(shortest)]
					return start
			j -= 1


def	test_file(cipher_data, filename):

	print("Reading uncompressed plain-text from %s" % filename)
	file_data = open(filename, 'rb').read()

	if (len(file_data) > len(cipher_data)):
		print("Uncompressed plain-text is too large")
	else:
		print("Trying uncompressed plain-text")
		found_key = test_data_block(cipher_data, bytearray(file_data))
		if (found_key):
			if test_key(cipher_data, found_key):
				return True

	# Compress our file at each compression_level
	for compression_level in range(9, 0, -1):
		print("Compressing plain-text at level %d" % compression_level)
		compressed_data = bytearray(zlib.compress(file_data, compression_level))

		# For manual analysis, save each level
		#open(filename + '.%d' % compression_level, 'wb').write(compressed_data)

		# If it is larger than the chunk, the level is wrong
		# Because we go best -> worst, give up
		if (len(compressed_data) > len(cipher_data)):
			print("File %s compression level %s is too large" % (filename, compression_level))
			break

		found_key = test_data_block(cipher_data, compressed_data)
		if (found_key):
			print("Found possible key, validating")
			if test_key(cipher_data, found_key):
				return True
	return False
			
def	test_key(cipher_data, key):
	xor_data = bytearray(cipher_data)
	for i in range(len(xor_data)):
		xor_data[i] ^= key[i % len(key)]
	# Try to uncompress it
	try:
		plain_data = zlib.decompress(bytes(xor_data))
	except:
		pass
	else:
		# It worked - return the key
		print("'key': b'%s'," % binascii.hexlify(bytes(bytearray(key))))
		print("'rom_len': %d," % len(plain_data))
		return True
	return False


def	test_data_block(cipher_data, plain_data):

	xor_data = [0] * (len(cipher_data))	# Need the full length

	#xor_data = [0] * (10000)
	# Try each offset
	for offset in range(0, 1):
		print("XOR-ing cipher-text with compressed plain-text at offset %d" % offset)
		cd = bytearray(cipher_data)
		for i in range(0, min(len(xor_data), len(plain_data)-offset)):
			xor_data[i] = cd[i] ^ plain_data[i + offset]
		#print("%3d" % offset, bytes(xor_data)[0:30])

		print("Check for three consecutive keys")
		found_key = key_search_consecutive_3(xor_data, 40, 256)
		if (found_key):
			return found_key

		print("Try suffix tree search")
		found_key = key_search_suffix_sort(xor_data[:8192], 40, 256)
		if (found_key):
			return found_key

		print("Guess from most common chars")
		found_key = key_search_most_common(xor_data, 80)
		if (found_key):
			return found_key


def	main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "ha:", ["help"])
	except getopt.GetoptError as err:
		print(str(err))
		sys.exit(2)

	adbFilename	= ""
	for o, a in opts:
		if o in ("-h", "--help"):
			print("""
Usage: find_keys.py [-h] [-a path/to/alldata.bin] [romfile] [romfile]

""")
			sys.exit(2)
		elif o in("-a", "--adb"):
			adbFilename = a
		else:
			assert False, "unhandled option"

	# Get the largest MDF section from the alldata.bin file
	largest_section = get_largest_section(adbFilename)

	# For each GBA rom file, try to match it
	for filename in args:
		if test_file(largest_section[8:], filename):
			exit(0)

if __name__ == "__main__":
	main()
