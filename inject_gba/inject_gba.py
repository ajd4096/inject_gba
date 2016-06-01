#!/usr/bin/env python3

import	argparse
import	os
import	shutil
import	sys
import	easygui	as eg

import	inject_gba.global_vars	as global_vars
import	inject_gba.psb		as psb

##################################################
#
#	load_from_psb
#
#	Read in a .psb.m file into our PSB object
#	If there is a matching alldata.bin file, read that in too
#

def	load_from_psb(psb_filename):
	if not psb_filename:
		return None

	if global_vars.verbose:
		print("Reading '%s'" % psb_filename)

	# Read in the encrypted/compressed psb data
	psb_data2 = bytearray(open(psb_filename, 'rb').read())

	# Decrypt the psb data using the filename as the key
	psb_data1 = psb.unobfuscate_data(psb_data2, psb_filename)
	if global_vars.verbose > global_vars.debug_level:
		open(psb_filename + '.1', 'wb').write(psb_data1)	# compressed

	if psb_filename.endswith('.psb'):
		# ".psb" files are not compressed, use the decrypted data
		psb_data0 = psb_data2
	else:
		# Uncompress the psb data
		psb_data0 = psb.uncompress_data(psb_data1)
		if global_vars.verbose > global_vars.debug_level:
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
	# '.psb.m' isn't a single extension :(
	if psb_filename.endswith('.psb'):
		base_filename = psb_filename[:-len('.psb')]
	elif psb_filename.endswith('.psb.m'):
		base_filename = psb_filename[:-len('.psb.m')]
	else:
		return

	# Read in the alldata.bin file if it exists
	bin_filename  = base_filename + '.bin'
	if os.path.isfile(bin_filename):
		if global_vars.verbose:
			print("Reading file %s" % bin_filename)
		bin_data = bytearray(open(bin_filename, 'rb').read())

		# Split the ADB data into each subfile.
		# The data is in compressed/encrypted form
		mypsb.split_subfiles(bin_data)

	return mypsb

##################################################
#
#	read_rom
#
#	This reads in a ROM file, adds prefix/padding, and injects it into the psb object
#

def	read_rom(mypsb, filename):
	if not mypsb or not filename:
		return

	if global_vars.verbose:
		print("Reading '%s'" % filename)

	prefix = b''
	padding = b''

	if global_vars.options.prefix:
		prefix = open(global_vars.options.prefix, 'rb').read()

	new_data = open(filename, 'rb').read()
	old_data = mypsb.extract_rom()

	if (len(prefix) + len(new_data)) < len(old_data):
		if global_vars.options.pad00:
			padding = b'\x00' * (len(old_data) - len(new_data) - len(prefix))
		elif global_vars.options.padFF:
			padding = b'\xFF' * (len(old_data) - len(new_data) - len(prefix))

	mypsb.replace_rom_file(prefix + new_data + padding)


##################################################
#
#	release_the_kraken
#
#	This is the main read/write logic
#

def	release_the_kraken(inpsb, outrom, inrom, outpsb):
	# We must have an inpsb (this should be enforced by the parser)
	if not inpsb:
		parser.print_help()
		exit(1)

	mypsb = load_from_psb(inpsb)

	# If we have outrom, write it out
	if outrom:
		write_rom(mypsb, outrom)

	# If we have inrom, read it in
	if inrom:
		read_rom(mypsb, inrom)

	# If we have outpsb, write it out
	if outpsb:
		write_psb(mypsb, outpsb)
		write_bin(mypsb, outpsb)

##################################################
#
#	rename_backup
#
#	Optionally create a backup file, and check if we are over-writing a file
#
#	Count the TOCTOUs!
#

def	rename_backup(filename):

	# Optionally create a .bak if none exist
	if global_vars.options.create_backup and os.path.isfile(filename) and not os.path.isfile(filename + '.bak') and not os.path.isdir(filename + '.bak') and not os.path.ismount(filename + '.bak'):
		os.rename(filename, filename + '.bak')

	# Optionally refuse to overwrite the existing file
	if not global_vars.options.allow_overwrite and os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return False

	return True

##################################################
#
#	write_bin
#
#	Write out the alldata.bin file
#

def	write_bin(mypsb, psb_filename):
	if not mypsb or not psb_filename:
		return

	# Join the subfiles back into a single ADB
	bin_data = mypsb.join_subfiles()
	if bin_data is None:
		return

	if psb_filename.endswith('.psb'):
		basename = psb_filename[:-len('.psb')]
	elif psb_filename.endswith('.psb.m'):
		basename = psb_filename[:-len('.psb.m')]
	else:
		return

	filename = basename + '.bin'

	if not rename_backup(filename):
		return

	if global_vars.verbose:
		print("Writing '%s'" % filename)

	open(filename, 'wb').write(bytes(bin_data))

##################################################
#
#	write_psb
#
#	Write out our PSB object into a file
#	If the filename ends with .m, the file is compressed
#	The file is encrypted using the filename
#

def	write_psb(mypsb, filename):
	if not mypsb or not filename:
		return

	if not rename_backup(filename):
		return

	if global_vars.verbose:
		print("Writing '%s'" % filename)

	# Pack our PSB object into the on-disk format
	psb_data0 = mypsb.pack()
	if global_vars.verbose > global_vars.debug_level:
		open(filename + '.0', 'wb').write(psb_data0)	# raw

	if filename.endswith('.psb'):
		# Write out the data as-is
		open(filename, 'wb').write(psb_data0)

	elif filename.endswith('.psb.m'):
		# Compress the PSB data
		psb_data1 = psb.compress_data(psb_data0)
		if global_vars.verbose > global_vars.debug_level:
			open(filename + '.1', 'wb').write(psb_data1)	# compressed

		# Encrypt the PSB data using the filename as the key
		psb_data2 = psb.unobfuscate_data(psb_data1, filename)
		if global_vars.verbose > global_vars.debug_level:
			open(filename + '.2', 'wb').write(psb_data2)	# compressed/encrypted

		# Write out the compressed/encrypted PSB data
		open(filename, 'wb').write(psb_data2)

##################################################
#
#	write_rom
#
#	This extracts the rom data from the psb object and writes it to a file.
#

def	write_rom(mypsb, filename):
	if not mypsb or not filename:
		return

	if not rename_backup(filename):
		return

	if global_vars.verbose:
		print("Writing '%s'" % filename)

	mypsb.write_rom_file(filename)

##################################################
#
#	main
#
#	Entry point for cli.
#

def	main():

	epilog="""
-----

To extract a rom:

%(prog)s --inpsb /path/to/alldata.psb.m --outrom /path/to/new.rom

This will:
* Read in /path/to/alldata{.psb.m, .bin}

* Save the rom as /path/to/new.rom

-----

To inject a rom:

%(prog)s --inpsb /path/to/original/alldata.psb.m --inrom /path/to/new.rom --outpsb /path/to/new/alldata.psb.m

This will:
* Read in /path/to/original/alldata{.psb.m, .bin}

* Replace the original rom with /path/to/new.rom

* Create /path/to/new/alldata{.psb.m, .bin}

-----
"""
	parser = argparse.ArgumentParser(
		fromfile_prefix_chars='@',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=epilog)

	parser.add_argument('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='count',		default=0)

	parser.add_argument(		'--allow-overwrite',	dest='allow_overwrite',		help='Allow over-writing output files',				action='store_true',	default=False)
	parser.add_argument(		'--create-backup',	dest='create_backup',		help='Create backup before over-writing output files',		action='store_true',	default=False)

	parser.add_argument(		'--prefix',		dest='prefix',			help='Prefix new rom with PREFIX',		metavar='PREFIX')
	group_pad = parser.add_mutually_exclusive_group()
	group_pad.add_argument(		'--pad00',	dest='pad00',		help='Pad new rom with 00',			action='store_true',	default=False)
	group_pad.add_argument(		'--padFF',	dest='padFF',		help='Pad new rom with FF',			action='store_true',	default=False)

	parser.add_argument(		'--inpsb',	dest='inpsb',		help='Read INPSB',				metavar='INPSB',	required=True)
	parser.add_argument(		'--outrom',	dest='outrom',		help='Write the rom file to OUTROM',		metavar='OUTROM')
	parser.add_argument(		'--inrom',	dest='inrom',		help='Replace the rom file with INROM',		metavar='INROM')
	parser.add_argument(		'--outpsb',	dest='outpsb',		help='Write new psb to OUTPSB',			metavar='OUTPSB')

	if len(sys.argv) <= 1:
		parser.print_help()
		exit(0)

	global_vars.options = parser.parse_args()
	global_vars.verbose = global_vars.options.verbose

	release_the_kraken(global_vars.options.inpsb, global_vars.options.outrom, global_vars.options.inrom, global_vars.options.outpsb)

##################################################
#
#	main_batch
#
#	Entry point for batch/drop-target converter.
#
#	This will inject each provided ROM into a copy of the base game directory.
#

def	main_batch():
	parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
	parser.add_argument('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='count',		default=0)

	parser.add_argument(		'--base',		dest='base',			help='Copy base game directory from BASE',	metavar='BASE',		default='base')

	parser.add_argument(		'--prefix',		dest='prefix',			help='Prefix new rom with PREFIX',		metavar='PREFIX')
	group_pad = parser.add_mutually_exclusive_group()
	group_pad.add_argument(		'--pad00',	dest='pad00',		help='Pad new rom with 00',			action='store_true',	default=False)
	group_pad.add_argument(		'--padFF',	dest='padFF',		help='Pad new rom with FF',			action='store_true',	default=False)

	parser.add_argument(		'files',	metavar='ROM', nargs='+', help='Batch convert ROM')

	if len(sys.argv) <= 1:
		parser.print_help()
		exit(0)

	global_vars.options = parser.parse_args()
	global_vars.verbose = global_vars.options.verbose

	# Because we are working on a copy of the base, force --allow-overwrite ON and --create-backup OFF
	global_vars.options.create_backup	= True
	global_vars.options.allow_overwrite	= False

	if not os.path.isdir(global_vars.options.base):
		print("Base '%s' not found" % global_vars.options.base)
		return

	for file in global_vars.options.files:

		if global_vars.verbose >= global_vars.info_level:
			print('-----')
			print("Processing ROM '%s'" % file)

		# Get the base part of the rom file for our directory name
		file_base = os.path.basename(file)

		# Remove the extension
		for ext in ['.gba', '.GBA', '.rom', '.ROM']:
			if file_base.endswith(ext):
				file_base = file_base[:-len(ext)]
				break

		# If the directory already exists, skip this rom
		if os.path.isdir(file_base):
			print("%s exists, skipping" % file_base)
			continue

		# Copy our base game into the rom directory
		shutil.copytree(global_vars.options.base, file_base)

		psb = os.path.join(file_base, 'content', 'alldata.psb.m')

		release_the_kraken(psb, None, file, psb)

##################################################
#
#	main_gui
#
#	Entry point for wizard gui.
#

def	main_gui():

	parser = argparse.ArgumentParser(fromfile_prefix_chars='@')

	parser.add_argument('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='count',		default=0)

	parser.add_argument(		'--prefix',		dest='prefix',			help='Prefix new rom with PREFIX',		metavar='PREFIX')
	group_pad = parser.add_mutually_exclusive_group()
	group_pad.add_argument(		'--pad00',	dest='pad00',		help='Pad new rom with 00',			action='store_true',	default=False)
	group_pad.add_argument(		'--padFF',	dest='padFF',		help='Pad new rom with FF',			action='store_true',	default=False)

	global_vars.options = parser.parse_args()
	global_vars.verbose = global_vars.options.verbose

	# Default --create-backup and --allow-overwrite to ON
	# The filesave box will ask if you want to overwrite.
	global_vars.options.create_backup	= True
	global_vars.options.allow_overwrite	= True

	app_name = 'GBA injection wizard'
	app_title = app_name

	choose_task_text ='''
This tool provides a simplified interface to:

* Decrypt, decompress, and unpack an alldata.psb.m/alldata.bin file,

* Extract or replace the ROM file

* Repack, compress, and encrypt a new alldata.psb.m/alldata.bin file.

What do you want to do?'''

	choose_task_choices = [
		'Extract ROM',
		'Set Injection Options',
		'Inject ROM',
		'Quit',
		]

	extract_choose_inpsb_text = '''Choose your input alldata.psb.m'''
	extract_choose_outrom_text = '''Choose your output ROM'''
	extract_confirm_text = '''
Extract the ROM from a .psb.m file

We are about to extract the ROM from this psb:
{inpsb}

and save the ROM as:
{outrom}

'''

	options_app_title		= '''Set Injection Options'''
	options_enable_prefix_text	= '''
Do you want to prefix the ROM?

This can be used to prefix with goomba or pocketnes.

'''
	options_choose_prefix_text	= '''Choose your ROM prefix'''
	options_enable_pad00_text = '''Do you want to pad the ROM with 00s?'''
	options_enable_padFF_text = '''Do you want to pad the ROM with FFs?'''
	options_confirm_text = '''
Injecting a ROM will now prefix the rom with:
{prefix}

and pad to the original length with:
{padding}
'''

	inject_choose_inrom_text = '''Choose your input ROM'''
	inject_choose_inpsb_text = '''Choose your input alldata.psb.m'''
	inject_choose_outpsb_text = '''Choose your output alldata.psb.m'''
	inject_confirm_text = '''
Inject a ROM into a .psb.m file

We are about to inject this rom:
{rom}

prefixed with:
{prefix}

padded with:
{padding}

into this psb:
{inpsb}

and save the result as:
{outpsb}

'''

	state = 'choose_task'
	while state:
		#
		# Choose task
		#
		if state == 'choose_task':
			app_title = app_name + ' - Choose Task'
			rv = eg.buttonbox(choose_task_text, app_title, choose_task_choices)
			#print(type(rv), rv)
			if not rv or rv == '':
				exit(0)
			if rv == choose_task_choices[0]:
				state = 'extract'
			elif rv == choose_task_choices[1]:
				state = 'options'
			elif rv == choose_task_choices[2]:
				state = 'inject'
			elif rv == choose_task_choices[3]:
				state = 'quit'
				exit(0)
		#
		# Extract ROM
		#
		elif state == 'extract':
			# Hidden state to clear our filenames
			app_title = 'Extract ROM'
			inpsb = ''
			outrom = ''
			state = 'extract_choose_inpsb'
		elif state == 'extract_choose_inpsb':
			rv = eg.fileopenbox(extract_choose_inpsb_text, app_title, filetypes=['*', ['*.psb.m', 'psb.m files']])
			#print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				inpsb = rv
				state = 'extract_choose_outrom'
		elif state == 'extract_choose_outrom':
			rv = eg.filesavebox(extract_choose_outrom_text, title=app_title, default='gba.rom', filetypes=['*.rom', '*.gba'])
			#print(type(rv), rv)
			if not rv or rv == '':
				state = 'choose_task'
			else:
				outrom = rv
				state = 'extract_confirm'
		elif state == 'extract_confirm':
			rv = eg.ccbox(extract_confirm_text.format(inpsb=inpsb, outrom=outrom), app_title)
			#print(type(rv), rv)
			if not rv or rv == '':
				state = 'choose_task'
			else:
				release_the_kraken(inpsb, outrom, None, None)
				write_rom(mypsb, outrom)
				state = 'choose_task'
		#
		# Set Injection Options
		#
		elif state == 'options':
			# Hidden state to clear variables
			app_title = options_app_title
			prefix  = 'None'
			padding = 'None'
			state = 'options_enable_prefix'
		elif state == 'options_enable_prefix':
			rv = eg.ynbox(options_enable_prefix_text, app_title)
			#print(type(rv), rv)
			if rv:
				state = 'options_choose_prefix'
			else:
				state = 'options_enable_pad00'
		elif state == 'options_choose_prefix':
			rv = eg.fileopenbox(options_choose_prefix_text, app_title, filetypes=['*.rom', '*.gba'])
			print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				prefix = rv
				state = 'options_enable_pad00'
		elif state == 'options_enable_pad00':
			rv = eg.ynbox(options_enable_pad00_text, app_title)
			#print(type(rv), rv)
			if rv:
				padding = '00'
			state = 'options_enable_padFF'
		elif state == 'options_enable_padFF':
			rv = eg.ynbox(options_enable_padFF_text, app_title)
			#print(type(rv), rv)
			if rv:
				padding = 'FF'
			state = 'options_confirm'
		elif state == 'options_confirm':
			rv = eg.ccbox(options_confirm_text.format(prefix=prefix, padding=padding), app_title)
			#print(type(rv), rv)
			if not rv or rv == '':
				state = 'choose_task'
			else:
				if prefix == 'None':
					global_vars.options.prefix = None
				else:
					global_vars.options.prefix = prefix


				if padding == '00':
					global_vars.options.pad00 = True
					global_vars.options.padFF = False
				elif padding == 'FF':
					global_vars.options.pad00 = False
					global_vars.options.padFF = True
				else:
					global_vars.options.pad00 = False
					global_vars.options.padFF = False

				state = 'choose_task'
		#
		# Inject ROM
		#
		elif state == 'inject':
			# Hidden state to clear our filenames
			app_title = 'Inject ROM'
			inrom = ''
			inpsb = ''
			outpsb = ''
			state = 'inject_choose_rom'
		elif state == 'inject_choose_rom':
			rv = eg.fileopenbox(inject_choose_inrom_text, app_title, filetypes=['*.rom', '*.gba'])
			#print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				inrom = rv
				state = 'inject_choose_inpsb'
		elif state == 'inject_choose_inpsb':
			rv = eg.fileopenbox(inject_choose_inpsb_text, app_title, filetypes=[['*.psb.m', 'psb.m files']])
			#print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				inpsb = rv
				state = 'inject_choose_outpsb'
		elif state == 'inject_choose_outpsb':
			# Choose the output psb. We set the default to the input psb (common use-case).
			# The filesavebox will prompt if you want to over-write.
			rv = eg.filesavebox(inject_choose_outpsb_text, title=app_title, default=inpsb, filetypes=[['*.psb.m', 'psb.m files']])
			#print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				outpsb = rv
				state = 'inject_confirm'
		elif state == 'inject_confirm':

			if global_vars.options.prefix:
				prefix = global_vars.options.prefix
			else:
				prefix = 'None'

			if global_vars.options.pad00:
				padding = '00'
			elif global_vars.options.padFF:
				padding = 'FF'
			else:
				padding = 'None'

			rv = eg.ccbox(inject_confirm_text.format(rom=inrom, prefix=prefix, padding=padding, inpsb=inpsb, outpsb=outpsb), app_title)
			#print(type(rv), rv)
			if not rv or rv == '':
				state = 'choose_task'
			else:
				release_the_kraken(inpsb, None, inrom, outpsb)
				state = 'choose_task'
		else:
			print("Unknown state '%s'" % state)
			exit(1)
