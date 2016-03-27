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

	if bin_filename:
		if options.verbose:
			print("Reading file %s" % bin_filename)
		bin_file_data = bytearray(open(bin_filename, 'rb').read())
	else:
		bin_file_data = None

	psb = PSB()
	psb.unpack(buffer_unpacker(psb_file_data), '', bin_file_data)

	if options.json:
		j = open(options.json, 'wt')
		psb.print_json(j)

def	main():
	# Make our CLI options global so we don't have to pass them around.
	global options

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.expand_prog_name(self.epilog)

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
Examples:

%prog -j output.json -b alldata.bin alldata.psb.m
This will convert the PSB tree into JSON, and write out all sub-files into ouput.json_0000 etc

""")
	parser.add_option('-b', '--bin',	dest='bin',		help='set path to alldata.bin to FILE',		metavar='FILE',		default=None)
	parser.add_option('-d', '--debug',	dest='debug',		help='write debug files',			action='store_true',	default=False)
	parser.add_option('-j',	'--json',	dest='json',		help='write JSON to FILE',			metavar='FILE',		default=None)
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	(options, args) = parser.parse_args()

	if not args:
		parser.print_help()

	for psb_filename in args:
		extract_psb(psb_filename, options.bin)


if __name__ == "__main__":
	main()
