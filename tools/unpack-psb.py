#!/usr/bin/env python3

import	fnmatch
import	optparse
import	os

import	psb
import	global_vars


def	extract_psb(psb_filename):

	if global_vars.options.verbose:
		print("Reading file %s" % psb_filename)

	psb_data = bytearray(open(psb_filename, 'rb').read())

	psb.unobfuscate_data(psb_data, psb_filename)

	psb_data = psb.uncompress_data(psb_data)

	header = psb.HDRLEN()
	header.unpack(psb.buffer_unpacker(psb_data))
	if header.signature != b'PSB\x00':
		print("PSB header not found")
		return

	mypsb = psb.PSB()
	mypsb.unpack(psb_data)

	# Get the base filename without any .psb.m
	base_filename = psb_filename
	b, e = os.path.splitext(base_filename)
	if (e == '.m'):
		base_filename = b
	b, e = os.path.splitext(base_filename)
	if (e == '.psb'):
		base_filename = b

	if global_vars.options.basename:
		# Make sure the directory exists
		base_dir = os.path.dirname(global_vars.options.basename)
		if base_dir:
			os.makedirs(base_dir, exist_ok = True)

		# Write out the yaml file
		filename = global_vars.options.basename + '.yaml'
		if os.path.isfile(filename):
			print("File '%s' exists, not over-writing" % filename)
		else:
			open(filename, 'wt').write(mypsb.print_yaml())

		if global_vars.options.files:
			# Read in the alldata.bin file if it exists
			bin_filename  = base_filename + '.bin'
			if os.path.isfile(bin_filename):
				if global_vars.options.verbose:
					print("Reading file %s" % bin_filename)
				bin_data = bytearray(open(bin_filename, 'rb').read())

				# Write out our subfiles
				mypsb.write_subfiles(base_dir, bin_data)

			# Write out our chunks
			mypsb.write_chunks(base_dir)


def	main():

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.expand_prog_name(self.epilog)

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
-----
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
