#!/usr/bin/env python3
"""Check kCFRunLoopCommonModes value"""
from CoreFoundation import kCFRunLoopCommonModes, kCFRunLoopDefaultMode
print(f"kCFRunLoopCommonModes = {kCFRunLoopCommonModes!r}")
print(f"kCFRunLoopDefaultMode = {kCFRunLoopDefaultMode!r}")
print(f"Type common: {type(kCFRunLoopCommonModes)}")
print(f"Type default: {type(kCFRunLoopDefaultMode)}")

# Try string version
from CoreFoundation import CFSTR
common_str = CFSTR("kCFRunLoopCommonModes")
print(f"CFSTR common = {common_str!r}")

# The actual string for common modes
print(f"\nCommon modes string: 'kCFRunLoopCommonModes'")