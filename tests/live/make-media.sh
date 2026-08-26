#!/bin/bash
# Builds the test library: 4 synthetic photos with EXIF/GPS, 1 video, 3 public-domain portraits (Wikimedia Commons), 1 near-duplicate, 1 screenshot-like image.
set -e; cd "$(dirname "$0")/media"
UA="immich-photo-manager-live-tests/1.0"
i=1; for spec in "red|CAT|38.7223|9.1393|01" "blue|BOAT|41.1579|8.6291|02" "green|TREE|38.7979|9.3902|03" "gold|RECEIPT 42.50 EUR|38.7223|9.1393|04"; do
  IFS='|' read color label lat lon d <<<"$spec"
  magick -size 1200x800 xc:$color -gravity center -pointsize 96 -fill black -annotate 0 "$label" photo$i.jpg
  exiftool -q -overwrite_original -DateTimeOriginal="2026:03:$d 12:0$i:00" -GPSLatitude=$lat -GPSLatitudeRef=N -GPSLongitude=$lon -GPSLongitudeRef=W -Make=LabCam -Model=Test$i photo$i.jpg; i=$((i+1)); done
ffmpeg -loglevel error -y -f lavfi -i "color=c=purple:s=640x360:d=3" -vf "drawtext=text='VIDEO CLIP':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" -pix_fmt yuv420p clip.mp4
curl -sL -A "$UA" "https://commons.wikimedia.org/wiki/Special:FilePath/Abraham_Lincoln_O-77_matte_collodion_print.jpg?width=800" -o lincoln1.jpg
curl -sL -A "$UA" "https://commons.wikimedia.org/wiki/Special:FilePath/Abraham_Lincoln_November_1863.jpg?width=800" -o lincoln2.jpg
curl -sL -A "$UA" "https://commons.wikimedia.org/wiki/Special:FilePath/Albert_Einstein_Head.jpg?width=800" -o einstein.jpg
magick lincoln1.jpg -resize 95% -quality 70 lincoln1_dup.jpg
exiftool -q -overwrite_original -DateTimeOriginal="2026:03:05 09:00:00" -GPSLatitude=40.7128 -GPSLatitudeRef=N -GPSLongitude=74.0060 -GPSLongitudeRef=W lincoln1.jpg lincoln2.jpg einstein.jpg lincoln1_dup.jpg
magick -size 1170x2532 xc:white -gravity north -pointsize 60 -annotate +0+200 "Screenshot" Screenshot_2026-03-05.png
magick -size 800x600 xc:orange -gravity center -pointsize 80 -annotate 0 "UPLOAD TEST" upload_test.jpg
magick -size 800x600 xc:teal -gravity center -pointsize 80 -annotate 0 "FORCE DELETE" upload_test2.jpg
ls
