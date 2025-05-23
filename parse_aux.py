#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re

# --------------------------
def extract_brace_group(s, start):
    """Extract content inside balanced braces starting at position `start`."""
    if s[start] != '{':
        raise ValueError("Expected opening brace at position {}".format(start))

    depth = 0
    i = start
    while i <= len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start+1:i], i + 1  # exclude outer braces
        i += 1

    return None


# --------------------------
def parse_newlabel_line(line):
    """Parse a line starting with newlabel and extract label info."""
    if not line.startswith('\\newlabel'):
        return None

    try:
        name_start = line.find('{') + 1
        name_end = line.find('}', name_start)
        label_name = line[name_start:name_end]

        fields = []
        i = line.find('{{', name_end)
        i += 1  # move to the first '{'

        while len(fields) < 5 and i < len(line):
            if line[i] == '{':
                field, i = extract_brace_group(line, i)
                fields.append(field)
            else:
                i += 1

        # type_field = fields[3] if len(fields) > 3 else None
        # type_main, type_sub = None, None
        # if type_field:
        #     if '.' in type_field:
        #         type_main, type_sub = type_field.split('.', 1)
        #     else:
        #         type_main = type_field

        return {
            # 'source': 'newlabel',
            'main_content': label_name,
            'reference': fields[0] if len(fields) > 0 else None,
            # 'page_number': fields[1] if len(fields) > 1 else None,
            # 'hyper_anchor': fields[2] if len(fields) > 2 else None,
            'entry_type': "label",
            # 'num': type_sub,
            # 'extra': fields[4] if len(fields) > 4 else None,
        }

    except Exception as e:
        print(f"Error parsing \\newlabel: {line.strip()}\n{e}")
        return None


# --------------------------
def parse_writefile_line(line):
    """Parse a line starting with writefile and extract info (sections)."""
    if not line.startswith('\\@writefile'):
        return None

    line = str(line)
    try:
        i = line.find('{')
        file_type, i = extract_brace_group(line, i)
        content, _ = extract_brace_group(line, i)

        if content.startswith('\\contentsline'):
            j = content.find('{')
            entry_type, j = extract_brace_group(content, j)
            raw_text, j = extract_brace_group(content, j)
            page_number, j = extract_brace_group(content, j)

            # Attempt to extract optional extra field and ignore it
            while j < len(content) and content[j] == '{':
                _, j = extract_brace_group(content, j)

            entry_number = None
            entry_title = raw_text.strip()

            # Case {\section{}{...}}
            test_toc = r'^\\toc[a-z]+\s\{[a-zA-Z0-9]*\}'
            if re.match(test_toc, raw_text):
                raw_text = re.sub(test_toc, '', raw_text, count=1)
                k = raw_text.find('{')
                entry_number, k = extract_brace_group(raw_text, k)
                entry_title = raw_text[k:].lstrip()
                if entry_title.startswith('{'):
                    entry_title = entry_title[1:].lstrip()
                    if entry_title.endswith('}'):
                        entry_title = entry_title[:-1].rstrip()

            elif raw_text.startswith('\\numberline'):
                k = raw_text.find('{')
                entry_number, k = extract_brace_group(raw_text, k)
                entry_title = raw_text[k:].lstrip()

            elif '\\hspace' in raw_text:
                split_index = raw_text.find('\\hspace')
                entry_number = raw_text[:split_index].strip()
                hspace_brace_start = raw_text.find('{', split_index)
                if hspace_brace_start != -1:
                    hspace_brace_end = raw_text.find('}', hspace_brace_start)
                    if hspace_brace_end != -1:
                        entry_title = raw_text[hspace_brace_end+1:].strip()

            # Removes unnecessary mboxes in section numbers
            test_mbox = r'^\\mbox\s*\{(.*?)\}(.*?)$'
            if match := re.match(test_mbox, str(entry_number)):
                entry_number = match.group(1) + match.group(2)
            
            if entry_title.startswith('{\\ignorespaces'):
                full_group, _ = extract_brace_group(entry_title, 0)
                entry_title = full_group[len('\\ignorespaces'):].strip()

            entry_title = re.sub(r'\\([a-zA-Z0-9]+)\s+\{', r'\\\1{', entry_title)

            return {
                # 'source': 'writefile',
                # 'type': file_type,
                'entry_type': entry_type,
                'reference': entry_number,
                'main_content': entry_title,
                # 'page_number': page_number
            }

    except Exception as e:
        print(f"Error parsing \\@writefile: {line.strip()}\n{e}")
        return None

# ---- Main function ----

def parse_aux_file(filename):
    """Parse a .aux file and return a list of entries from \newlabel and \\@writefile."""
    entries = []

    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if line.startswith('\\newlabel'):
                parsed = parse_newlabel_line(line)
            elif line.startswith('\\@writefile'):
                parsed = parse_writefile_line(line)
            else:
                parsed = None

            if parsed:
                entries.append(parsed)

    return entries
