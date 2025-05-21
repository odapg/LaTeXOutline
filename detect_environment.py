# Adaptation of LaTeXTools' change_environment.py
# LaTeXTools is distributed under the MIT Licence,
# Copyright (c) 2024 Sublime Text Packages
# https://github.com/SublimeText/LaTeXTools

import sublime
import sublime_plugin
import re
import itertools
import bisect

# -------------------------------------------------

begin_pattern = r"\\begin\{([^\}]*)\}"
end_pattern = r"\\end\{([^\}]*)\}"
begin_re = re.compile(begin_pattern)
end_re = re.compile(end_pattern)

# -------------------------------------------------

def find_env_regions(contents, pos, pairs):
    """returns the regions corresponding to nearest matching environments"""

    def extract_begin_region(region):
        s = contents[region[0]:region[1]]
        boffset = len("\\begin{")
        m = begin_re.search(s)
        if m:
            boffset = m.regs[1][0]
        return [region[0] + boffset, region[1] - 1]

    def extract_end_region(region):
        boffset = len("\\end{")
        return [region[0] + boffset, region[1] - 1]

    new_regions = []
    try:
        begin, end = _find_surrounding_pair(contents, pairs, pos)
    except:
        return []
    begin_region = extract_begin_region(begin)
    end_region = extract_end_region(end)
    new_regions.append(begin_region)
    new_regions.append(end_region)

    return new_regions

# ------------------------------

def get_lines(text, start, end):
    line_start = text.rfind('\n', 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find('\n', end)
    line_end = len(text) if line_end == -1 else line_end
    return text[line_start:line_end]

# ------------------------------

comment_line_re = re.compile(r"\s*%.*")

def is_comment(contents, reg):
    line_str = get_lines(contents, reg[0], reg[1])
    return comment_line_re.match(line_str) is not None

# ------------------------------

def filter_non_comment_regions(contents, regions):
    
    return [r for r in regions if not is_comment(contents, r)]

# ------------------------------

def _extract_env_name(contents, region, is_begin):
    s = contents[region[0]:region[1]]
    if is_begin:
        m = begin_re.search(s)
    else:
        m = end_re.search(s)
    if m:
        return m.group(1)
    return ""

# ------------------------------

def _find_surrounding_pair(contents, pairs, pos):
    matching_pairs = []
    for begin, end in pairs:
        if begin[0] <= pos <= end[1]:
            name_begin = _extract_env_name(contents, begin, is_begin=True)
            name_end = _extract_env_name(contents, end, is_begin=False)
            if name_begin == name_end:
                matching_pairs.append((begin, end, begin[0]))
    if not matching_pairs:
        return []

    matching_pairs.sort(key=lambda x: -x[2])
    return (matching_pairs[0][0], matching_pairs[0][1])

# ------------------------------

def match_envs(contents, begins, ends):

    events = []
    for b in begins:
        text = contents[b[0]:b[1]]
        m = begin_re.search(text)
        if m:
            name = m.group(1)
            events.append(("begin", b, name))
    for e in ends:
        text = contents[e[0]:e[1]]
        m = end_re.search(text)
        if m:
            name = m.group(1)
            events.append(("end", e, name))

    events.sort(key=lambda x: x[1][0])

    stack = []
    pairs = []

    for kind, reg, name in events:
        if kind == "begin":
            stack.append((reg, name))
        elif kind == "end":
            for i in reversed(range(len(stack))):
                b_reg, b_name = stack[i]
                if b_name == name:
                    pairs.append((b_reg, reg))
                    del stack[i]
                    break

    return pairs
