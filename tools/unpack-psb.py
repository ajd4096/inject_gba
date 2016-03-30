#!/usr/bin/env python3

import	fnmatch
import	optparse
import	os

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

	mypsb = psb.PSB()
	mypsb.unpack(psb_file_data, bin_file_data)

	mypsb.print_yaml(open(global_vars.options.basename + '.yaml', 'wt'))


def	main():

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.expand_prog_name(self.epilog)

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
Examples:

%prog -b output alldata.psb.m
This will read alldata.psb.m (and alldata.bin) and create output.yaml

%prog -f -b output alldata.psb.m
This will read alldata.psb.m (and alldata.bin) and create output.yaml with all sub-files in output_0000_filename etc

""")
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	parser.add_option('-b',	'--basename',	dest='basename',	help='write yaml to BASE.yaml',			metavar='BASE')
	parser.add_option('-f',	'--files',	dest='files',		help='write subfiles to BASE_NNNN_filename',	action='store_true',	default=False)
	(global_vars.options, args) = parser.parse_args()

	if not args:
		parser.print_help()

	for filename in args:
		if fnmatch.fnmatch(filename, '*.psb'):
			extract_psb(filename)
		elif fnmatch.fnmatch(filename, '*.psb.m'):
			extract_psb(filename)

if __name__ == "__main__":
	main()
