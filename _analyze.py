#!/usr/bin/env python3
"""Analyze screenshot"""
from PIL import Image
import numpy as np
img = Image.open("/tmp/screenshot.png")
print(f"Size: {img.size}")
arr = np.array(img)
h, w = arr.shape[:2]
print(f"Center pixel: {arr[h//2, w//2]}")
print(f"Top-left: {arr[10, 10]}")
flat = arr.reshape(-1, 3)
print(f"Mean color: {flat.mean(axis=0)}")
print(f"Color std: {flat.std(axis=0)}")
is_peach = (arr[:,:,0] > 200).any() and (arr[:,:,1] > 180).any()
print(f"Has warm tones: {is_peach}")
black = (flat.sum(axis=1) < 30).sum()
total = len(flat)
print(f"Black pixels: {black}/{total} ({100*black/total:.1f}%)")
# Sample grid of pixels
samples = arr[::h//10, ::w//10]
print(f"\nGrid samples:")
for row in samples[:5]:
    for px in row[:5]:
        print(f"({px[0]:3d},{px[1]:3d},{px[2]:3d})", end=" ")
    print()
