#!/usr/bin/env python3

import	fnmatch
import	optparse
import	os

import	psb
import	global_vars


DEBUG=0

def	load_from_psb(psb_filename):

	if not global_vars.options.quiet:
		print("Reading '%s'" % psb_filename)

	# Read in the encrypted/compressed psb data
	psb_data2 = bytearray(open(psb_filename, 'rb').read())

	# Decrypt the psb data using the filename, or --key if provided.
	if global_vars.options.key:
		psb_data1 = psb.unobfuscate_data(psb_data2, global_vars.options.key)
	else:
		psb_data1 = psb.unobfuscate_data(psb_data2, psb_filename)
	if DEBUG:
		open(psb_filename + '.1', 'wb').write(psb_data1)	# compressed

	if psb_filename.endswith('.psb'):
		# ".psb" files are not compressed, use the decrypted data
		psb_data0 = psb_data
	else:
		# Uncompress the psb data
		psb_data0 = psb.uncompress_data(psb_data1)
		if DEBUG:
			open(psb_filename + '.0', 'wb').write(psb_data0)	# raw

	# Check we have a PSB header
	header = psb.HDRLEN()
	header.unpack(psb.buffer_unpacker(psb_data0))
	if header.signature != b'PSB\x00':
		print("PSB header not found")
		return

	# Unpack the PSB structure
	mypsb = psb.PSB()
	mypsb.unpack(psb_data0)

	# Get the base filename without any .psb.m
	base_filename = psb_filename
	b, e = os.path.splitext(base_filename)
	if (e == '.m'):
		base_filename = b
	b, e = os.path.splitext(base_filename)
	if (e == '.psb'):
		base_filename = b

	# Read in the alldata.bin file if it exists
	bin_filename  = base_filename + '.bin'
	if os.path.isfile(bin_filename):
		if global_vars.options.verbose:
			print("Reading file %s" % bin_filename)
		bin_data = bytearray(open(bin_filename, 'rb').read())

		# Split the ADB data into each subfile.
		# The data is in compressed/encrypted form
		mypsb.split_subfiles(bin_data)

	return mypsb


def	load_from_yaml(yaml_filename):

	if not global_vars.options.quiet:
		print("Reading '%s'" % yaml_filename)

	yaml_data = open(yaml_filename, 'rt').read()

	mypsb = psb.PSB()
	mypsb.load_yaml(yaml_data)

	# Read in our subfiles
	# This will update the PSB.fileinfo[] entries with the new lengths etc
	if not global_vars.options.quiet:
		print("Reading subfiles")
	mypsb.read_all_subfiles(os.path.dirname(yaml_filename))

	# Read in our chunk files
	if not global_vars.options.quiet:
		print("Reading chunk files")
	mypsb.read_chunks(os.path.dirname(yaml_filename))

	return mypsb


# Write out the yaml file
def	write_yaml(mypsb):
	filename = global_vars.options.basename + '.yaml'

	if os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return

	if not global_vars.options.quiet:
		print("Writing '%s'" % filename)

	open(filename, 'wt').write(mypsb.print_yaml())

# Write out our PSB
def	write_psb(mypsb):
	filename = global_vars.options.basename + '.psb.m'

	if os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return

	if not global_vars.options.quiet:
		print("Writing '%s'" % filename)

	# Pack our PSB object into the on-disk format
	psb_data0 = mypsb.pack()

	if DEBUG:
		open(filename + '.0', 'wb').write(psb_data0)	# raw

	# Compress the PSB data
	# FIXME - make this optional? some sub .psb files are not
	psb_data1 = psb.compress_data(psb_data0)
	if DEBUG:
		open(filename + '.1', 'wb').write(psb_data1)	# compressed

	# Encrypt the PSB data
	if global_vars.options.key:
		psb_data2 = psb.unobfuscate_data(psb_data1, global_vars.options.key)
	else:
		psb_data2 = psb.unobfuscate_data(psb_data1, filename)
	if DEBUG:
		open(filename + '.2', 'wb').write(psb_data2)	# compressed/encrypted

	# Write out the compressed/encrypted PSB data
	open(filename, 'wb').write(psb_data2)

# Write out our rom file
def	write_rom_file(mypsb):
	filename = global_vars.options.basename + '.rom'
	if os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return

	if not global_vars.options.quiet:
		print("Writing '%s'" % filename)

	mypsb.write_rom_file(filename)

# Write out our subfiles
def	write_subfiles(mypsb):
	if not global_vars.options.quiet:
		print("Writing subfiles")

	base_dir = os.path.dirname(global_vars.options.basename)
	mypsb.write_all_subfiles(base_dir)

# Write out our chunks
def	write_chunks(mypsb):
	if not global_vars.options.quiet:
		print("Writing chunk files")

	base_dir = os.path.dirname(global_vars.options.basename)
	mypsb.write_chunks(base_dir)

# Write out the ADB
def	write_bin(mypsb):

	# Join the subfiles back into a single ADB
	bin_data = mypsb.join_subfiles()
	if bin_data is None:
		return

	filename = global_vars.options.basename + '.bin'

	if os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return

	if not global_vars.options.quiet:
		print("Writing '%s'" % filename)

	open(filename, 'wb').write(bytes(bin_data))


def	replace_rom_file(mypsb):
	if global_vars.options.rom:
		filename = global_vars.options.rom
		if not global_vars.options.quiet:
			print("Reading '%s'" % filename)

		fd = open(filename, 'rb').read()

		mypsb.replace_rom_file(fd)

def	main():

	class MyParser(optparse.OptionParser):
		def format_epilog(self, formatter):
			return self.expand_prog_name(self.epilog)

	parser = MyParser(usage='Usage: %prog [options] <psb filename>', epilog=
"""
-----
Examples:

%prog -b output alldata.psb.m
This will read alldata.psb.m (and alldata.bin) and create output{.psb.m, .bin, .yaml}

%prog -f -b output alldata.psb.m
This will read alldata.psb.m (and alldata.bin) and create output{.psb.m, .bin, .yaml} with all sub-files in output_0000_filename etc

%prog -b output2 -k mysecretkey output.yaml
This will read output.yaml (and output_* files) and create output2{.psb.m, .bin, .yaml}
The file output2.psb.m will be encrypted with 'mysecretkey'
-----
To replace a rom:

%prog -r /path/to/rom -b workdir/alldata originaldir/alldata.psb.m

This will:
1. Read in originaldir/alldata{.psb.m,.bin}

2. Replace the rom with /path/to/rom

3. Create workdir if needed.

4. Write out workdir/alldata{.psb.m, .bin}

""")
	parser.add_option('-q',	'--quiet',	dest='quiet',		help='quiet output',				action='store_true',	default=False)
	parser.add_option('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='store_true',	default=False)
	parser.add_option('-b',	'--basename',	dest='basename',	help='write yaml to BASE.yaml',			metavar='BASE')
	parser.add_option('-f',	'--files',	dest='files',		help='write subfiles to BASE_NNNN_filename',	action='store_true',	default=False)
	parser.add_option('-k',	'--key',	dest='key',		help='encrypt BASE.psb.m using KEY',		metavar='KEY')
	parser.add_option('-r',	'--rom',	dest='rom',		help='replace the rom file with ROM',		metavar='ROM')
	(global_vars.options, args) = parser.parse_args()

	if not args:
		parser.print_help()

	for filename in args:
		if filename.endswith('.psb') or filename.endswith('.psb.m'):
			mypsb = load_from_psb(filename)
		elif filename.endswith('.yaml'):
			mypsb = load_from_yaml(filename)

		if global_vars.options.basename:
			# Make sure the directory exists
			base_dir = os.path.dirname(global_vars.options.basename)
			if base_dir:
				os.makedirs(base_dir, exist_ok = True)

			# Write out the existing rom *before* we replace it
			write_rom_file(mypsb)

			replace_rom_file(mypsb)

			write_psb(mypsb)
			write_bin(mypsb)

			if global_vars.options.files:
				write_yaml(mypsb)
				write_subfiles(mypsb)
				write_chunks(mypsb)


if __name__ == "__main__":
	main()
