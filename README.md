# inject_gba

This is still a massive work-in-progress.

# Requirements:
## Python 3
No, it won't work with Python 2.
Python 3 was released in 2008, it is time to move on.

## Various python modules.
I do not know what modules your system installs by default.
If it complains about a missing import, install it.

-----

To insert a GBA rom into alldata.bin:

unpack-psb.py -r /path/to/new.rom -o workdir/alldata.psb.m originaldir/alldata.psb.m

This will:
* Read in originaldir/alldata{.psb.m, .bin}

* Save the original rom in workdir/alldata.rom

* Replace the original rom with /path/to/new.rom

* Create workdir/alldata{.psb.m, .bin}
