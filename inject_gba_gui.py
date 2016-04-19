#!/usr/bin/env python3
import	os
import	sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'easygui-0.98.0-py3.5.egg'))
import	easygui as eg

import	inject_gba_cli as myapp

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
		print(type(rv), rv)
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
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			inpsb = rv
			state = 'extract_choose_outrom'
	elif state == 'extract_choose_outrom':
		rv = eg.filesavebox(extract_choose_outrom_text, title=app_title, default='gba.rom', filetypes=['*.rom', '*.gba'])
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			outrom = rv
			state = 'extract_confirm'
	elif state == 'extract_confirm':
		rv = eg.ccbox(extract_confirm_text.format(inpsb=inpsb, outrom=outrom), app_title)
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			mypsb = myapp.load_from_psb(inpsb)
			myapp.write_rom(mypsb, outrom)
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
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			inrom = rv
			state = 'inject_choose_inpsb'
	elif state == 'inject_choose_inpsb':
		rv = eg.fileopenbox(inject_choose_inpsb_text, app_title, filetypes=[['*.psb.m', 'psb.m files']])
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			inpsb = rv
			state = 'inject_choose_outpsb'
	elif state == 'inject_choose_outpsb':
		rv = eg.filesavebox(inject_choose_outpsb_text, title=app_title, default='alldata.psb.m', filetypes=[['*.psb.m', 'psb.m files']])
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			outpsb = rv
			state = 'inject_confirm'
	elif state == 'inject_confirm':
		rv = eg.ccbox(inject_confirm_text.format(rom=inrom, inpsb=inpsb, outpsb=outpsb), app_title)
		print(type(rv), rv)
		if not rv or rv == '':
			state = 'choose_task'
		else:
			mypsb = myapp.load_from_psb(inpsb)
			myapp.read_rom(mypsb, inrom)
			myapp.write_psb(mypsb, outpsb)
			myapp.write_bin(mypsb, outpsb)
			state = 'choose_task'
	else:
		print("Unknown state '%s'" % state)
		exit(1)
