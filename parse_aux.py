#!/usr/bin/python3
# -*- coding: utf-8 -*-

# from .lo_functions import chars
lo_chars = {
    'part': '■',
    'chapter': '𑗕',
    'section': '⏺',
    'subsection': '⊛',
    'subsubsection': '‣',
    'paragraph': '⸱',
    'frametitle': '▫'
    }

def extract_brace_group(s, start):
    """Extract content inside balanced braces starting at position `start`."""
    if s[start] != '{':
        raise ValueError("Expected opening brace at position {}".format(start))

    depth = 0
    i = start
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start+1:i], i + 1  # exclude outer braces
        i += 1

    raise ValueError("Unmatched braces in string starting at position {}".format(start))


def parse_newlabel_line(line):
    """Parse a line starting with \newlabel and extract label info."""
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

        type_field = fields[3] if len(fields) > 3 else None
        type_main, type_sub = None, None

        if type_field:
            if '.' in type_field:
                type_main, type_sub = type_field.split('.', 1)
            else:
                type_main = type_field

        return {
            'source': 'newlabel',
            'name': label_name,
            'label_text': fields[0] if len(fields) > 0 else None,
            'page_number': fields[1] if len(fields) > 1 else None,
            'hyper_anchor': fields[2] if len(fields) > 2 else None,
            'entry_type': type_main,
            'num': type_sub,
            'extra': fields[4] if len(fields) > 4 else None,
        }

    except Exception as e:
        print(f"Error parsing \\newlabel: {line.strip()}\n{e}")
        return None


def parse_writefile_line(line):
    """Parse a \@writefile line and split entry_text into number and title."""
    if not line.startswith('\\@writefile'):
        return None

    try:
        i = line.find('{')
        file_type, i = extract_brace_group(line, i)
        content, i = extract_brace_group(line, i)

        if content.startswith('\\contentsline'):
            j = content.find('{')
            entry_type, j = extract_brace_group(content, j)
            raw_text, j = extract_brace_group(content, j)
            page_number, j = extract_brace_group(content, j)

            # If raw_text starts with \numberline{X}Some Title
            entry_number = None
            entry_title = raw_text

            if raw_text.startswith('\\numberline'):
                k = raw_text.find('{')
                entry_number, k = extract_brace_group(raw_text, k)
                entry_title = raw_text[k:].lstrip()
                if entry_title.startswith('}'):
                    entry_title = entry_title[1:].lstrip()

                # Remove {\ignorespaces ...} if present
                if entry_title.startswith('{\\ignorespaces'):
                    entry_title = entry_title[14:-1].strip()

            return {
                'source': 'writefile',
                'file': file_type,
                'entry_type': entry_type,
                'num': entry_number,
                'entry_title': entry_title,
                'page_number': page_number
            }

    except Exception as e:
        print(f"Error parsing \\@writefile: {line.strip()}\n{e}")
        return None



def parse_aux_file(filename):
    """Parse a .aux file and return a list of entries from \newlabel and \@writefile."""
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

def print_sections(sec_data):        
    print("-------- Sections")
    for entry in sec_data: 
        type = entry['entry_type'].title()
        num = str(entry['num'])
        title = entry['entry_title']
        print(type + " " + num + ". " + title)

def print_labels(lab_data):    
    print("-------- Labels")
    for entry in lab_data: 
        type = entry['entry_type'].title()
        num = "(" + str(entry['num']) + ")" if entry['entry_type'] == 'equation' else str(entry['num'])
        label = entry['name']
        print(type + " " + num + ": " + label + "  📋" )

def print_raw_data(all_data):
    for entry in all_data:
        print("\n--- Entry ---")
        for key, value in entry.items():
            print(f"{key}: {value}")

def print_all_data(all_data):
    for entry in all_data:
        if entry['source'] =='writefile' and entry['file'] == 'toc':
            if entry['entry_type'] in section_types:
                bullet = lo_chars[entry['entry_type']]
            else:
                bullet = "◦"
            type = entry['entry_type'].title()
            num = str(entry['num'])
            title = entry['entry_title']
            print(bullet + " " + num + ". " + title) # + " " + type
        elif entry['source'] =='newlabel':
            if entry['entry_type'] in section_types:
                print("   ↪ " + "  📋" )    
            else:
                if entry['entry_type'] == 'equation':
                    num = "(" + str(entry['num']) + ")"
                    type = "Eq."
                else:
                    num = str(entry['num'])
                    type = entry['entry_type'].title()
                label = entry['name']
                print(" ◦ " + type + " " + num + "  📋" )

# Example usage
#if __name__ == '__main__':
#    aux_file = '/Users/glass/Documents/Dropbox/Fabio-Khai-Olivier/One-side/2025/1-OSBC-June2019.aux'
#            #'/Users/glass/maths/Peut-être ?/Bergman-2025/Article/heat-controls.aux' 
#    section_types = ('part', 'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'frametitle')
#    all_data = parse_aux_file(aux_file)
#    # sec_data = [d for d in all_data if d['source'] =='writefile' and d['file'] == 'toc']
#    # lab_data = [d for d in all_data if d['source'] =='newlabel']
#    print_raw_data(all_data)



