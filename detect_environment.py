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

begin_re = r"\\begin(?:\[[^\]]*\])?\{([^\}]*)\}"
end_re = r"\\end\{([^\}]*)\}"
# compile the begin_re (findall does not work if its compiled)
begin_re = re.compile(begin_re)
end_re = re.compile(end_re)

# -------------------------------------------------

def _find_env_regions(contents, pos, pairs):
    """returns the regions corresponding to nearest matching environments"""
# view -> contents: substr() begin() end()
    def extract_begin_region(region):
        # s = view.substr(region)
        s = contents[region[0]:region[1]]
        boffset = len("\\begin{")
        m = begin_re.search(s)
        if m:
            boffset = m.regs[1][0]
        # return sublime.Region(region.begin() + boffset, region.end() - 1)
        return [region[0] + boffset, region[1] - 1]
# view -> contents: begin() end()
    def extract_end_region(region):
        boffset = len("\\end{")
        # return sublime.Region(region.begin() + boffset, region.end() - 1)
        return [region[0] + boffset, region[1] - 1]

    new_regions = []

    # get the nearest open environments
    try:
# view -> contents: view
        begin, end = _find_surrounding_pair(contents, pairs, pos)
    except NoEnvError:
        return []
    
    # extract the regions for the environments
    begin_region = extract_begin_region(begin)
    end_region = extract_end_region(end)

# view -> contents: substr()
    # validity check: matching env name
    # if view.substr(begin_region) == view.substr(end_region):
    if contents[begin_region[0]:begin_region[1]] == contents[end_region[0]:end_region[1]]:
        new_regions.append(begin_region)
        new_regions.append(end_region)

    return new_regions

# ------------------------------

class NoEnvError(Exception):
    pass

# ------------------------------
# view -> contents  ! view.line
def filter_non_comment_regions(contents, regions):
    comment_line_re = re.compile(r"\s*%.*")
    
    def get_lines(text, start, end):
        line_start = text.rfind('\n', 0, start)
        line_start = 0 if line_start == -1 else line_start + 1
        line_end = text.find('\n', end)
        line_end = len(text) if line_end == -1 else line_end
        return text[line_start:line_end]

    def is_comment(reg):
        line_str = get_lines(contents, reg[0], reg[1])
        return comment_line_re.match(line_str) is not None

    return [r for r in regions if not is_comment(r)]

# ------------------------------
# view -> contents, just substr
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
# view -> contents: begin() and end()
def _find_surrounding_pair(contents, pairs, pos):
    matching_pairs = []
    for begin, end in pairs:
        if begin[0] <= pos <= end[1]:
            name_begin = _extract_env_name(contents, begin, is_begin=True)
            name_end = _extract_env_name(contents, end, is_begin=False)
            if name_begin == name_end:
                matching_pairs.append((begin, end, begin[0]))
    if not matching_pairs:
        raise NoEnvError("No matching environment found")

    matching_pairs.sort(key=lambda x: -x[2])
    return matching_pairs[0][0], matching_pairs[0][1]

# ------------------------------
# view -> contents: begin() 
def _match_envs(begins, ends):
    """Match begin/end into a stack (one pass)"""
    stack = []
    pairs = []
    i, j = 0, 0
    while i < len(begins) and j < len(ends):
        if begins[i][0] < ends[j][0]:
            stack.append(begins[i])
            i += 1
        else:
            if stack:
                pairs.append((stack.pop(), ends[j]))
            j += 1
    return pairs
