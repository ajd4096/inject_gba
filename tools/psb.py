
import	binascii
import	ctypes
import	hashlib
import	html
import	json
import	mt19937
import	optparse
import	os
import	struct
import	sys
import	zlib

import	global_vars

class	buffer_packer():
	def __init__(self):
		self._buffer = []

	def __call__(self, fmt, data):
		self._buffer += struct.pack(fmt, data)

	def	length(self):
		return len(self._buffer)

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
	def	__init__(self, basename):
		self.basename		= basename
		self.bin_data		= None
		self.header		= PSB_HDR()
		self.names		= []
		self.strings		= [] 
		self.chunks		= []
		self.entries		= None
		self.file_number	= 0
		# Variables used for repacking
		self.new_names		= []
		self.new_strings	= []
		self.new_chunks		= []

	def	__str__(self):
		o = "PSB:\n"
		o += str(self.header)
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
		return o

	def	pack(self):
		packer = buffer_packer()

		# Walk the 'entries' tree
		# This builds our new_names, new_strings, new_chunks lists
		entries_packer = buffer_packer()
		self.pack_object(entries_packer, self.entries)
		entries_data = entries_packer._buffer

		psb_data = bytearray(packer._buffer)
		bin_data = bytearray([])

		return psb_data, bin_data

	def	unpack(self, psb_data, bin_data = None):
		unpacker = buffer_unpacker(psb_data)

		if global_vars.options.verbose:
			print("Parsing header:")
			l = len(unpacker.data())
			print("PSB data length %d 0x%X" % (l, l))

		self.bin_data = bin_data

		self.header.unpack(unpacker)
		if self.header.signature != b'PSB\x00':
			if global_vars.options.debug:
				print("Not a PSB file")
				print(self.header.signature)
			return
		if global_vars.options.verbose:
			print(self.header)

		# Read in the arrays of names
		# These are a complex structure used to remove duplicate prefixes of the file names
		unpacker.seek(self.header.offset_names)
		self.names = self.unpack_names(unpacker)

		# Read in the array of strings
		unpacker.seek(self.header.offset_strings)
		self.strings = self.unpack_strings(unpacker)

		# Read in the array of chunks
		self.chunks = self.unpack_chunks(unpacker)

		# Read in our tree of entries
		self.entries = self.unpack_object(unpacker, '', self.header.offset_entries)

	def	print_json(self, file):
		json.dump(self.entries, file, indent=1)

	#
	# based on exm2lib get_number()
	#
	def	pack_object(self, packer, obj):
		t = obj['type']
		if t >= 1 and t <= 3:
			packer('<B', t)
		elif t == 4:
			packer('<B', t)
		elif t >=5 and t <= 8:
			packer('<B', t)
			v = obj['value']
			packer('<%ds' % (t - 4), v.to_bytes(t - 4, 'little'))
		elif t >= 21 and t <= 22:
			# index into 'strings' array (21 = 1 byte, 22 = 2 bytes)
			v = obj['value']
			for si in range(0, len(self.new_strings)):
				if self.new_strings[si] == v:
					if si < 1 << 8:
						packer('<B', 21)
						packer('<B', si)
					else:
						packer('<B', 22)
						packer('<H', si)
					break
			else:
				self.new_strings.append(v)
				si = len(self.new_strings) -1
				if si < 1 << 8:
					packer('<B', 21)
					packer('<B', si)
				else:
					packer('<B', 21)
					packer('<H', si)
		elif t == 25:
			# Chunk data
			# by inspection, length=1, index into chunk data
			packer('<B', t)
			fn = obj['file']
			fd = open(fn, 'rb').read()
			self.new_chunks.append(fd)
			ci = len(self.new_chunks) - 1
			packer('<B', ci)
		elif t == 30:
			# 4 byte float
			packer('<B', t)
			v = obj['value']
			packer('f', v)
		elif t == 32:
			# array of objects, written as array of offsets, array of objects
			packer('<B', t)
			# Get our list of objects
			v = obj['value']
			# FIXME - if this is a file, use the real file size and track the offset within alldata.bin
			# Build a list of offsets
			list_of_offsets = PSB_ARRAY()
			list_of_objects	= []
			next_offset = 0
			for o in v:
				# Pack our object into a temporary buffer to get the size
				tmp_packer = buffer_packer()
				self.pack_object(tmp_packer, o)
				# Remember our offset
				list_of_offsets.values.append(next_offset)
				# Remember our size for the next offset
				next_offset = tmp_packer.length()
				# Remember our object data
				list_of_objects.append(bytes(tmp_packer._buffer))
			# Pack the list of offsets
			list_of_offsets.pack(packer)
			# Pack the object data
			for oi in range(0, len(list_of_objects)):
				packer('<s', list_of_objects[oi])
		elif t == 33:
			# array of name/object pairs, written as array of name indexes, array of offsets, array of objects
			packer('<B', t)
			# Get our list of objects
			v = obj['value']
			next_offset = 0
			list_of_names   = PSB_ARRAY()
			list_of_offsets = PSB_ARRAY()
			list_of_objects	= []
			for o in v:
				obj_name= o[0]
				obj_data = o[1]
				if global_vars.options.test:
					print(">>> %s %s" % ('name', obj_name))
				# Add the name to our (psb-global) list of names
				self.new_names.append(obj_name)
				obj_name_index = len(self.new_names) -1
				# Pack our object into a temporary buffer to get the size
				tmp_packer = buffer_packer()
				self.pack_object(tmp_packer, obj_data)
				# Remember our name index
				list_of_names.values.append(obj_name_index)
				# Remember our offset
				list_of_offsets.values.append(next_offset)
				# Remember our size for the next offset
				next_offset = tmp_packer.length()
				# Remember our object data
				list_of_objects.append(bytes(tmp_packer._buffer))
			# Pack the list of names
			list_of_names.pack(packer)
			# Pack the list of offsets
			list_of_offsets.pack(packer)
			# Pack the object data
			for oi in range(0, len(list_of_objects)):
				packer('<s', list_of_objects[oi])
		else:
			print("Unknown type")
			print(t)
			assert(False)

	def	unpack_object(self, unpacker, name, offset):
		#print(">>> %s @0x%X" % (name, offset))
		unpacker.seek(offset)
		t = unpacker.peek('<B')[0]
		if t >= 1 and t <= 3:
			# from exm2lib & inspection, length = 0, purpose unknown
			t = unpacker('<B')[0]
			v = 0
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return {'type':t}
		elif t == 4:
			# from exm2lib & inspection, length = 0
			# Used as a number, eg offset of file_info chunk
			t = unpacker('<B')[0]
			v = 0
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return {'type':t, 'value':0}
		elif t >= 5 and t <= 8:
			# from exm2lib, 1 to 4 byte int
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % (t - 4)), 'little')
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return {'type':t, 'value':v}
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
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return {'type':t, 'value':v}
		elif t == 21:
			# by inspection, length=1, index into strings array
			t = unpacker('<B')[0]
			v = unpacker('<B')[0]
			vs = self.strings[v]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d '%s'" % (name, offset, t, v, vs))
			return {'type':t, 'value':vs}
		elif t == 22:
			# by inspection, length=2, index into strings array
			t = unpacker('<B')[0]
			v = unpacker('<H')[0]
			vs = self.strings[v]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d '%s'" % (name, offset, t, v, vs))
			return {'type':t, 'value':vs}
		elif t == 25:
			# by inspection, length=1, index into chunk data
			t = unpacker('<B')[0]
			v = unpacker('<B')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value chunk %d" % (name, offset, t, v))

			# Build the name of our sub-file for the chunk
			diskname = self.getFilename()
			# Write out the chunk data into a file
			if global_vars.options.files:
				open(diskname, "wb").write(self.chunks[v])
			return {'type':t, 'value':v, 'file':os.path.basename(diskname)}
		elif t == 29:
			# by inspection, length=0, purpose unknown, seems to be followed by a type 21
			t = unpacker('<B')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return {'type':t}
		elif t == 30:
			# from exm2lib, 4 byte float
			t = unpacker('<B')[0]
			v = unpacker('f')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return {'type':t, 'value':v}
		elif t == 31:
			# from exm2lib, 8 byte float
			t = unpacker('<B')[0]
			v = unpacker('d')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return {'type':t, 'value':v}
		elif t == 32:
			# from exm2lib, array of offsets of objects, followed by the objects
			t = unpacker('<B')[0]
			offsets = PSB_ARRAY()
			offsets.unpack(unpacker)
			v = []
			if global_vars.options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, offsets.count))
			for i in range(0, offsets.count):
				o = offsets.values[i]
				if global_vars.options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
				v1 = self.unpack_object(unpacker, name + "|%d" % i, offsets.offset1 + o)
				v.append(v1)
			return {'type':t, 'value':(v)}
		elif t == 33:
			if global_vars.options.verbose:
				print(unpacker.peek('<16B'))
			# from exm2lib, array of names, array of offsets
			t = unpacker('<B')[0]
			names = PSB_ARRAY()
			names .unpack(unpacker)
			offsets = PSB_ARRAY()
			offsets.unpack(unpacker)
			v = []
			if global_vars.options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, names.count))
			for i in range(0, names.count):
				ni = names.values[i]
				ns = self.names[ni]
				o = offsets.values[i]
				if global_vars.options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
					print(unpacker.peek('<16B'))
				# Unpack the object at the offset
				v1 = self.unpack_object(unpacker, name + "|%s" % ns, offsets.offset1 + o)
				if name == '|file_info':
					# If we're a file_info list
					# v1['type'] == 32
					# v1['value'] = 2-element list of type/value pairs
					# list index 0 = offset
					# list index 1 = length
					fo = v1['value'][0]['value']
					fl = v1['value'][1]['value']
					# If we have the alldata.bin file, extract the data
					if self.bin_data:
						# Extract the data chunk
						fd = self.bin_data[fo : fo + fl]
						# Unobfuscate the data using the filename for the seed
						unobfuscate_data(fd, ns)
						# Decompress the data
						fd = uncompress_data(fd)
						# Build the name of our sub-file
						diskname = self.getFilename()
						v1['file'] = os.path.basename(diskname)
						# Write out the file.
						if global_vars.options.files:
							open(diskname, "wb").write(fd)
						# Try to parse it as a PSB
						if global_vars.options.parse:
							psb = PSB(diskname)
							psb.unpack(fd)
							# If we have a PSB, add it to the tree
							if psb.header.signature == b'PSB\x00':
								# FIXME - some sub-PSBs have strings but no entries
								v1['entries'] = psb.entries
					v.append((ns, v1))
				else:
					v.append((ns, v1))
			return {'type':t, 'value':(v)}

		else:
			print(">>> %s @0x%X" % (name, offset))
			print("Unknown type")
			print(unpacker.peek('<16B'))

	# Get the next sub-file name
	def	getFilename(self):
		name = "%s_%4.4d" % (self.basename, self.file_number)
		self.file_number += 1
		return name
		
	def	unpack_chunks(self, unpacker):
		chunks		= []
		chunk_offsets	= PSB_ARRAY()
		chunk_lengths	= PSB_ARRAY()

		# Read in our chunk offsets array (this may be empty)
		unpacker.seek(self.header.offset_chunk_offsets)
		chunk_offsets.unpack(unpacker)
		if global_vars.options.verbose:
			print("Chunk offsets count %d" % chunk_offsets.count)
			for i in range(0, chunk_offsets.count):
				print("Chunk offset %d = %d 0x%X" % (i, chunk_offsets.values[i], chunk_offsets.values[i]))


		# Read in our chunk lengths array (this may be empty)
		unpacker.seek(self.header.offset_chunk_lengths)
		chunk_lengths.unpack(unpacker)
		if global_vars.options.verbose:
			print("Chunk lengths count %d" % chunk_lengths.count)
			for i in range(0, chunk_lengths.count):
				print("Chunk length %d = %d 0x%X" % (i, chunk_lengths.values[i], chunk_lengths.values[i]))

		# If we have chunk data, split it out
		if chunk_offsets.count > 0 and self.header.offset_chunk_data < len(unpacker.data()):
			for i in range(0, chunk_offsets.count):
				o = chunk_offsets.values[i]
				l = chunk_lengths.values[i]
				unpacker.seek(self.header.offset_chunk_data + o)
				d = unpacker.data()[:l]
				chunks.append(d)
		return chunks

	def	unpack_names(self, unpacker):
		str1		= PSB_ARRAY()
		str2		= PSB_ARRAY()
		str3		= PSB_ARRAY()
		str1.unpack(unpacker)
		str2.unpack(unpacker)
		str3.unpack(unpacker)

		if global_vars.options.verbose:
			print("Parsing names arrays (%d)" % str3.count)

		names		= []
		for i in range(0, str3.count):
			s = self.get_name(str1, str2, str3, i)
			names.append(s)
			if global_vars.options.verbose:
				print("Name %d %s" % (i, s))

		return names

	# Copied from exm2lib
	def	get_name(self, str1, str2, str3, index):
		accum = ""

		a = str3.values[index];
		b = str2.values[a];
		c = 0
		d = 0
		e = 0
		#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))

		while b != 0:
			c = str2.values[b]
			d = str1.values[c]
			e = b - d
			#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))
			b = c
			accum = chr(e) + accum
		return accum

	def	unpack_strings(self, unpacker):
		strings	= []
		strings_array	= PSB_ARRAY()
		strings_array.unpack(unpacker)

		if global_vars.options.verbose:
			print("Parsing strings array (%d)" % strings_array.count)
		# Read in each string
		for i in range(0, strings_array.count):
			o = strings_array.values[i]
			# Create a python string from the NUL-terminated C-string at offset
			unpacker.seek(self.header.offset_strings_data + o)
			d = unpacker.data();
			for j in range(0, len(d)):
				if d[j] == 0:
					s = d[:j].decode('utf-8')
					strings.append(s)
					if global_vars.options.verbose:
						print("String %d  @0x%X %s" % (i, o, s))
					break
		return strings

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

	def	pack(self, packer):
		self.count = len(self.values)
		# Pack the number of bytes in our length, and the length
		if self.count < 1 << 8:
			packer('<B', 1 + 12)
			packer('<B', self.count)
		else:
			packer('<B', 2 + 12)
			packer('<H', self.count)
		# Find our biggest value
		if self.count:
			max_value = max(self.values)
		else:
			max_value = 0
		# Pack the number of bytes in each value
		if max_value <= 1 << 8:
			packer('<B', 1 + 12)
			for v in self.values:
				packer('<B', v)
		elif max_value < 1 << 16:
			packer('<B', 2 + 12)
			for v in self.values:
				packer('<H', v)
		elif max_value < 1 << 24:
			packer('<B', 3 + 12)
			for v in self.values:
				packer('<3s', v.to_bytes(3, byteorder='little'))
		elif max_value < 1 << 32:
			packer('<B', 4 + 12)
			for v in self.values:
				packer('<I', v)

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
	if global_vars.options.verbose:
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
	if global_vars.options.verbose:
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
		if global_vars.options.verbose:
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
		if global_vars.options.verbose:
			print("Uncompressed Length: %d 0x%X" % (len(uncompressed), len(uncompressed)))
		return uncompressed
	else:
		# Return the data as-is
		return data

