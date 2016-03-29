#!/usr/bin/env python3

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

import	psb
import	global_vars


def	extract_psb(psb_filename):

	if global_vars.options.verbose:
		print("Reading file %s" % psb_filename)

	psb_file_data = bytearray(open(psb_filename, 'rb').read())

	psb.unobfuscate_data(psb_file_data, psb_filename)

	psb_file_data = psb.uncompress_data(psb_file_data)

	header = psb.HDRLEN()
	header.unpack(psb.buffer_unpacker(psb_file_data))
	if header.signature != b'PSB\x00':
		print("PSB header not found")
		return

	# Get the base filename without any .psb.m
	base_filename = psb_filename
	b, e = os.path.splitext(base_filename)
	if (e == '.m'):
		base_filename = b
	b, e = os.path.splitext(base_filename)
	if (e == '.psb'):
		base_filename = b

	bin_filename  = base_filename + '.bin'
	if os.path.isfile(bin_filename):
		if global_vars.options.verbose:
			print("Reading file %s" % bin_filename)
		bin_file_data = bytearray(open(bin_filename, 'rb').read())
	else:
		bin_file_data = None

	mypsb = psb.PSB(base_filename)
	mypsb.unpack(psb_file_data, bin_file_data)

	if global_vars.options.json:
		j = open(base_filename + '.json', 'wt')
		mypsb.print_json(j)

	if global_vars.options.yaml:
		j = open(base_filename + '.yaml', 'wt')
		mypsb.print_yaml(j)

	if global_vars.options.test:
		psb_data, bin_data = mypsb.pack()
		open(psb_filename + '.out', 'wb').write(psb_data)
		open(bin_filename + '.out', 'wb').write(bin_data)

def	main():

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.expand_prog_name(self.epilog)

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
Examples:

%prog -y alldata.psb.m
This will read alldata.psb.m and alldata.bin, and write out alldata.yaml

%prog -f -y alldata.psb.m
This will read alldata.psb.m and alldata.bin, and write out alldata.yaml with all sub-files in alldata_0000_originalfilename etc

""")
	parser.add_option('-f',	'--files',	dest='files',		help='write subfiles to alldata_NNNN',		action='store_true',	default=False)
	parser.add_option('-j',	'--json',	dest='json',		help='write JSON to alldata.json',		action='store_true',	default=False)
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-t',	'--test',	dest='test',		help='test repacking PSB',			action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	parser.add_option('-y',	'--yaml',	dest='yaml',		help='write YAML to alldata.jaml',		action='store_true',	default=False)
	(global_vars.options, args) = parser.parse_args()

	if not args:
		parser.print_help()

	for psb_filename in args:
		extract_psb(psb_filename)

if __name__ == "__main__":
	main()
