# inject_gba
To insert a GBA rom into alldata.bin:

unpack-psb.py -r /path/to/new.rom -o workdir/alldata.psb.m originaldir/alldata.psb.m

This will:
* Read in originaldir/alldata{.psb.m, .bin}

* Save the original rom in workdir/alldata.rom

* Replace the original rom with /path/to/new.rom

* Create workdir/alldata{.psb.m, .bin}
