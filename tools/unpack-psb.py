#!/usr/bin/env python3

import	fnmatch
import	optparse
import	os

import	psb
import	global_vars


DEBUG=1

def	extract_psb(psb_filename):

	if global_vars.options.verbose:
		print("Reading file %s" % psb_filename)

	psb_data = bytearray(open(psb_filename, 'rb').read())
	if DEBUG:
		open(psb_filename + '.2', 'wb').write(psb_data)	# compressed/encrypted

	if global_vars.options.key:
		psb.unobfuscate_data(psb_data, global_vars.options.key)
	else:
		psb.unobfuscate_data(psb_data, psb_filename)
	if DEBUG:
		open(psb_filename + '.1', 'wb').write(psb_data)	# compressed

	psb_data = psb.uncompress_data(psb_data)
	if DEBUG:
		open(psb_filename + '.0', 'wb').write(psb_data)	# raw

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

def	repack_psb(yaml_filename):

	if global_vars.options.verbose:
		print("Reading file %s" % yaml_filename)

	yaml_data = open(yaml_filename, 'rt').read()

	mypsb = psb.PSB()
	mypsb.load_yaml(yaml_data)

	# Read in our chunk files
	mypsb.read_chunks(os.path.dirname(yaml_filename))

	# Read in our subfiles
	# This will update the PSB.fileinfo[] entries with the new lengths etc
	bin_data = mypsb.read_subfiles(os.path.dirname(yaml_filename))

	# Pack our PSB object into the on-disk format
	psb_data = mypsb.pack()

	if global_vars.options.basename:
		base_dir = os.path.dirname(global_vars.options.basename)

		# Make sure the directory exists
		if base_dir:
			os.makedirs(base_dir, exist_ok = True)

		# Write out the yaml file for debugging
		if DEBUG:
			filename = global_vars.options.basename + '.yaml'
			if os.path.isfile(filename):
				print("File '%s' exists, not over-writing" % filename)
			else:
				open(filename, 'wt').write(mypsb.print_yaml())

		psb_filename = global_vars.options.basename + '.psb'

		if DEBUG:
			open(psb_filename + '.0', 'wb').write(psb_data)	# raw

		# Compress the data
		# FIXME - make this optional? some sub .psb files are not
		psb_data = psb.compress_data(psb_data)

		if DEBUG:
			open(psb_filename + '.1', 'wb').write(psb_data)	# compressed

		# Encrypt the data
		if global_vars.options.key:
			psb.unobfuscate_data(psb_data, global_vars.options.key)
		else:
			psb.unobfuscate_data(psb_data, os.path.basename(global_vars.options.basename + '.psb.m'))
		if DEBUG:
			open(psb_filename + '.2', 'wb').write(psb_data)	# compressed/encrypted

		# Write out the compressed/encrypted data
		filename = global_vars.options.basename + '.psb.m'
		if os.path.isfile(filename):
			print("File '%s' exists, not over-writing" % filename)
		else:
			open(filename, 'wb').write(psb_data)

		# Write out the bin data
		if bin_data:
			filename = global_vars.options.basename + '.bin'
			if os.path.isfile(filename):
				print("File '%s' exists, not over-writing" % filename)
			else:
				open(filename, 'wb').write(bytes(bin_data))

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

%prog -b output2 -k mysecretkey output.yaml
This will read output.yaml (and output_* files) and create output2.psb.m and output2.bin
The file output2.psb.m will be encrypted with 'mysecretkey'
-----
To replace a rom:

Extract the PSB:
%prog -f -b workdir/output originaldir/alldata.psb.m
This will create workdir if needed, and overwrite any workdir/output* files which exist.

Replace workdir/output_NNNN_filename with your rom.
The filename will vary, but it should be obvious.
The yaml file contains the offset and length of the original rom, you do NOT need to edit this.

Create a new PSB:
%prog -b otherdir/alldata workdir/output.yaml
This will create a new alldata.psb.m and alldata.bin in otherdir/
The file otherdir/alldata.psb.m will be encrypted with 'alldata.psb.m'
This will create otherdir if needed, but will not overwrite any otherdir/alldata* files which exist.

""")
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	parser.add_option('-b',	'--basename',	dest='basename',	help='write yaml to BASE.yaml',			metavar='BASE')
	parser.add_option('-f',	'--files',	dest='files',		help='write subfiles to BASE_NNNN_filename',	action='store_true',	default=False)
	parser.add_option('-k',	'--key',	dest='key',		help='encrypt BASE.psb.m using KEY',		metavar='KEY')
	(global_vars.options, args) = parser.parse_args()

	if not args:
		parser.print_help()

	for filename in args:
		if fnmatch.fnmatch(filename, '*.psb'):
			extract_psb(filename)
		elif fnmatch.fnmatch(filename, '*.psb.m'):
			extract_psb(filename)
		elif fnmatch.fnmatch(filename, '*.yaml'):
			repack_psb(filename)

if __name__ == "__main__":
	main()
