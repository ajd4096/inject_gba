
import	binascii
import	collections
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

#
# Use namedtuples as light-weight OO
#
TypeValue		= collections.namedtuple('TypeValue', 't v')
NamedTypeValue		= collections.namedtuple('NamedTypeValue', 'n t v')
FileOffsetLength	= collections.namedtuple('FileOffsetLength', 'f o l')

def	getIntSize(v):
	for s in range(1, 8):
		if v < (1 << (8 * s)):
			return s

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
		self.files		= []
		# Variables used for repacking
		self.new_names		= None
		self.new_strings	= None
		self.new_chunks		= None
		self.new_files		= None

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

		# Walk the 'entries' tree to build our list of new_names
		# new_names is built in tree order, but the original seems to be sorted
		self.new_names	= []
		self.new_strings = None
		self.new_chunks = None
		self.new_files  = None
		entries_packer = buffer_packer()
		self.pack_object(entries_packer, '', self.entries)

		# Sort the new_names list, then repack the tree to get the correct indexes for the names array
		self.new_names.sort()

		# Walk the 'entries' tree to build our list of new_strings, new_chunks new_files lists
		self.new_strings = []
		self.new_chunks = []
		self.new_files  = []
		entries_packer = buffer_packer()
		self.pack_object(entries_packer, '', self.entries)
		entries_data = entries_packer._buffer

		if global_vars.options.verbose:
			for i in range(0, len(self.new_names)):
				print("Name %d %s" % (i, self.new_names[i]))
			for i in range(0, len(self.new_strings)):
				print("String %d %s\n" % (i, self.new_strings[i]))

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
		self.unpack_names(unpacker)

		# Read in the array of strings
		self.unpack_strings(unpacker)

		# Read in the array of chunks
		self.unpack_chunks(unpacker)

		# Read in our tree of entries
		self.unpack_entries(unpacker)

	def	print_json(self, file):
		json.dump(self.entries, file, indent=1)

	#
	# based on exm2lib get_number()
	#
	def	pack_object(self, packer, name, obj):
		t = obj.t
		if t >= 1 and t <= 3:
			packer('<B', t)
		elif t >=4 and t <= 12:
			# int, 0-8 bytes
			packer('<B', t)
			v = obj.v
			if v == 0:
				packer('<B', 4)
			else:
				s = getIntSize(v)
				packer('<B', 4 + s)
				packer('<%ds' % s, v.to_bytes(s, 'little'))
		elif t >= 13 and t <= 20:
			# array of ints, packed as size of count, count, size of entries, entries[]
			count = len(obj.v)
			s = getIntSize(count)
			packer('<B', 12 + s)
			packer('<%ds' % s, count.to_bytes(s, 'little'))
			# Find our biggest value
			if count:
				max_value = max(obj.v)
			else:
				max_value = 0
			# Pack the number of bytes in each value
			s = getIntSize(max_value)
			packer('<B', s + 12)
			# Pack each value
			for v in obj.v:
				packer('<%ds' % s, v.to_bytes(s, 'little'))
		elif t >= 21 and t <= 24:
			# index into 'strings' array (1-4 bytes)
			if self.new_strings:
				vs = obj.v
				if not vs in self.new_strings:
					self.new_strings.append(vs)
				i = self.new_strings.index(vs)
				s = getIntSize(i)
				packer('<B', 20 + s)
				packer('<%ds' % s, i.to_bytes(s, 'little'))
		elif t >= 25 and t <= 28:
			# index into 'chunks' array, 1-4 bytes
			if self.new_chunks:
				packer('<B', t)
				fn = obj.v
				fd = open(fn, 'rb').read()
				self.new_chunks.append(fd)
				i = len(self.new_chunks) - 1
				s = getIntSize(i)
				packer('<B', 24 + s)
				packer('<%ds' % s, i.to_bytes(s, 'little'))
		elif t == 29:
			# 0 byte float
			packer('<B', t)
		elif t == 30:
			# 4 byte float
			packer('<B', t)
			packer('f', obj.v)
		elif t == 31:
			# 8 byte float
			packer('<B', t)
			packer('d', obj.v)
		elif t == 32:
			# array of objects, written as array of offsets (int), array of objects
			packer('<B', t)
			# Get our list of objects
			v = obj.v
			# Build a list of offsets
			list_of_offsets = []
			list_of_objects	= []
			next_offset = 0
			for i in range(0, len(v)):
				o = v[i]
				# Pack our object into a temporary buffer to get the size
				tmp_packer = buffer_packer()
				self.pack_object(tmp_packer, name + "|%d" % i, o)
				# Remember our offset
				list_of_offsets.append(next_offset)
				# Remember our size for the next offset
				next_offset = tmp_packer.length()
				# Remember our object data
				list_of_objects.append(bytes(tmp_packer._buffer))
			# Pack the list of offsets
			self.pack_object(packer, '', TypeValue(13, list_of_offsets))
			# Pack the object data
			for oi in range(0, len(list_of_objects)):
				packer('<s', list_of_objects[oi])
		elif t == 33:
			# array of name/object pairs, written as array of name indexes, array of offsets, array of objects
			packer('<B', t)
			# Get our list of objects
			v = obj.v
			next_offset = 0
			list_of_names   = []
			list_of_offsets = []
			list_of_objects	= []
			for o in v:
				obj_name = o[0]
				obj_data = o[1]
				if global_vars.options.test:
					print("<<< %s %s" % ('name', obj_name))
				# Add the name to our (psb-global) list of names
				if not obj_name in self.new_names:
					self.new_names.append(obj_name)
				obj_name_index = self.new_names.index(obj_name)
				# If the type33 is a file_info, each member is a file
				if name == '|file_info':
					assert(type(obj_data) == FileOffsetLength)
					print('<<<', obj_data)
					# If we have a file, read it in and fix the offset/length before packing the object
					if self.new_files:
						print("Reading in '%s' for '%s'" % (obj_data.f, obj_name))
						# Read in the raw data
						fd = open(os.path.join(os.path.dirname(self.basename), obj_data.f), 'rb').read()
						print("Raw length %d 0x%X" % (len(fd), len(fd)))
						# Compress the data
						if '.jpg.m' in obj_name:
							fd = compress_data(fd, 0)
						else:
							fd = compress_data(fd, 9)
						print("Compressed length %d 0x%X" % (len(fd), len(fd)))
						# Obfuscate the data using the filename for the seed
						unobfuscate_data(fd, obj_name)
						# Remember the unpadded length
						new_length = len(fd)
						# Pad the data to a multiple of 0x800 bytes
						p = len(fd) % 0x800
						if p:
							fd += b'\x00' * (0x800 - p)
						print("Padded length %d 0x%X" % (len(fd), len(fd)))
						# Add the compressed/encrypted/padded data to our new_files array
						self.new_files.append(fd)
						# Fix up the offset/length
						new_offset = 0
						for i in range(0, len(self.new_files) -1):
							new_offset += len(self.new_files[i])

						if new_offset != obj_data.o:
							print("<<< '%s' -> '%s'" % (obj_data.f, obj_name))
							print("<<< old offset %d 0x%X" % (obj_data.o, obj_data.o))
							print("<<< new offset %d 0x%X" % (new_offset, new_offset))

						if new_length != obj_data.l:
							print("<<< '%s' -> '%s'" % (obj_data.f, obj_name))
							print("<<< old length %d 0x%X" % (obj_data.l, obj_data.l))
							print("<<< new length %d 0x%X" % (new_length, new_length))

						obj_data = TypeValue(32, [TypeValue(4, new_offset), TypeValue(4, new_length)])
					else:
						obj_data = TypeValue(32, [TypeValue(4, obj_data.o), TypeValue(4, obj_data.l)])
				# Pack our object into a temporary buffer to get the size
				tmp_packer = buffer_packer()
				self.pack_object(tmp_packer, name + "|%s" % obj_name, obj_data)
				# Remember our name index
				list_of_names.append(obj_name_index)
				# Remember our offset
				list_of_offsets.append(next_offset)
				# Remember our size for the next offset
				next_offset = tmp_packer.length()
				# Remember our object data
				list_of_objects.append(bytes(tmp_packer._buffer))
			# Pack the list of names
			self.pack_object(packer, '', TypeValue(13, list_of_names))
			# Pack the list of offsets
			self.pack_object(packer, '', TypeValue(13, list_of_offsets))
			# Pack the object data
			for oi in range(0, len(list_of_objects)):
				packer('<s', list_of_objects[oi])
		else:
			print("Unknown type")
			print(t)
			assert(False)

	def	unpack_object(self, unpacker, name):
		#print(">>> %s @0x%X" % (name, offset))
		t = unpacker.peek('<B')[0]
		if t >= 1 and t <= 3:
			# from exm2lib & inspection, length = 0, purpose unknown
			t = unpacker('<B')[0]
			v = 0
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return TypeValue(t, None)
		elif t == 4:
			# int, 0 bytes
			t = unpacker('<B')[0]
			v = 0
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return TypeValue(t, 0)
		elif t >= 5 and t <= 12:
			# int, 1-8 bytes
			t = unpacker('<B')[0]
			s = t - 4
			v = int.from_bytes(unpacker('<%dB' % s), 'little')
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %d 0x%X" % (name, offset, t, v, v))
			return TypeValue(t, v)
		elif t >= 13 and t <= 20:
			# array of ints, packed as size of count, count, size of entries, entries[]
			t = unpacker('<B')[0]
			size_count = t - 12
			count = int.from_bytes(unpacker('<%dB' % size_count), 'little')
			size_entries = unpacker('<B')[0] - 12
			values = []
			for i in range(0, count):
				v = int.from_bytes(unpacker('<%dB' % size_entries), 'little')
				values.append(v)
			return TypeValue(t, values)
		elif t >= 21 and t <= 24:
			# index into strings array, 1-4 bytes
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % (t - 21 + 1)), 'little')
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value string %d" % (name, offset, t, v))
			assert(v <= len(self.strings))
			vs = self.strings[v]
			return TypeValue(t, vs)
		elif t >= 25 and t <= 28:
			# index into chunks array, 1-4 bytes
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % (t - 25 + 1)), 'little')
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value chunk %d" % (name, offset, t, v))
			assert(v <= len(self.chunks))
			# Build the name of our sub-file for the chunk
			diskname = self.getFilename()
			# Write out the chunk data into a file
			if global_vars.options.files:
				open(diskname, "wb").write(self.chunks[v])
			return {'type':t, 'value':v, 'file':os.path.basename(diskname)}
		elif t == 29:
			# float, 0 bytes?
			t = unpacker('<B')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value ?" % (name, offset, t))
			return TypeValue(t, 0.0)
		elif t == 30:
			# float, 4 bytes
			t = unpacker('<B')[0]
			v = unpacker('f')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return TypeValue(t, v)
		elif t == 31:
			# float, 8 bytes
			t = unpacker('<B')[0]
			v = unpacker('d')[0]
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value %f" % (name, offset, t, v))
			return TypeValue(t, v)
		elif t == 32:
			# from exm2lib, array of offsets of objects, followed by the objects
			t = unpacker('<B')[0]
			offsets = self.unpack_object(unpacker, name + '|offsets')
			seek_base = unpacker.tell()
			if global_vars.options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, len(offsets.v)))
			v = []
			for i in range(0, len(offsets.v)):
				o = offsets.v[i]
				if global_vars.options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
				unpacker.seek(seek_base + o)
				v1 = self.unpack_object(unpacker, name + "|%d" % i)
				v.append(v1)
			return TypeValue(t, v)
		elif t == 33:
			if global_vars.options.verbose:
				print(unpacker.peek('<16B'))
			# from exm2lib, array of int name indexes, array of int offsets, followed by objects
			t = unpacker('<B')[0]
			names   = self.unpack_object(unpacker, name + '|names')
			offsets = self.unpack_object(unpacker, name + '|offsets')
			seek_base = unpacker.tell()
			assert(len(names.v) == len(offsets.v))
			if global_vars.options.verbose:
				print(">>> %s @0x%X (%d entries)" % (name, offset, len(names.v)))
			v = []
			for i in range(0, len(names.v)):
				ni = names.v[i]
				ns = self.names[ni]
				o = offsets.v[i]
				if global_vars.options.verbose:
					print(">>> %s @0x%X entry %d:" % (name, offset, i))
					print(unpacker.peek('<16B'))
				# Unpack the object at the offset
				unpacker.seek(seek_base + o)
				v1 = self.unpack_object(unpacker, name + "|%s" % ns)
				# If we're a file_info list, the object is a type 32 collection containing the offset & length values of the file data in alldata.bin
				# If we have the alldata.bin file, extract the data
				if name == '|file_info' and self.bin_data:
					# Build the name of our sub-file
					diskname = self.getFilename()
					# Get the offset and length
					# v1.t == 32
					# v1.v = 2-element list of type/value pairs
					# list index 0 value = offset (type 4-12)
					# list index 1 value = length (type 4-12)
					assert(v1.t == 32)
					assert(len(v1.v) == 2)
					assert(v1.v[0].t >= 4)
					assert(v1.v[0].t <= 12)
					fo = v1.v[0].v
					assert(fo <= len(self.bin_data))
					assert(v1.v[1].t >= 4)
					assert(v1.v[1].t <= 12)
					fl = v1.v[1].v
					assert((fo + fl) <= len(self.bin_data))
					# Extract the data chunk
					fd = self.bin_data[fo : fo + fl]
					#open(diskname + '.1', "wb").write(fd)
					# Add the (possibly compressed/encrypted) data to our files array
					self.files.append(fd)
					# Unobfuscate the data using the filename for the seed
					unobfuscate_data(fd, ns)
					#open(diskname + '.2', "wb").write(fd)
					# Uncompress the data
					fd = uncompress_data(fd)
					# Write out the file.
					if global_vars.options.files:
						print(">>> file '%s'" % ns)
						print(">>> disk '%s'" % os.path.basename(diskname))
						print(">>> len %d" % len(fd))
						open(diskname, "wb").write(fd)
					v.append((ns, FileOffsetLength(os.path.basename(diskname), fo, fl)))
				else:
					v.append((ns, v1))
			return TypeValue(t, v)

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
		self.chunks		= []

		# Read in our chunk offsets array (this may be empty)
		unpacker.seek(self.header.offset_chunk_offsets)
		chunk_offsets = self.unpack_object(unpacker, 'chunk_offsets')
		if global_vars.options.verbose:
			print("Chunk offsets count %d" % len(chunk_offsets.v))
			for i in range(0, len(chunk_offsets.v)):
				print("Chunk offset %d = %d 0x%X" % (i, chunk_offsets.v[i], chunk_offsets.v[i]))


		# Read in our chunk lengths array (this may be empty)
		unpacker.seek(self.header.offset_chunk_lengths)
		chunk_lengths = self.unpack_object(unpacker, 'chunk_lengths')
		if global_vars.options.verbose:
			print("Chunk lengths count %d" % len(chunk_lengths.v))
			for i in range(0, chunk_lengths.count):
				print("Chunk length %d = %d 0x%X" % (i, chunk_lengths.v[i], chunk_lengths.v[i]))

		assert(len(chunk_offsets.v) == len(chunk_lengths.v))

		# If we have chunk data, split it out
		if len(chunk_offsets.v) > 0 and self.header.offset_chunk_data < len(unpacker.data()):
			for i in range(0, len(chunk_offsets.v)):
				o = chunk_offsets.v[i]
				l = chunk_lengths.v[i]
				unpacker.seek(self.header.offset_chunk_data + o)
				d = unpacker.data()[:l]
				self.chunks.append(d)

	def	unpack_entries(self, unpacker):
		unpacker.seek(self.header.offset_entries)
		self.entries = self.unpack_object(unpacker, '')

	def	unpack_names(self, unpacker):
		self.names		= []

		unpacker.seek(self.header.offset_names)
		str1	= self.unpack_object(unpacker, 'str1')
		str2	= self.unpack_object(unpacker, 'str2')
		str3	= self.unpack_object(unpacker, 'str3')

		if global_vars.options.verbose:
			print("Parsing names arrays (%d)" % len(str3.v))

		for i in range(0, len(str3.v)):
			s = self.get_name(str1, str2, str3, i)
			self.names.append(s)
			if global_vars.options.verbose:
				print("Name %d %s" % (i, s))

	# Copied from exm2lib
	def	get_name(self, str1, str2, str3, index):
		accum = ""

		a = str3.v[index];
		b = str2.v[a];
		c = 0
		d = 0
		e = 0
		#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))

		while b != 0:
			c = str2.v[b]
			d = str1.v[c]
			e = b - d
			#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))
			b = c
			accum = chr(e) + accum
		return accum

	def	unpack_strings(self, unpacker):
		self.strings	= []

		unpacker.seek(self.header.offset_strings)
		strings_array	= self.unpack_object(unpacker, 'strings')

		if global_vars.options.verbose:
			print("Parsing strings array (%d)" % len(strings_array.v))
		# Read in each string
		for i in range(0, len(strings_array.v)):
			o = strings_array.v[i]
			# Create a python string from the NUL-terminated C-string at offset
			unpacker.seek(self.header.offset_strings_data + o)
			d = unpacker.data();
			for j in range(0, len(d)):
				if d[j] == 0:
					s = d[:j].decode('utf-8')
					self.strings.append(s)
					if global_vars.options.verbose:
						print("String %d  @0x%X %s" % (i, o, s))
					break

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
# Compress the data and prepend a mdf header
#
def	compress_data(data, level = 9):
	packer = buffer_packer()

	# Create a header
	header = HDRLEN()
	header.signature = b'mdf\x00'
	header.length = len(data)
	header.pack(packer)

	# Compressed the data
	try:
		compressed = zlib.compress(data, level)
		packer('<%ds'% len(compressed), compressed)
	except Exception as e:
		# We could not compress it, use the uncompressed data
		print("Compression failed", e)
		packer('<%ds' % len(data), data)

	return bytearray(packer._buffer)

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

