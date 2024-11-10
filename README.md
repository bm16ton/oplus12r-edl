From resources;
```
https://xdaforums.com/t/bkerlers-edl-firehose-tools-for-op11-sd8-gen-2-devices.4676406/
https://github.com/bkerler/edl/issues/439
https://github.com/bkerler/edl/issues/236
https://github.com/ezdiy/edl

Chinease tools;
bff
edl-tool-9008_1.0.5
qualcomm-toolbox
qualcomm-toolbox-test
```
I added all the source files (hopefully) and an unused guide for collecting keys I know nothing about but maybe useful. 
Also I used the edl tools fork (link above) but maybe not required since using QSaharaServer fh_loader.

The extent I have tested this is the very few commands listed below, obvioudsly this was for linux but if your the type
who likes to buy a pc then immediatly hand it over to microsoft/mac overlords, and those overlords say yes when you ask
if you can do this, the tools mentioned above are all windows based.
```
cd oplus_8g2
sudo ./QSaharaServer -p /dev/ttyUSB0 -s 13:firehose
./fh_loader --port=/dev/ttyUSB0 --signeddigests=Digest.mbn --noprompt --showpercentagecomplete --zlpawarehost=1 --memoryname=ufs --testvipimpact
cd ../edl-8g2-patch/
mkdir logs
touch logs/log.txt
./edl printgpt --memory=ufs --lun=0 --loader=prog_firehose_ddr.elf --debugmode
./edl printgpt --memory=ufs --lun=0 --loader=prog_firehose_ddr.elf
./edl w bluetooth_a /media/maddocks/ffa2be2d-c02e-44df-9238-e8598c6db2e3/payload-extract/bluetooth.img  --memory=ufs --lun=4  --loader=prog_firehose_ddr.elf --debugmode
```
