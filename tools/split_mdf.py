#!/bin/env python3
# vim: set fileencoding=latin-1

import	sys
import	binascii
import	getopt
import	struct
import	zlib


def	write_mdf_section(filename, data):

	# Write out the raw MDF section
	open(filename, 'wb').write(data)


def	split_mdf_file(filename):

	# Read in the whole file (zelda alldata.bin is 49M)
	data = bytes(open(filename, 'rb').read())

	section = 0
	page_size	= 1024
	start_offset	= 0
	next_offset	= start_offset + page_size
	
	while next_offset < len(data):
		magic	= struct.unpack('>4s', data[next_offset: next_offset +4])[0]

		if (magic == b'MDF\0' or magic == b'mdf\0'):
			# Write out the current section
			print("Section", section, "Offset", start_offset, "Length", next_offset - start_offset)
			write_mdf_section(filename + '.%4.4d' % section, data[start_offset : next_offset])

			# Increment the file section #
			section += 1

			# Move our start pointer to the start of the next MDF section
			start_offset = next_offset

		# Check the next page
		next_offset += page_size
	else:
		print("Section", section, "Offset", start_offset, "Length", next_offset - start_offset)
		write_mdf_section(filename + '.%4.4d' % section, data[start_offset : next_offset])


def	main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
	except getopt.GetoptError as err:
		print(str(err))
		sys.exit(2)

	for o, a in opts:
		if o in ("-h", "--help"):
			print("""
Usage: split_mdf.py [-h] [path/to/alldata.bin]

Splits alldata.bin into each MDF section, written to alldata.bin.0000 etc
""")
			sys.exit(2)
		else:
			assert False, "unhandled option"

	for filename in args:
		split_mdf_file(filename)

if __name__ == "__main__":
	main()
