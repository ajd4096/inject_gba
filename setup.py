from setuptools import setup

setup(
	name		= 'inject_gba',
	version		= '0.1',
	description	= 'Inject GBA roms for Nintendo Wii-U virtual console',
	url		= 'http://github.com/ajd4096/inject_gba',
	author		= 'Andrew Dalgleish',
	author_email	= 'ajd4096@github.com',
	license		= 'BSD',
	packages	= ['inject_gba'],
	entry_points	= {
		"console_scripts": [
			'inject_gba_cli = inject_gba.inject_gba:main_cli',
			'inject_gba_gui = inject_gba.inject_gba:main_gui',
		],
	},
	install_requires	= [
		'easygui',
		'pyyaml',
	],
	zip_safe	= True)
