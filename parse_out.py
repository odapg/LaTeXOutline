#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import re
import codecs

def decode_utf16_bookmark(raw_text):
    # Convert a LaTeX \376\377\0001\000.\000\040\... string to bytes
    byte_string = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), raw_text)
    utf16_bytes = byte_string.encode('latin1') 
    return utf16_bytes.decode('utf-16')

def parse_out_file(path):

    out_pattern = re.compile(r'\\BOOKMARK\s+\[\d\]\[-\]\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}%\s*(\d+)')

    out_data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            match = out_pattern.search(line)
            if match:
                ref, raw_title, parent, num = match.groups()
                ref_parts = ref.split(".", 1)
                title = decode_utf16_bookmark(raw_title)
                item = [ref_parts[0], ref_parts[1], title, num]
                out_data.append(item)
                
    return out_data


