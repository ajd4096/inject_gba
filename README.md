# inject_gba

-----

## Description:
GBA injection for Wii-U virtual console games.

-----

## Warning:
This is still a massive work-in-progress.

-----

## Requirements:
### Python 3
No, it won't work with Python 2.
Python 3 was released in 2008, it is time to move on.

### Various python modules.
Initial attempt at packaging, I may have missed some dependencies.
If you get a missing import, install it.

The GUI requires python's tkinter, you will need to install this yourself.

-----

## Installation:

### FreeBSD 10
Install Python 3.4:
```
sudo pkg install python34 py34-tkinter
```

Install inject_gba:
```
sudo python3 setup.py install
```

### Linux - Centos 6
The easiest way to install Python 3 is from the ius repo at http://ius.io
```
sudo yum install https://centos6.iuscommunity.org/ius-release.rpm
sudo yum install python35u python35u-setuptools python35u-tkinter
```

If you have a bare-bones installation you will need some X11 fonts:
```
sudo yum install xorg-x11-fonts\*
```

If you are connecting via SSH (eg to a VM) you will need xauth:
```
sudo yum install xorg-x11-xauth
```

Install inject_gba using:
```
sudo python3.5 setup.py install
```

### Windows (I tested Python 3.5.1 on Windows 8.1)

Install the 32-bit python, even on 64-bit windows.
https://www.python.org/downloads/windows/

If you get error 0x80240017, make sure you have installed all updates.
If you still get the same error you may need to update the Universal C Runtime:
https://support.microsoft.com/en-au/kb/2999226

Select "Install for all users" and "Add python to PATH"

Open a CMD prompt as administrator and run
```
python setup.py install
```

This will install "inject_gba.exe"

It works just by typing "inject_gba".

You can run this from anywhere.

You do not need to specify a path.

You do not need to type "python inject_gba.py".

You do not need to be in the source directory.

You do not need to keep the source directory.


-----

## Quick Start:

To start the GUI:
```
inject_gba --gui
```

To extract a rom:
```
inject_gba --inpsb /path/to/alldata.psb.m --outrom /path/to/extracted.rom
```

To inject a rom:
```
inject_gba --inpsb /path/to/alldata.psb.m --inrom /path/to/new.rom --outpsb /path/to/new/alldata.psb.m
```

You can put options in a text file, one option per line, and run it using:
inject_gba @optionsfile
