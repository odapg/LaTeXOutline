# Adaptation of LaTeXTools' change_environment.py
# LaTeXTools is distributed under the MIT Licence,
# Copyright (c) 2024 Sublime Text Packages
# https://github.com/SublimeText/LaTeXTools

import sublime
import sublime_plugin
import re
import itertools
import bisect

begin_re = r"\\begin(?:\[[^\]]*\])?\{([^\}]*)\}"
end_re = r"\\end\{([^\}]*)\}"
# compile the begin_re (findall does not work if its compiled)
begin_re = re.compile(begin_re)
end_re = re.compile(end_re)

def _find_env_regions(view, pos, pairs):
    """returns the regions corresponding to nearest matching environments"""

    def extract_begin_region(region):
        """creates a sublime.Region: \\begin{|text|}"""
        s = view.substr(region)
        boffset = len("\\begin{")
        m = begin_re.search(s)
        if m:
            boffset = m.regs[1][0]
        return sublime.Region(region.begin() + boffset, region.end() - 1)

    def extract_end_region(region):
        """creates a sublime.Region: \\end{|text|}"""
        boffset = len("\\end{")
        return sublime.Region(region.begin() + boffset, region.end() - 1)

    new_regions = []

    # get the nearest open environments
    try:
        begin, end = _find_surrounding_pair(view, pairs, pos)
    except NoEnvError as e:
        sublime.status_message(e.args[0])
        return []
    
    # extract the regions for the environments
    begin_region = extract_begin_region(begin)
    end_region = extract_end_region(end)

    # validity check: matching env name
    if view.substr(begin_region) == view.substr(end_region):
        new_regions.append(begin_region)
        new_regions.append(end_region)
    if not new_regions:
        sublime.status_message("Environment detection failed")

    return new_regions

class NoEnvError(Exception):
    pass


def _get_closest_section(sec_before):
    """returns the closest \\section before"""
    sec_iter = reversed(sec_before)
    try:
        b = next(sec_iter)
    except:
        raise NoEnvError("No section detected")
    return b

def _get_closest_begin(begin_before, end_before):
    """returns the closest \\begin, that is open"""
    end_iter = reversed(end_before)
    begin_iter = reversed(begin_before)
    while True:
        try:
            b = next(begin_iter)
        except:
            raise NoEnvError("No open environment detected")
        try:
            e = next(end_iter)
        except:
            break
        if not b.begin() < e.begin():
            break
    return b


def _get_closest_end(end_after, begin_after):
    """returns the closest \\end, that is open"""
    end_iter = iter(end_after)
    begin_iter = iter(begin_after)
    while True:
        try:
            e = next(end_iter)
        except:
            raise NoEnvError("No closing environment detected")
        try:
            b = next(begin_iter)
        except:
            break
        if not e.begin() > b.begin():
            break
    return e


def filter_non_comment_regions(view, regions):
    comment_line_re = re.compile(r"\s*%.*")
    def is_comment(reg):
        line_str = view.substr(view.line(reg))
        return comment_line_re.match(line_str) is not None
    return [r for r in regions if not is_comment(r)]

def _extract_env_name(view, region, is_begin):
    s = view.substr(region)
    if is_begin:
        m = begin_re.search(s)
    else:
        m = end_re.search(s)
    if m:
        return m.group(1)
    return ""

def _find_surrounding_pair(view, pairs, pos):
    matching_pairs = []
    for begin, end in pairs:
        if begin.begin() <= pos <= end.end():
            name_begin = _extract_env_name(view, begin, is_begin=True)
            name_end = _extract_env_name(view, end, is_begin=False)
            if name_begin == name_end:
                matching_pairs.append((begin, end, begin.begin()))
    if not matching_pairs:
        raise NoEnvError("No matching environment found")

    matching_pairs.sort(key=lambda x: -x[2])
    return matching_pairs[0][0], matching_pairs[0][1]

def _match_envs(begins, ends):
    """Match begin/end into a stack (one pass)"""
    stack = []
    pairs = []
    i, j = 0, 0
    while i < len(begins) and j < len(ends):
        if begins[i].begin() < ends[j].begin():
            stack.append(begins[i])
            i += 1
        else:
            if stack:
                pairs.append((stack.pop(), ends[j]))
            j += 1
    return pairs
