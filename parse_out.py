#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import re
import codecs

def decode_utf16_bookmark(raw_text):
    # Convert a LaTeX \376\377\0001\000.\000\040\... string to bytes
    byte_string = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), raw_text)
    utf16_bytes = byte_string.encode('latin1')  # original text was escaped in \ooo octal format
    return utf16_bytes.decode('utf-16')

def parse_out_file(path):
    pattern = re.compile(r'\\BOOKMARK\s+\[\d\]\[-\]\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}%\s*(\d+)')
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                ref, raw_title, parent, num = match.groups()
                try:
                    title = decode_utf16_bookmark(raw_title)
                except Exception as e:
                    title = f"(Erreur de décodage: {e})"
                print(f"{num.zfill(2)} | {ref} | {title}")

def main():
    parser = argparse.ArgumentParser(description="Parse et décode les signets d'un fichier .out LaTeX.")
    parser.add_argument("file", help="Chemin du fichier .out à parser")
    args = parser.parse_args()
    parse_out_file(args.file)

if __name__ == "__main__":
    main()


