
import	binascii
import	collections
import	ctypes
import	hashlib
import	html
import	mt19937
import	optparse
import	os
import	struct
import	sys
import	yaml
import	zlib

import	global_vars

#
# Define our object classes
#
# Note: we can't use __slots__ to save memory because that breaks __dict__ which we need for serialization
#
class	TypeValue(yaml.YAMLObject):
	yaml_tag = u'!TV'
	def	__init__(self, t, v):
		self.t = t
		self.v = v
	def	__repr__(self):
		return "%s(t=%r, v=%r)" % (self.__class__.__name__, self.t, self.v)

class	NameObject(yaml.YAMLObject):
	yaml_tag = u'!NO'
	def	__init__(self, ni, ns, o):
		self.ni = ni	# index into names[]
		self.ns = ns	# string from names[]
		self.o = o	# object
	def	__repr__(self):
		return "%s(ni=%r, ns=%r, o=%r)" % (self.__class__.__name__, self.ni, self.ns, self.o)

class	FileInfo(yaml.YAMLObject):
	yaml_tag = u'!FI'
	def	__init__(self, i, l, o,):
		self.i = i	# index into files[], filenames[]
		self.l = l	# original length
		self.o = o	# original offset
	def	__repr__(self):
		return "%s(i=%r, l=%r, o=%r)" % (self.__class__.__name__, self.i, self.l, self.o)

#
# get the size of an int in bytes
#
def	getIntSize(v):
	for s in range(1, 8):
		if v < (1 << (8 * s)):
			return s

class	buffer_packer():
	def __init__(self):
		self._buffer = []
		self._offset = 0	# points to the *next* byte to write

	def __call__(self, fmt, data):
		packed_data = struct.pack(fmt, data)
		packed_length = len(packed_data)
		self._buffer[self._offset : self._offset + packed_length] = packed_data
		self._offset += packed_length

	def	length(self):
		return len(self._buffer)

	def	seek(self, offset):
		if len(self._buffer) < offset:
			self._buffer = self._buffer + [0] * (offset - len(self._buffer) + 1)
		self._offset = offset

	def	tell(self):
		return self._offset


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

		self.names		= []	# list of strings indexed by NameObject.ni
		self.strings		= [] 	# list of strings index by Type 21-24
		self.chunkdata		= []	# raw data indexed by Type 25-28
		self.chunknames		= []	# CNNNN filenames for each chunk
		self.entries		= None
		self.filedata		= []	# uncompress/unencrypted data for each file
		self.filenames		= []	# FNNNN filenames for each file_info 
		# Stashed when unpacking, used after to load the file data
		self.fileoffsets	= []
		self.filelengths	= []
		self.filenameindex	= []
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

		# Encrypt/compress/concat our files

		# Write out our dummy header
		#self.header.pack(packer)

		# Pack the array of names
		#self.pack_names(unpacker)

		# Pack the array of strings
		#self.pack_strings(unpacker)

		# Pack the array of chunks
		#self.pack_chunks(unpacker)

		# Pack our tree of entries
		#self.pack_entries(unpacker)

		# Rewrite the header with the correct offsets
		#packer.seek(0)
		#self.header.pack(packer)

		psb_data = bytearray(packer._buffer)
		bin_data = bytearray([])

		return psb_data, bin_data

	def	unpack(self, psb_data, bin_data = None):
		unpacker = buffer_unpacker(psb_data)

		if global_vars.options.verbose:
			print("Parsing header:")
			l = len(unpacker.data())
			print("PSB data length %d 0x%X" % (l, l))

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

		# Extract our subfiles
		if (bin_data):
			self.extractSubFiles(bin_data)

	def	print_yaml(self):
		# Create a top-level dict to dump
		level0 = {
			'names':	self.names,
			'strings':	self.strings,
			'chunknames':	self.chunknames,
			'entries':	self.entries,
			'filenames':	self.filenames,
		}
		return yaml.dump(level0)

	def	load_yaml(self, data):
		# FIXME - use yaml.safe_load
		level0 = yaml.load(data)
		if isinstance(level0, dict):
			self.names		= level0['names']
			self.strings		= level0['strings']
			self.chunknames		= level0['chunknames']
			self.entries		= level0['entries']
			self.filenames		= level0['filenames']
			# Read in our subfiles
			self.filedata = []
			for filename in self.filenames:
				if global_vars.options.verbose:
					print("Reading file '%s'" % filename)
				data = open(filename, 'rb').read()
				self.filedata.append(data)
			# Read in our chunk files
			self.chunkdata = []
			for filename in self.chunknames:
				if global_vars.options.verbose:
					print("Reading chunk '%s'" % filename)
				data = open(filename, 'rb').read()
				self.chunkdata.append(data)

	#
	# based on exm2lib get_number()
	#
	def	pack_object(self, packer, name, obj):
		t = obj.t
		if t >= 1 and t <= 3:
			packer('<B', t)
		elif t >=4 and t <= 12:
			# int, 0-8 bytes
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
			s = getIntSize(v)
			packer('<B', 20 + s)
			packer('<%ds' % s, v.to_bytes(s, 'little'))
		elif t >= 25 and t <= 28:
			# index into 'chunks' array, 1-4 bytes
			s = getIntSize(v)
			packer('<B', 24 + s)
			packer('<%ds' % s, v.to_bytes(s, 'little'))
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
				next_offset += tmp_packer.length()
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
				obj_name_index = o.ni
				obj_name = o.ns
				obj_data = o.o
				if global_vars.options.verbose:
					print("<<< %s %s" % ('name', obj_name))
				# If the type33 is a file_info, each member is a file
				if name == '|file_info':
					assert(type(obj_data) == FileInfo)
					if global_vars.options.verbose:
						print('<<<', obj_data)
					# If we have a file, read it in and fix the offset/length before packing the object
					if self.new_files:
						print("Reading in '%s' for '%s'" % (obj_data.f, obj_name))
						# Read in the raw data
						fd = open(os.path.join(os.path.dirname(global_vars.options.basename), obj_data.f), 'rb').read()
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
		if global_vars.options.verbose:
			print(">>> %s @0x%X" % (name, unpacker.tell()))
			print(unpacker.peek('<16B'))
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
			v = int.from_bytes(unpacker('<%dB' % (t - 5 + 1)), 'little')
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
			return TypeValue(t, v)
		elif t >= 25 and t <= 28:
			# index into chunks array, 1-4 bytes
			t = unpacker('<B')[0]
			v = int.from_bytes(unpacker('<%dB' % (t - 25 + 1)), 'little')
			if global_vars.options.verbose:
				print(">>> %s @0x%X type %d value chunk %d" % (name, offset, t, v))
			assert(v <= len(self.chunkdata))
			return TypeValue(t, v)
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
			# array of objects
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
			# array of name-objects
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
				if name == '|file_info':
					# Build the name of our sub-file
					diskname = self.getFilename(i) + "_" + os.path.basename(ns)

					# If it looks like our rom, output the filename
					if 'system/roms' in ns:
						print("ROM in '%s'" % diskname)

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
					assert(v1.v[1].t >= 4)
					assert(v1.v[1].t <= 12)
					fl = v1.v[1].v

					# Save the filename, offset, length
					self.filenames.append(diskname)
					self.fileoffsets.append(fo)
					self.filelengths.append(fl)
					self.filenameindex.append(ni)

				v.append(NameObject(ni, ns, v1))
			return TypeValue(t, v)

		else:
			print(">>> %s @0x%X" % (name, offset))
			print("Unknown type")
			print(unpacker.peek('<16B'))

	def	extractSubFiles(self, bin_data):
		for i in range(0, len(self.filenames)):
			fo = self.fileoffsets[i]
			fl = self.filelengths[i]
			assert(fo <= len(bin_data))
			assert((fo + fl) <= len(bin_data))

			ni = self.filenameindex[i]
			ns = self.names[ni]

			# Extract the data chunk
			fd = bin_data[fo : fo + fl]
			#open(diskname + '.1', "wb").write(fd)

			# Unobfuscate the data using the original filename for the seed
			unobfuscate_data(fd, ns)
			#open(diskname + '.2', "wb").write(fd)

			# Uncompress the data
			fd = uncompress_data(fd)
			#open(diskname, "wb").write(fd)

			# Save the unobfuscated/uncompressed data to our files array
			self.filedata.append(fd)


	# Get the chunk filename
	def	getChunkFilename(self, chunk_index):
		if global_vars.options.basename:
			name = "%s_C%4.4d" % (os.path.basename(global_vars.options.basename), chunk_index)
		else:
			name = "%s_C%4.4d" % ('BASE', chunk_index)
		return name
		
	# Get the sub-file filename
	def	getFilename(self, file_index):
		if global_vars.options.basename:
			name = "%s_F%4.4d" % (os.path.basename(global_vars.options.basename), file_index)
		else:
			name = "%s_F%4.4d" % ('BASE', file_index)
		return name
		
	def	unpack_chunks(self, unpacker):
		self.chunkdata		= []

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

				# Save the chunk data
				unpacker.seek(self.header.offset_chunk_data + o)
				d = unpacker.data()[:l]
				self.chunkdata.append(d)

				# Save the chunk filename
				self.chunknames.append(self.getChunkFilename(i))

	def	unpack_entries(self, unpacker):
		unpacker.seek(self.header.offset_entries)
		self.entries = self.unpack_object(unpacker, '')

	def	unpack_names(self, unpacker):
		self.names		= []

		unpacker.seek(self.header.offset_names)
		offsets	= self.unpack_object(unpacker, 'offsets')
		tree	= self.unpack_object(unpacker, 'tree')
		names	= self.unpack_object(unpacker, 'names')

		if global_vars.options.verbose:
			print("Parsing names arrays (%d)" % len(names.v))

		for i in range(0, len(names.v)):
			s = self.get_name(offsets, tree, names, i)
			self.names.append(s)
			if global_vars.options.verbose:
				print("Name %d %s" % (i, s))

	# Copied from exm2lib
	def	get_name(self, offsets, tree, names, index):
		accum = ""

		a = names.v[index];
		b = tree.v[a];
		c = 0
		d = 0
		e = 0
		#print("%d %d %d %d %d %c" % (a, b, c, d, e, chr(e)))

		while b != 0:
			c = tree.v[b]
			d = offsets.v[c]
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

