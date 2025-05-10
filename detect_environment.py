# Adaptation of LaTeXTools' change_environment.py
# LaTeXTools is distributed under the MIT Licence,
# Copyright (c) 2024 Sublime Text Packages
# https://github.com/SublimeText/LaTeXTools

import sublime
import sublime_plugin
import re

def _find_env_regions(view, pos, begins, ends, secs):
    """returns the regions corresponding to nearest matching environments"""
    begin_re = r"\\begin(?:\[[^\]]*\])?\{([^\}]*)\}"
    end_re = r"\\end\{([^\}]*)\}"
    # compile the begin_re (findall does not work if its compiled)
    begin_re = re.compile(begin_re)

    comment_line_re = re.compile(r"\s*%.*")

    def is_comment(reg):
        line_str = view.substr(view.line(reg))
        return comment_line_re.match(line_str) is not None
    begins = [b for b in begins if not is_comment(b)]
    ends = [e for e in ends if not is_comment(e)]

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

    # partition the open and closed environments
    begin_before, begin_after =\
        _partition(begins, lambda b: b.begin() <= pos)
    end_before, end_after =\
        _partition(ends, lambda e: e.end() < pos)
    sec_before, sec_after =\
        _partition(secs, lambda e: e.begin() < pos)

    # get the nearest open environments
    try:
        begin = _get_closest_begin(begin_before, end_before)
        end = _get_closest_end(end_after, begin_after)
        sec = _get_closest_section(sec_before)
    except NoEnvError as e:
        sublime.status_message(e.args[0])
        return []
    
    # if a \section (or \subsection, etc.) is met backwards before meeting
    # a \begin, then abort
    if sec and sec.begin() > begin.begin():
        return []

    # extract the regions for the environments
    begin_region = extract_begin_region(begin)
    end_region = extract_end_region(end)

    # validity check: matching env name
    if view.substr(begin_region) == view.substr(end_region):
        new_regions.append(begin_region)
        new_regions.append(end_region)
    elif one_sel:
        sublime.status_message(
            "The environment begin and end does not match:"
            "'{0}' and '{1}'"
            .format(view.substr(begin_region), view.substr(end_region))
        )
    if not new_regions:
        sublime.status_message("Environment detection failed")

    return new_regions


def _partition(env_list, is_before):
    """partition the list in the list items before and after the sel"""
    before, after = [], []
    iterator = iter(env_list)
    while True:
        try:
            item = next(iterator)
        except:
            break
        if is_before(item):
            before.append(item)
        else:
            after.append(item)
            after.extend(iterator)
            break
    return before, after


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
