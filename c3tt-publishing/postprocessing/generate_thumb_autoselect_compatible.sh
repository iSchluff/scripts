#!/bin/bash

BASEDIR=$(dirname $0)
INTERVAL=180

file="$1"
outdir="$2"


LENGTH=$(ffprobe-voc -loglevel quiet -print_format default -show_format "$file" | grep duration= | sed -e 's/duration=\([[:digit:]]*\).*/\1/g')

TMPDIR=$(mktemp -d /tmp/thumb.XXXXXX)

if [ -z "$outdir" ]; then
  outgif=${file%.*}.gif
  outjpg=${file%.*}.jpg
  outjpg_preview=${file%.*}_preview.jpg
else
  outgif=${outdir}/$(basename ${file%.*}.gif)
  outjpg=${outdir}/$(basename ${file%.*}.jpg)
  outjpg_preview=${outdir}/$(basename ${file%.*}_preview.jpg)
fi


# now extract candidates and convert to non-anamorphic images
#
# we use equidistant sampling, but skip parts of the file that might contain pre-/postroles
# also, use higher resolution sampling at the beginning, as there's usually some interesting stuff there


for POS in 20 30 40 $(seq 15 $INTERVAL $[ $LENGTH - 60 ])
do
	ffmpeg-voc -loglevel error -ss $POS -i "$file"  -an -r 1 -filter:v 'scale=sar*iw:ih' -vframes 1 -f image2 -vcodec mjpeg -y "$TMPDIR/$POS.jpg"
done

WINNER=$(python2 $BASEDIR/select.py $TMPDIR/*.jpg)
ffmpeg-voc -loglevel error -i $WINNER -filter:v 'crop=ih*4/3:ih' -s 192x144 $outjpg
ffmpeg-voc -loglevel error -i $WINNER -filter:v 'crop=ih*4/3:ih' -s 640x360 $outjpg_preview