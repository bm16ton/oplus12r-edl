#!/bin/bash

echo "starting wipe_rawprogram_PHY"
echo \n\n\n\n
for i in 0 1 2 3 4 5 ; do python3 edl.py qfil $1/wipe_rawprogram_PHY$i.xml $1/patch$i.xml $1 --loader=firehose --memory=UFS --vip --vip-digest=Digest.mbn --vip-sign=sig.dat --skipinitialread; done;
echo \n\n\n\n\n\n\n\n
echo "starting rawprogramX_BLANK_GPT.xml"
echo \n\n\n\n\n\n\n\n
for i in 0 1 2 3 4 5 ; do python3 edl.py qfil $1/rawprogram$i_BLANK_GPT.xml $1/patch$i.xml $1 --loader=firehose --memory=UFS --vip --vip-digest=Digest.mbn --vip-sign=sig.dat --skipinitialread; done;
echo \n\n\n\n\n\n\n\n
echo "starting rawprogramX_WIPE_PARTITIONS.xml"
echo \n\n\n\n\n\n\n\n
for i in 0 1 2 3 4 5 ; do python3 edl.py qfil $1/rawprogram$i_WIPE_PARTITIONS.xml $1/patch$i.xml $1 --loader=firehose --memory=UFS --vip --vip-digest=Digest.mbn --vip-sign=sig.dat --skipinitialread; done;
echo \n\n\n\n\n\n\n\n
echo "starting rawprogramX.xml"
echo \n\n\n\n\n\n\n\n
for i in 0 1 2 3 4 5 ; do cp $1/rawprogram$i.xml $1/rawprogram.xml ; python3 edl.py qfil $1/rawprogram$i.xml $1/patch$i.xml $1 --loader=firehose --memory=UFS --vip --vip-digest=Digest.mbn --vip-sign=sig.dat --skipinitialread; done;
#for i in 0 1 2 3 4 5 ; do python3 edl --loader=firehose printgpt --memory=UFS --lun=$i; done;
