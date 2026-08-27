#!/usr/bin/env python3
"""Assemble demo frames into animated GIF."""
import os
import glob
from PIL import Image

# Find frames in Downloads or current dir
home = os.path.expanduser("~")
downloads = os.path.join(home, "Downloads")
project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Look for frame*.png in Downloads
frames_dir = downloads
frame_files = sorted(glob.glob(os.path.join(frames_dir, "frame*.png")))

if not frame_files:
    # Try current directory
    frame_files = sorted(glob.glob("frame*.png"))

if not frame_files:
    print("No frame*.png files found in Downloads or current directory!")
    exit(1)

print(f"Found {len(frame_files)} frames:")
for frame_file in frame_files:
    print(f"  {os.path.basename(frame_file)}")

# Frame durations in ms
# frame0=start, frame1=setup, frame2=gallery, frame3=selection,
# frame4=confirm, frame5=album, frame6=geographic
delays = [1500, 3000, 2500, 3000, 3000, 3000, 4000]

# Ensure we have enough delays
while len(delays) < len(frame_files):
    delays.append(3000)

# Load and resize frames
images = []
for frame_file in frame_files:
    img = Image.open(frame_file).convert("RGBA")
    # Scale down to 800px wide for reasonable GIF size
    width, height = img.size
    new_w = 800
    new_h = int(height * new_w / width)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    # Convert to RGB (GIF doesn't support alpha)
    rgb = Image.new("RGB", img.size, (236, 231, 223))  # --bg color
    rgb.paste(img, mask=img.split()[3])
    images.append(rgb)

# Save GIF
output = os.path.join(project, "assets", "demo.gif")
images[0].save(
    output,
    save_all=True,
    append_images=images[1:],
    duration=delays[:len(images)],
    loop=0,
    optimize=True,
)

size_mb = os.path.getsize(output) / 1024 / 1024
print(f"\nGIF saved: {output}")
print(f"Size: {size_mb:.2f} MB")
print(f"Frames: {len(images)}")
print(f"Resolution: {images[0].size[0]}x{images[0].size[1]}")
