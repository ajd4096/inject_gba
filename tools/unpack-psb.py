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


game_info = (
        {
                'name':         b'WiiU',
	},
);

 
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
		self.entries		= {}
		self.file_info		= None
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
		o += "Entries1 %s\n" % str(self.entries)
		#for i in range(0, self.entries.names.count):
		#	s = self.entries.names.values[i]
		#	o += "%d %d %s\n" % (i, s, self.name[s])
		for i in range(0, len(self.file_data)):
			fi = self.file_data[i]
			o += "%d 0x%X %d %s\n" % (i, fi['offset'], fi['length'], fi['name'])
		return o

	def	unpack(self, unpacker):
		self.header.unpack(unpacker)

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
					s = ctypes.create_unicode_buffer(str(d[:j])).value
					self.strings.append(s)
					if options.verbose:
						print("String %d  @0x%X %s" % (i, o, s))
					break

		# Unused - this is empty
		unpacker.seek(self.header.offset_chunk_offsets)
		self.chunk_offsets.unpack(unpacker)

		# Unused - this is empty
		unpacker.seek(self.header.offset_chunk_lengths)
		self.chunk_lengths.unpack(unpacker)

		# Read in our list of entries
		unpacker.seek(self.header.offset_entries)
		t = unpacker('<B')[0]
		self.entries = self.unpack_array(unpacker, t)

		if (isinstance(self.entries, PSB_OFFSET)):
			print("Entries array contains offsets without names")
		elif (isinstance(self.entries, PSB_NAMEOFFSET)):
			# Main alldata.psb.m has:
			# expire_suffix_list (points to empty list)
			# file_info (one per file)
			# id ??
			# version ??
			if options.verbose:
				print("Names in entries array (%d):" % self.entries.names.count)
				for i in range(0, self.entries.names.count):
					ni = self.entries.names.values[i]
					ns = self.names[ni]
					o = self.entries.offsets.values[i]
					print("> %d 0x%X %s" % (i, o, ns))
			if not options.quiet:
				print("Parsing entries array (%d):" % self.entries.names.count)
			for i in range(0, self.entries.names.count):
				ni = self.entries.names.values[i]
				ns = self.names[ni]
				o = self.entries.offsets.values[i]
				# I know file_info for sure
				if ns == 'file_info':
					print("> %d 0x%X %s" % (i, o, ns))
					unpacker.seek(self.entries.offsets.offset1 + o)
					t = unpacker('<B')[0]
					self.file_info  = self.unpack_array(unpacker, t)
					#print(self.file_info)

					for fii in range(0, self.file_info.names.count):
						fi_offset	= self.file_info.offsets.values[fii]
						fi_ni		= self.file_info.names.values[fii]
						fi_name		= self.names[fi_ni]
						# Each file has a two element array of offsets to packed 'numbers'
						unpacker.seek(self.file_info.offsets.offset1 + fi_offset)
						t = unpacker('<B')[0]
						offsets = self.unpack_array(unpacker, t)
						# The 1st is the offset within ADB
						unpacker.seek(offsets.offsets.offset1 + offsets.offsets.values[0])
						bin_offset = self.unpack_number(unpacker)
						# The 2nd is the compressed length
						unpacker.seek(offsets.offsets.offset1 + offsets.offsets.values[1])
						bin_length = self.unpack_number(unpacker)
						#print("Offset 0x%X" % bin_offset)
						#print("Length %d 0x%X" % (bin_length, bin_length))
						# Append a dict of (filename, offset, length)
						self.file_data.append({ 'name': fi_name, 'offset': bin_offset, 'length': bin_length})
						if options.verbose and not options.bin:
							print("File %d" % fii)
							print("Name: %s" % fi_name)
							print("Offset: 0x%X" % bin_offset)
							print("Compressed Length: %d (0x%X)" % (bin_length, bin_length))
							# get_xor_key will print the seed + key
							get_xor_key(fi_name)
							print('-')
				else:
					print("> %d 0x%X %s" % (i, o, ns))
					print("Danger, Will Robinson! Danger!")
					print("I'm still exploring this entry type.")
					# The rest I'm still exploring
					if ns == 'expire_suffix_list':
						unpacker.seek(self.entries.offsets.offset1 + o)
						#print(unpacker('<16B'))
						t = unpacker('<B')[0]
						entries2 = self.unpack_array(unpacker, t)
						if entries2.offsets.count:
							print(entries2)
					elif ns == 'id':
						unpacker.seek(self.entries.offsets.offset1 + o)
						print(unpacker('<16B'))
					elif ns == 'item':
						unpacker.seek(self.entries.offsets.offset1 + o)
						#print(unpacker('<16B'))
						t = unpacker('<B')[0]
						entries2 = self.unpack_array(unpacker, t)
						if entries2.offsets.count:
							print(entries2)
						for j in range(0, entries2.names.count):
							ni = entries2.names.values[j]
							ns = self.names[ni]
							o = entries2.offsets.values[j]
							unpacker.seek(entries2.offsets.offset1 + o)
							print(">> %d @0x%X %s" % (j, o, ns))
							print(unpacker('<16B'))
					elif ns == 'message':
						unpacker.seek(self.entries.offsets.offset1 + o)
						#print(unpacker('<16B'))
						t = unpacker('<B')[0]
						entries2 = self.unpack_array(unpacker, t)
						if entries2.offsets.count:
							print(entries2)
						for j in range(0, entries2.names.count):
							ni = entries2.names.values[j]
							ns = self.names[ni]
							o = entries2.offsets.values[j]
							unpacker.seek(entries2.offsets.offset1 + o)
							print(">> %d @0x%X %s" % (j, o, ns))
							print(unpacker('<16B'))
					elif ns == 'param':
						unpacker.seek(self.entries.offsets.offset1 + o)
						#print(unpacker('<16B'))
						t = unpacker('<B')[0]
						entries2 = self.unpack_array(unpacker, t)
						if entries2.offsets.count:
							print(entries2)
						for j in range(0, entries2.names.count):
							ni = entries2.names.values[j]
							ns = self.names[ni]
							o = entries2.offsets.values[j]
							unpacker.seek(entries2.offsets.offset1 + o)
							print(">> %d @0x%X %s" % (j, o, ns))
							print(unpacker('<16B'))
					elif ns == 'root':
						unpacker.seek(self.entries.offsets.offset1 + o)
						#print(unpacker('<16B'))
						t = unpacker('<B')[0]
						entries2 = self.unpack_array(unpacker, t)
						if entries2.offsets.count:
							print(entries2)
						for j in range(0, entries2.names.count):
							ni = entries2.names.values[j]
							ns = self.names[ni]
							o = entries2.offsets.values[j]
							unpacker.seek(entries2.offsets.offset1 + o)
							print(">> %d @0x%X %s" % (j, o, ns))
							print(unpacker('<16B'))
					elif ns == 'version':
						unpacker.seek(self.entries.offsets.offset1 + o)
						print(unpacker('<16B'))
						
		

	def	unpack_number(self, unpacker):
		type_to_kind = [0, 1, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7, 8, 8, 8, 8, 9, 9, 0xA, 0xB, 0xC];
		type = unpacker('<B')[0]
		kind = type_to_kind[type]
		v = 0
		if (kind == 1):
			v = 0
		elif kind == 2:
			v = 1
		elif kind == 3:
			n = type - 4
			v = int.from_bytes(unpacker('<%dB' % n), 'little')
		elif kind == 9 and type == 0x1E:
			v = unpacker('f')
		elif kind == 10:
			v = unpacker('d')
		else:
			print("Unsupported packed number 0x%X" % type)
			assert(False)
		return v

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

	def	unpack_array(self, unpacker, t):
		if (t == 0x20):
			v = PSB_OFFSET()
			v.unpack(unpacker)
			return v
		elif (t == 0x21):
			v = PSB_NAMEOFFSET()
			v.unpack(unpacker)
			return v
		else:
			print("Unknown type 0x%X" % t)
			assert(False)
		return None

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

class	PSB_NAMEOFFSET():
	def	__init__(self):
		self.names	= PSB_ARRAY()
		self.offsets	= PSB_ARRAY()

	def	__str__(self):
		o = "Array of name+offset:\n"
		o += "Names %s\n" % str(self.names)
		o += "Offsets %s\n" % str(self.offsets)
		return o

	def	unpack(self, unpacker):
		self.names.unpack(unpacker)
		self.offsets.unpack(unpacker)

class	PSB_OFFSET():
	def	__init__(self):
		self.offsets	= PSB_ARRAY()

	def	__str__(self):
		o = "Array of offsets:\n"
		o += "Offsets %s\n" % str(self.offsets)
		return o

	def	unpack(self, unpacker):
		self.offsets.unpack(unpacker)


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

	if header.signature == b'mdf\x00' and header.length > len(data):
		# (Skip the 8 byte MDF header)
		uncompressed = zlib.decompress(bytes(data[header.offset1 : ]))
		if (len(uncompressed) != header.length):
			print("Warning: uncompressed length %d does not match header length %d" % (len(uncompressed), header.length))
		if not options.quiet:
			print("Uncompressed Length: %d" % len(uncompressed))
		return uncompressed

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
	psb.unpack(buffer_unpacker(psb_file_data))

	if not bin_filename:
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
		# By inspection, this length does include the MDR header
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

""")
	parser.add_option('-b', '--bin',	dest='bin',		help='set path to alldata.bin to FILE',		metavar='FILE',		default=None)
	parser.add_option('-d', '--debug',	dest='debug',		help='write debug files',			action='store_true',	default=False)
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	(options, args) = parser.parse_args()

	for psb_filename in args:
		extract_psb(psb_filename, options.bin)


if __name__ == "__main__":
	main()
