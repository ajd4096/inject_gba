#!/usr/bin/env python3

import	binascii
import	ctypes
import	hashlib
import	mt19937
import	optparse
import	os
import	struct
import	sys
import	zlib

class	buffer_packer():
	def __init__(self):
		self._buffer = []

	def __call__(self, fmt, data):
		self._buffer += struct.pack(fmt, data)

	def	tell(self):
		return len(self._buffer)

'''
<	Little endian
>	Big endian
b	signed char
B	unsigned char
H	unsigned 2 bytes
I	unsigned 4 bytes
L	unsigned 4 bytes
Q	unsigned 8 bytes
'''

class	buffer_unpacker():
	def __init__(self, buffer):
		self._buffer = buffer
		self._offset = 0

	def __call__(self, fmt):
		result = struct.unpack_from(fmt, self._buffer, self._offset)
		self._offset += struct.calcsize(fmt)
		return result

	def	iseof(self):
		if self._offset >= len(self._buffer):
			return True
		return False

	def	seek(self, offset):
		if offset >= 0 and offset < len(self._buffer):
			self._offset = offset
		return self._offset

	def	tell(self):
		return self._offset

	def	length(self):
		return len(self._buffer)

	def	data(self):
		return self._buffer[self._offset : ]

	# For debugging, get the next output then reset the offset
	def	peek(self, fmt):
		off = self.tell()
		out = self(fmt)
		self.seek(off)
		return out

# mdf\0
# PSB\0
class	HDRLEN():
	def	__init__(self):
		self.offset0		= 0
		self.offset1		= 0
		self.signature		= []
		self.length		= 0

	def	pack(self, packer):
		packer('>4s',	self.signature)
		packer('<I',	self.length)

	def	unpack(self, unpacker):
		self.offset0		= unpacker.tell()
		self.signature		= unpacker('>4s')[0]
		self.length		= unpacker('<I')[0]
		self.offset1		= unpacker.tell()


'''

From exm2lib
struct PSBHDR {
	unsigned char signature[4];
	unsigned long type;
	unsigned long unknown1;
	unsigned long offset_names;
	unsigned long offset_strings;
	unsigned long offset_strings_data;
	unsigned long offset_chunk_offsets;
	unsigned long offset_chunk_lengths;
	unsigned long offset_chunk_data;
	unsigned long offset_entries;
};


'''

class	PSB():
	def	__init__(self):
		self.header		= PSB_HDR()
		self.str1		= PSB_ARRAY()
		self.str2		= PSB_ARRAY()
		self.str3		= PSB_ARRAY()
		self.names		= []
		self.strings_array	= PSB_ARRAY()
		self.strings		= [] 
		self.chunk_offsets	= PSB_ARRAY()
		self.chunk_lengths	= PSB_ARRAY()
		self.entries		= None
		self.file_data		= []

	def	__str__(self):
		o = "PSB:\n"
		o += str(self.header)
		#o += str(self.str1)
		#o += str(self.str2)
		#o += str(self.str3)
		for i in range(0, len(self.names)):
			o += "Name %d %s\n" % (i, self.names[i])
		#o += "Strings %s\n" % str(self.strings)
		#o += "Strings Data %s\n" % self.strings_data
		for i in range(0, len(self.strings)):
			o += "String %d %s\n" % (i, self.strings[i])
		#o += "Chunk offsets %s\n" % str(self.chunk_offsets)
		#o += "Chunk lengths %s\n" % str(self.chunk_offsets)
		o += "Entries %s\n" % str(self.entries)
		#for i in range(0, self.entries.names.count):
		#	s = self.entries.names.values[i]
		#	o += "%d %d %s\n" % (i, s, self.name[s])
		for i in range(0, len(self.file_data)):
			fi = self.file_data[i]
			o += "%d 0x%X %d %s\n" % (i, fi['offset'], fi['length'], fi['name'])
		return o

	def	unpack(self, unpacker, name):
		if options.verbose:
			print("Parsing header:")
			l = len(unpacker.data())
			print("PSB data length %d 0x%X" % (l, l))

		self.header.unpack(unpacker)
		if options.verbose:
			print(self.header)

		# Read in the arrays of names
		# These are a complex structure used to remove duplicate prefixes of the file names
		unpacker.seek(self.header.offset_names)
		self.str1.unpack(unpacker)
		#print("str1 %d" % self.str1.count)
		self.str2.unpack(unpacker)
		#print("str2 %d" % self.str1.count)
		self.str3.unpack(unpacker)
		#print("str3 %d" % self.str1.count)
		if options.verbose:
			print("Parsing names arrays (%d)" % self.str3.count)
		for i in range(0, self.str3.count):
			s = self.get_name(i)
			self.names.append(s)
			if options.verbose:
				print("Name %d %s" % (i, s))

		# Read in the array of strings
		unpacker.seek(self.header.offset_strings)
		self.strings_array.unpack(unpacker)
		if options.verbose:
			print("Parsing strings array (%d)" % self.strings_array.count)
		# Read in each string
		for i in range(0, self.strings_array.count):
			o = self.strings_array.values[i]
			# Create a python string from the NUL-terminated C-string at offset
			unpacker.seek(self.header.offset_strings_data + o)
			d = unpacker.data();
			for j in range(0, len(d)):
				if d[j] == 0:
					s = d[:j].decode('utf-8')
					self.strings.append(s)
					if options.verbose:
						print("String %d  @0x%X %s" % (i, o, s))
					break

		# This may be empty
		unpacker.seek(self.header.offset_chunk_offsets)
		self.chunk_offsets.unpack(unpacker)
		print("Chunk offsets count %d" % self.chunk_offsets.count)
		for i in range(0, self.chunk_offsets.count):
			print("Chunk offset %d = %d 0x%X" % (i, self.chunk_offsets.values[i], self.chunk_offsets.values[i]))


		# This may be empty
		unpacker.seek(self.header.offset_chunk_lengths)
		self.chunk_lengths.unpack(unpacker)
		print("Chunk lengths count %d" % self.chunk_lengths.count)
		for i in range(0, self.chunk_offsets.count):
			print("Chunk length %d = %d 0x%X" % (i, self.chunk_lengths.values[i], self.chunk_lengths.values[i]))

		# If we have chunk data, split it out
		if options.chunk:
			if self.chunk_offsets.count > 0 and self.header.offset_chunk_data < len(unpacker.data()):
				for i in range(0, self.chunk_offsets.count):
					o = self.chunk_offsets.values[i]
					l = self.chunk_lengths.values[i]
					unpacker.seek(self.header.offset_chunk_data + o)
					d = unpacker.data()[:l]
					open(name + '.chunk.%4.4d' % i, 'wb').write(d)


		# Read in our tree of entries
		self.entries = self.unpack_object(unpacker, "entries", self.header.offset_entries)

	#
	# based on exm2lib get_number()
	#
	def	unpack_object(self, unpacker, name, offset):
		#print(">>> %s @0x%X" % (name, offset))
		unpacker.seek(offset)
		t = unpacker.peek('<B')[0]
		if t >= 1 and t <= 3:
			# from exm2lib & inspection, length = 0, purpose unknown
			t = unpacker('<B')[0]
			v = 0
			if options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return v
		if t == 4:
			# from exm2lib & inspection, length = 0
			# Used as a number, eg offset of file_info chunk
			t = unpacker('<B')[0]
			v = 0
			if options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return v
		elif t >= 5 and t <= 8:
			# from exm2lib, 1 to 4 byte int
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % (t - 4)), 'little')
			if options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return v
		elif t == 9:
			# by inspection, length=5
			# I've only seen these values, all would fit in 4 bytes
			# This suggests a bitmask rather than a negative number
			#    176  4294967042 0xFFFFFF02
			#    176  4294967292 0xFFFFFFFC
			#     44  4294967295 0xFFFFFFFF
			#print(unpacker.peek('<16B'))
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % 5), 'little')
			if options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return v
		elif t == 21:
			# by inspection, length=1, index into strings array
			t = unpacker('<B')[0]
			v = unpacker('<B')[0]
			vs = self.strings[v]
			if options.verbose:
				print(">>> %s @0x%X type %d value %d '%s'" % (name, offset, t, v, vs))
			return vs
		elif t == 22:
			# by inspection, length=2, index into strings array
			t = unpacker('<B')[0]
			v = unpacker('<H')[0]
			vs = self.strings[v]
			if options.verbose:
				print(">>> %s @0x%X type %d value %d '%s'" % (name, offset, t, v, vs))
			return vs
		elif t == 25:
			# by inspection, length=1, index into chunk data
			t = unpacker('<B')[0]
			v = unpacker('<B')[0]
			if options.verbose:
				print(">>> %s @0x%X type %d value chunk %d" % (name, offset, t, v))
			return v
		elif t == 29:
			# by inspection, length=0, purpose unknown, seems to be followed by a type 21
			t = unpacker('<B')[0]
			if options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return None
		elif t == 30:
			# from exm2lib, 4 byte float
			t = unpacker('<B')[0]
			v = unpacker('f')[0]
			if options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return v
		elif t == 31:
			# from exm2lib, 8 byte float
			t = unpacker('<B')[0]
			v = unpacker('d')[0]
			if options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return v
		elif t == 32:
			# from exm2lib, array of offsets
			t = unpacker('<B')[0]
			offsets = PSB_ARRAY()
			offsets.unpack(unpacker)
			v = []
			if options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, offsets.count))
			for i in range(0, offsets.count):
				o = offsets.values[i]
				if options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
				v1 = self.unpack_object(unpacker, name + "|%d" % i, offsets.offset1 + o)
				v.append(v1)
			return v
		elif t == 33:
			# from exm2lib, array of names, array of offsets
			t = unpacker('<B')[0]
			names = PSB_ARRAY()
			names .unpack(unpacker)
			offsets = PSB_ARRAY()
			offsets.unpack(unpacker)
			v = []
			if options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, names.count))
			for i in range(0, names.count):
				ni = names.values[i]
				ns = self.names[ni]
				o = offsets.values[i]
				if options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
				v1 = self.unpack_object(unpacker, name + "|%s" % ns, offsets.offset1 + o)
				v.append((ns, v1))
				if name == 'entries|file_info':
					self.file_data.append({ 'name': ns, 'offset': v1[0], 'length': v1[1]})
			return v
		else:
			print(">>> %s @0x%X" % (name, offset))
			print("Unknown type")
			print(unpacker.peek('<16B'))

	# Copied from exm2lib
	def	get_name(self, index):
		accum = ""

		a = self.str3.values[index];
		b = self.str2.values[a];
		c = 0
		d = 0
		e = 0
		#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))

		while b != 0:
			c = self.str2.values[b]
			d = self.str1.values[c]
			e = b - d
			#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))
			b = c
			accum = chr(e) + accum
		return accum

class	PSB_HDR():
	def	__init__(self):
		self.signature			= []
		self.type			= 0
		self.unknown1			= 0
		self.offset_names		= 0
		self.offset_strings		= 0
		self.offset_strings_data	= 0
		self.offset_chunk_offsets	= 0
		self.offset_chunk_lengths	= 0
		self.offset_chunk_data		= 0
		self.offset_entries		= 0

	def	__str__(self):
		o = "PSB header:\n"
		o += "signature %s\n"			% self.signature
		o += "type 0x%X\n"			% self.type
		o += "unknown1 0x%X\n"			% self.unknown1
		o += "offset_names 0x%X\n"		% self.offset_names
		o += "offset_strings 0x%X\n"		% self.offset_strings
		o += "offset_strings_data 0x%X\n"	% self.offset_strings_data
		o += "offset_chunk_offsets 0x%X\n"	% self.offset_chunk_offsets
		o += "offset_chunk_lengths 0x%X\n"	% self.offset_chunk_lengths
		o += "offset_chunk_data 0x%X\n"		% self.offset_chunk_data
		o += "offset_entries 0x%X\n"		% self.offset_entries
		return o


	def	unpack(self, unpacker):
		self.signature			= unpacker('>4s')[0]
		self.type			= unpacker('<I')[0]
		self.unknown1			= unpacker('<I')[0]
		self.offset_names		= unpacker('<I')[0]
		self.offset_strings		= unpacker('<I')[0]
		self.offset_strings_data	= unpacker('<I')[0]
		self.offset_chunk_offsets	= unpacker('<I')[0]
		self.offset_chunk_lengths	= unpacker('<I')[0]
		self.offset_chunk_data		= unpacker('<I')[0]
		self.offset_entries		= unpacker('<I')[0]

class	PSB_ARRAY():
	def	__init__(self):
		self.offset0		= 0
		self.offset1		= 0
		self.count_length	= 0
		self.count		= 0
		self.value_length	= 0
		self.values		= []

	def	__str__(self):
		o = "Array:\n"
		o += "Offset 0x%X-0x%X\n" % (self.offset0, self.offset1)
		o += "Count Length %d\n" % self.count_length
		o += "Count %d (0x%X)\n" % (self.count, self.count)
		o += "Value Length %d\n" % self.value_length
		o += "Values %s\n" % str(self.values[:5])
		return o

	def	unpack(self, unpacker):
		self.offset0 = unpacker.tell()
		# Get the number of bytes in our count
		# The -12 is copied from asmodean's exm2lib
		self.count_length	= unpacker('<B')[0] -12
		# Get our count
		if self.count_length == 1:
			self.count		= unpacker('<B')[0]
		elif self.count_length == 2:
			self.count		= unpacker('<H')[0]
		else:
			print("Unknown count length %d" % self.count_length)
			assert(False)
		# Get the number of bytes in each value
		# The -12 is copied from asmodean's exm2lib
		self.value_length		= unpacker('<B')[0] -12
		# Read in our list of values
		self.values = [];
		if self.value_length == 1:
			v = unpacker('<%dB' % self.count)
			self.values.extend(v)
		elif self.value_length == 2:
			v = unpacker('<%dH' % self.count)
			self.values.extend(v)
		elif self.value_length == 3:
			for i in range(0, self.count):
				v = int.from_bytes(unpacker('<3B'), 'little')
				self.values.append(v)
		elif self.value_length == 4:
			v = unpacker('<%dI' % self.count)
			self.values.extend(v)
		else:
			print("Unknown value length %d" % self.value_length)
			assert(False)
		self.offset1 = unpacker.tell()


#
# Get the XOR key for the given filename
#
def	get_xor_key(filename):
	fixed_seed	= b'MX8wgGEJ2+M47'	# From m2engage.elf
	key_length	= 0x50

	# Take our game hash_seed (always the same), and append our filename
	hash_seed = fixed_seed + os.path.basename(filename).lower().encode('latin-1')
	if options.verbose:
		print("Using hash seed:\t%s" % hash_seed)

	# Take the MD5 hash of the seed+filename
	hash_as_bytes = hashlib.md5(hash_seed).digest()
	hash_as_longs = struct.unpack('<4I', hash_as_bytes)

	# Initialize our mersenne twister
	mt19937.init_by_array(hash_as_longs)

	# Start with an empty key buffer
	key_buffer = bytearray()

	# Initialize our key from the MT
	while len(key_buffer) < key_length:
		# Get the next 32 bits from our MT-PRNG, as a long
		l = mt19937.genrand_int32();
		# Convert to 4 bytes little-endian
		s = struct.pack('<L', l)

		# Add them to our key buffer
		key_buffer.extend(s)
	if options.verbose:
		print("Using key:\t%s," % binascii.hexlify(bytes(key_buffer)))

	return key_buffer
	

#
# Unobfuscate the data
# This modifies the data in-place
#
def	unobfuscate_data(data, filename):
	header = HDRLEN()
	header.unpack(buffer_unpacker(data))

	if header.signature == b'mdf\x00':
		if options.verbose:
			print("sig=%s" % header.signature)
			print("len=%d (0x%X)" % (header.length, header.length))

		key_buffer = get_xor_key(filename)

		# For each byte after the HDRLEN, XOR in our key
		key_len = len(key_buffer)
		for i in range(len(data) - header.offset1):
			data[i + header.offset1] ^= key_buffer[i % key_len]

#
# Uncompress the data
# This returns a separate set of data
# (Daft python call-by-object)
#
def	uncompress_data(data):
	header = HDRLEN()
	header.unpack(buffer_unpacker(data))

	if header.signature == b'mdf\x00':
		# FIXME - need to test if the data really is compressed
		# (Skip the 8 byte MDF header)
		uncompressed = zlib.decompress(bytes(data[header.offset1 : ]))
		if (len(uncompressed) != header.length):
			print("Warning: uncompressed length %d does not match header length %d" % (len(uncompressed), header.length))
		if not options.quiet:
			print("Uncompressed Length: %d 0x%X" % (len(uncompressed), len(uncompressed)))
		return uncompressed
	else:
		# Return the data as-is
		return data

def	extract_psb(psb_filename, bin_filename):

	if options.verbose:
		print("Reading file %s" % psb_filename)
	psb_file_data = bytearray(open(psb_filename, 'rb').read())

	unobfuscate_data(psb_file_data, psb_filename)
	if options.debug:
		open(psb_filename + '.1', 'wb').write(psb_file_data)

	psb_file_data = uncompress_data(psb_file_data)
	if options.debug:
		open(psb_filename + '.2', 'wb').write(psb_file_data)

	header = HDRLEN()
	header.unpack(buffer_unpacker(psb_file_data))
	if header.signature != b'PSB\x00':
		print("PSB header not found")
		return

	psb = PSB()
	psb.unpack(buffer_unpacker(psb_file_data), psb_filename)


	if not bin_filename:
		print("File count %d" % len(psb.file_data))
		print("-")
		for i in range(0, len(psb.file_data)):
			fi	= psb.file_data[i]
			fn	= "file.%4.4d" % i
			print("File %d" % i)
			print("Name: %s" % fi['name'])
			if not options.quiet:
				print("Offset: 0x%X" % fi['offset'])
				print("Compressed Length: %d (0x%X)" % (fi['length'], fi['length']))
			print("-")
		return

	if len(psb.file_data) == 0:
		print("No files found in PSB")
		return

	if options.verbose:
		print("Reading file %s" % bin_filename)
	bin_file_data = bytearray(open(bin_filename, 'rb').read())

	print("File count %d" % len(psb.file_data))
	print("-")
	for i in range(0, len(psb.file_data)):
		fi	= psb.file_data[i]
		fn	= "file.%4.4d" % i
		print("File %d" % i)
		print("Name: %s" % fi['name'])
		if not options.quiet:
			print("Offset: 0x%X" % fi['offset'])
			print("Compressed Length: %d (0x%X)" % (fi['length'], fi['length']))

		# Get the possibly-encrypted, possibly-compressed data
		o = fi['offset']
		l = fi['length']
		# By inspection, this length does include the 'mdf\0' header
		data = bytearray(bin_file_data[o : o + l])
		if options.debug:
			open(fn + ".0", 'wb').write(data)
		if not options.quiet:
			print("Length: %d" % len(data))

		unobfuscate_data(data, fi['name'])
		if options.debug:
			open(fn + ".1", 'wb').write(data)

		data = uncompress_data(data)
		if options.debug:
			open(fn + ".2", 'wb').write(data)

		# Write out the final file
		open(fn, 'wb').write(data)

		print("-")

def	main():
	# Make our CLI options global so we don't have to pass them around.
	global options

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.epilog

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
Examples:
%prog -v alldata.psb.m\t\t\tVerbosely list the contents of alldata.psb.m

%prog -b alldata.bin alldata.psb.m\tExtract the contents of alldata.bin into file.0000 etc

%prog -v file.NNNN\t\t\tVerbosely list the contents of PSB file.NNNN

%prog -c file.NNNN\t\t\tExtract chunk data from PSB file.NNNN

""")
	parser.add_option('-b', '--bin',	dest='bin',		help='set path to alldata.bin to FILE',		metavar='FILE',		default=None)
	parser.add_option('-c', '--chunk',	dest='chunk',		help='write chunk files',			action='store_true',	default=False)
	parser.add_option('-d', '--debug',	dest='debug',		help='write debug files',			action='store_true',	default=False)
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	(options, args) = parser.parse_args()

	for psb_filename in args:
		extract_psb(psb_filename, options.bin)


if __name__ == "__main__":
	main()
