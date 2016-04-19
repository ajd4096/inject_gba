# inject_gba

## Description:
GBA injection for Wii-U virtual console games.

## Warning:
This is still a massive work-in-progress.

## Requirements:
### Python 3
No, it won't work with Python 2.
Python 3 was released in 2008, it is time to move on.

### Various python modules.
Initial attempt at packaging, I may have missed some dependencies.
If you get a missing import, install it.

The GUI requires python's tkinter, you will need to install this yourself.

## Installation:

python3 setup.py install

You can run this without installing using inject_gba_cli.py and inject_gba_gui.py

## Quick Start:

To start the GUI:
inject_gba_gui

To extract a rom:
inject_gba_cli --inpsb /path/to/alldata.psb.m --outrom /path/to/extracted.rom

To inject a rom:
inject_gba_cli --inpsb /path/to/alldata.psb.m --inrom /path/to/new.rom --outpsb /path/to/new/alldata.psb.m
