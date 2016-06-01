#!/usr/bin/env python3

import	argparse
import	os
import	sys

import	inject_gba.global_vars	as global_vars
import	inject_gba.psb		as psb

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

# Count the TOCTOUs!
def	rename_backup(filename):

	# Optionally create a .bak if none exist
	if global_vars.options.create_backup and os.path.isfile(filename) and not os.path.isfile(filename + '.bak') and not os.path.isdir(filename + '.bak') and not os.path.ismount(filename + '.bak'):
		os.rename(filename, filename + '.bak')

	# Optionally refuse to overwrite the existing file
	if not global_vars.options.allow_overwrite and os.path.isfile(filename):
		print("File '%s' exists, not over-writing" % filename)
		return False

	return True

# Write out our PSB
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

# Write out the ADB
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

def	write_rom(mypsb, filename):
	if not mypsb or not filename:
		return

	if not rename_backup(filename):
		return

	if global_vars.verbose:
		print("Writing '%s'" % filename)

	mypsb.write_rom_file(filename)

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
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog=epilog)

	parser.add_argument('-v',	'--verbose',	dest='verbose',		help='verbose output',				action='count',		default=0)

	parser.add_argument(		'--allow-overwrite',	dest='allow_overwrite',		help='Allow over-writing output files',				action='store_true',	default=False)
	parser.add_argument(		'--create-backup',	dest='create_backup',		help='Create backup before over-writing output files',		action='store_true',	default=False)

	parser.add_argument(		'--prefix',		dest='prefix',			help='Prefix new rom with PREFIX',		metavar='PREFIX')

	group_pad = parser.add_mutually_exclusive_group()
	group_pad.add_argument(		'--pad00',	dest='pad00',		help='Pad new rom with 00',			action='store_true',	default=False)
	group_pad.add_argument(		'--padFF',	dest='padFF',		help='Pad new rom with FF',			action='store_true',	default=False)

	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument(		'--gui',	dest='gui',		help='Use GUI',					action='store_true',	default=False)
	group.add_argument(		'--inpsb',	dest='inpsb',		help='Read INPSB',				metavar='INPSB')
	parser.add_argument(		'--outrom',	dest='outrom',		help='Write the rom file to OUTROM',		metavar='OUTROM')
	parser.add_argument(		'--inrom',	dest='inrom',		help='Replace the rom file with INROM',		metavar='INROM')
	parser.add_argument(		'--outpsb',	dest='outpsb',		help='Write new psb to OUTPSB',			metavar='OUTPSB')

	if len(sys.argv) <= 1:
		parser.print_help()
		exit(0)
	else:
		options = parser.parse_args()

	global_vars.verbose = options.verbose
	global_vars.options = options

	if options.gui:
		main_gui()
	else:
		main_cli()

def	main_cli():
	# We must have an inpsb (this should be enforced by the parser)
	if not global_vars.options.inpsb:
		parser.print_help()
	mypsb = load_from_psb(global_vars.options.inpsb)

	# If we have outrom, write it out
	if global_vars.options.outrom:
		write_rom(mypsb, global_vars.options.outrom)

	# If we have inrom, read it in
	if global_vars.options.inrom:
		read_rom(mypsb, global_vars.options.inrom)

	# If we have outpsb, write it out
	if global_vars.options.outpsb:
		write_psb(mypsb, global_vars.options.outpsb)
		write_bin(mypsb, global_vars.options.outpsb)

def	main_gui():
	import	easygui as eg

	# Default --create-backup and --allow-overwrite to ON
	# The filesave box will ask if you want to overwrite.
	global_vars.options.create_backup	= True
	global_vars.options.allow_overwrite	= True

	app_name = 'GBA injection wizard'
	app_title = app_name

	choose_task_text ='''This tool provides a simplified interface to:

	* Decrypt, decompress, and unpack an alldata.psb.m/alldata.bin file,

	* Extract or replace the ROM file

	* Repack, compress, and encrypt a new alldata.psb.m/alldata.bin file.


	What do you want to do?'''
	choose_task_choices = [
		'Extract ROM',
		'Inject ROM',
		'Quit',
		]

	inject_choose_inrom_text = '''Choose your input ROM'''
	inject_choose_inpsb_text = '''Choose your input alldata.psb.m'''
	inject_choose_outpsb_text = '''Choose your output alldata.psb.m'''
	inject_confirm_text = '''
	Inject a ROM into a .psb.m file

	We are about to inject this rom:
	{rom}

	into this psb:
	{inpsb}

	and save the result as:
	{outpsb}

	'''

	extract_choose_inpsb_text = '''Choose your input alldata.psb.m'''
	extract_choose_outrom_text = '''Choose your output ROM'''
	extract_confirm_text = '''
	Extract the ROM from a .psb.m file

	We are about to extract the ROM from this psb:
	{inpsb}

	and save the ROM as:
	{outrom}

	'''


	state = 'choose_task'
	while state:
		if state == 'choose_task':
			app_title = app_name + ' - Choose Task'
			rv = eg.buttonbox(choose_task_text, app_title, choose_task_choices)
			#print(type(rv), rv)
			if not rv or rv == '':
				exit(0)
			if rv == choose_task_choices[0]:
				state = 'extract'
			elif rv == choose_task_choices[1]:
				state = 'inject'
			elif rv == choose_task_choices[2]:
				state = 'quit'
				exit(0)
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
				mypsb = load_from_psb(inpsb)
				write_rom(mypsb, outrom)
				state = 'choose_task'
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
			rv = eg.filesavebox(inject_choose_outpsb_text, title=app_title, default='alldata.psb.m', filetypes=[['*.psb.m', 'psb.m files']])
			#print(type(rv), rv)
			if not rv or rv == '' or rv == '.':
				state = 'choose_task'
			else:
				outpsb = rv
				state = 'inject_confirm'
		elif state == 'inject_confirm':
			rv = eg.ccbox(inject_confirm_text.format(rom=inrom, inpsb=inpsb, outpsb=outpsb), app_title)
			#print(type(rv), rv)
			if not rv or rv == '':
				state = 'choose_task'
			else:
				mypsb = load_from_psb(inpsb)
				read_rom(mypsb, inrom)
				write_psb(mypsb, outpsb)
				write_bin(mypsb, outpsb)
				state = 'choose_task'
		else:
			print("Unknown state '%s'" % state)
			exit(1)
