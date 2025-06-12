#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sublime
from sublime_plugin import TextCommand
import re
import time
import unicodedata
from sublime import Region
from .parse_aux import parse_aux_file, extract_brace_group
from .parse_out import parse_out_file
from .detect_environment import (
    find_env_regions, filter_non_comment_regions, match_envs,
    begin_re, end_re, is_comment)
import threading

# -------------------------- Characters --------------------------
# Changes here should also be reported in latexoutline.sublime-syntax
# Suggestions: ▪ ⌑ ⦾ ⁌ ∙ ◦ ⦿ ■ 𑗕 ◉ • ⸱ ‣ ▫ ⊙ ⊛ ⏺ ʘ ⏿ ◎ ⦿ ⌖
lo_chars = {
    'part': '■',
    'chapter': '𑗕',
    'section': '⏺',
    'subsection': '⊛',
    'subsubsection': '‣',
    'paragraph': '⸱',
    'frametitle': '▫',
    'label': '›',
    'copy': '❐',
    'takealook': '⌖'}

# --------------------- Detected symbols -------------------------
# pattern / name / level
symbols_list = [
    ("title", "title", -1),
    ("label", "label", 20),
    ("part", "part", 0),
    ("chapter", "chapter", 1),
    ("section", "section", 2),
    ("subsection", "subsection", 3),
    ("subsubsection", "subsubsection", 4),
    ("paragraph", "paragraph", 5),
    ("frametitle", "frametitle", 3),
]

# ------------------- Some regex patterns -----------------------
eq_pattern = re.compile(r'''
    (align|alignat|aligned|alignedat|displaymath
    |eqnarray|equation|flalign|gather|gathered
    |math|multline|x?xalignat|split
    |dmath|dseries|dgroup|darray|dsuspend)(\*)?
''', re.VERBOSE)
part_pattern = re.compile(r"^Part")
chap_pattern = re.compile(r"^Chapter:")
symbols_patterns = [(re.compile(rf"\\({s[0]})(\*)?\s*(?:\[[^\]]*\])?\{{"), s[1], s[2])
                    for s in symbols_list]

# ----------------------------------------------------------------

# ----------------------------------------------------------------------------#
#                                                                             #
#                               MAIN FUNCTIONS                                #
#                                                                             #
# ----------------------------------------------------------------------------#


def show_outline(window, side="right", outline_type="toc", path=None):
    """
    Creates the outline view. 
    Filling it will be taken care of by LatexOutlineEventHandler which in
    particular calls the on_activated method (and then refresh_lo_view and
    fill_symlist).
    """

    # Creates the outline view otherwise
    prev_focus = window.active_view()
    new_view = create_outline_view(window)
    view_name = "Table of contents"
    name = u"𝌆 {0}".format(view_name)
    new_view.set_name(name)
    new_view.settings().set('side', side)
    new_view.settings().set('current_outline_type', outline_type)
    if path:
        new_view.settings().set('current_file', path)
        
    arrange_layout(new_view, side)
    
    nb_groups = window.num_groups()
    window.set_view_index(new_view, nb_groups-1, 0)
    
    window.focus_view(prev_focus)


# --------------------------

def fill_symlist(base_symlist, path, view, lo_view):
    '''
    Filters the symlist to only show sections and labels
    Prepares their presentation in the LO view, put it in the 'symlist' setting
    '''
    lo_settings = sublime.load_settings('latexoutline.sublime-settings')
    show_ref_nb = lo_settings.get('show_ref_numbers')
    show_env_names = lo_settings.get('show_environments_names')

    shift = 0
    if any(part_pattern.search(b["type"]) for b in base_symlist):
        shift = 2
    elif any(chap_pattern.search(b["type"]) for b in base_symlist):
        shift = 1

    aux_data = get_aux_file_data(path)

    symlist = []
    for item in base_symlist:
        rgn = item["region"]
        sym = item["content"]
        type = item["type"]
        file = item["file"]
        level = item["level"]

        if show_ref_nb and aux_data:
            ref = get_ref(sym, type, aux_data)
        else:
            ref = None

        is_equation = False

        fancy_content = new_lo_line(sym, ref, type, is_equation=is_equation, 
                                    show_ref_nb=show_ref_nb, 
                                    show_env_names=show_env_names, shift=shift)

        # Creates the entry of the generated symbol list
        symlist.append(
            {"region": (rgn[0], rgn[1]),
             "type": type,
             "content": sym,
             "is_equation": is_equation,
             "file": file, 
             "fancy_content": fancy_content,
             "ref": ref,
             "level": level,
             "env_type": ""}
            )

    lo_view.settings().erase('symlist')
    lo_view.settings().set('symlist', symlist)

    # Getting environment names can take some time; better let it in the background
    if show_env_names:
        thread = GetEnvNamesTask(view)
        thread.start()

    return symlist


# --------------------------

def refresh_lo_view(lo_view, path, view, outline_type):
    '''Completely refresh the contents of the outline view'''

    # Get the section/label list
    symlist, tex_files = get_symbols(path)
    new_sym_list = fill_symlist(symlist, path, view, lo_view)
    active_view_id = view.id()

    if lo_view is not None:
        # Save variables to the sidebar view settings
        if active_view_id:
            lo_view.settings().set('active_view', active_view_id)
        if path:
            lo_view.settings().set('current_file', path)
        lo_view.settings().set('file_list', tex_files)
        # Fills the sidebar contents
        fill_sidebar(lo_view, new_sym_list, outline_type)
        view.settings().set('sync_in_progress', False)
        sync_lo_view()


# --------------------------

def fill_sidebar(lo_view, sym_list, outline_type):
    '''Fills the contents of the outline view'''
    lo_view.run_command('latex_outline_fill_sidebar', 
                        {'symlist': sym_list, 'outline_type': outline_type})

# ------

class LatexOutlineFillSidebarCommand(TextCommand):
    '''Text command for the latter'''
    def run(self, edit, symlist=None, outline_type="full"):
        
        type_nb = level_filter(outline_type)
        symlist_contents = [item["fancy_content"] for item in symlist 
                                if item["level"] <= type_nb]
        self.view.erase(edit, Region(0, self.view.size()))
        self.view.insert(edit, 0, "\n".join(symlist_contents))
        self.view.sel().clear()
       

# --------------------------

def sync_lo_view():
    ''' sync the outline view with current place in the LaTeX file '''

    lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
    if not lo_view:
        return

    label_level = get_symbol_level("label")
    
    outline_type = lo_view.settings().get('current_outline_type')
    type_nb = level_filter(outline_type)

    view = sublime.active_window().active_view()
    
    # Refresh the regions (only) in the current symlist
    refresh_regions(lo_view, view)
    settings_sym_list = lo_view.settings().get('symlist')

    sym_list = [item for item in settings_sym_list
                    if item["level"] <= type_nb]
    
    point = view.sel()[0].end()
    file_path = view.file_name()
    partial_symlist = [s for s in sym_list if s["file"] == file_path]
    
    if len(partial_symlist) >0: 
        range_lows = [view.line(item['region'][0]).begin() for item in partial_symlist]
        range_sorted = [0] + range_lows[1:len(range_lows)] + [view.size()]
        partial_index = binary_search(range_sorted, point) - 1
        lo_line = sym_list.index(partial_symlist[partial_index])

        # Highlight the previous (sub)section rather than the label
        max_level = min(type_nb, label_level - 1)
        if outline_type != "toc":
            for i in range(lo_line, -1, -1):
                if sym_list[i]["level"] <= max_level:
                    lo_line = i
                    break
        # A shift if there is a title
        is_title = any([s for s in sym_list if s["type"] == "title"])
        if is_title and lo_line != 0:
            lo_line += 1
    else:
        lo_line=0

    lo_point_start = lo_view.text_point_utf8(lo_line, 0)
    lo_view.show_at_center(lo_point_start, animate=True)
    lo_view.sel().clear()
    lo_view.sel().add(lo_point_start)
    # For some reason, 
    # the following makes the outline highlighting more reliable.
    lo_view.set_syntax_file('Packages/LaTeXOutline/latexoutline.sublime-syntax')

    view.settings().set('sync_in_progress', False)


# --------------------------------------------------------------------------#
#                                                                           #
#                          Intermediate functions                           #
#                                                                           #
# --------------------------------------------------------------------------#


def get_ref(sym, type, aux_data):
    '''Obtains the reference of the entry'''
    
    ref = None

    # Labels
    if type == "label":
        ref = next((entry['reference'] for entry in aux_data
                    if sym == entry['main_content']), '*')
    # Sections
    elif type != "title":
        for i, data_item in enumerate(aux_data):
            if data_item['entry_type'] != type or data_item['reference'] == '':
                continue
            # Minimal check, this is very unprecise, but should work in most cases
            # ts = normalize_for_comparison(sym)
            # if ts == normalize_for_comparison(data_item['main_content']):
            correct_item = aux_data.pop(i)
            ref = correct_item['reference']
            break

    return ref


# --------------------------

def new_lo_line(sym, ref, type, is_equation=False,
                env_type="Ref.", show_ref_nb=False, show_env_names=False, shift=0):
    '''Creates the content to be displayed'''
    
    prefix = {
        "title": "❝",
        "part": lo_chars['part'] + ' ',
        "chapter": (' ' if shift == 2 else '') + lo_chars['chapter'] + ' ',
        "section": ' ' * shift + lo_chars['section'] + ' ',
        "subsection": ' ' * (shift + 1) + lo_chars['subsection'] + ' ',
        "subsubsection": ' ' * (shift + 2) + lo_chars['subsubsection'] + ' ',
        "paragraph": ' ' * (shift + 3) + lo_chars['paragraph'] + ' ',
        "frametitle": lo_chars['frametitle'] + ' ',
        "label": '  ' + lo_chars['label'],
        "copy": ' ' + lo_chars['copy'],
        "takealook": ' ' + lo_chars['takealook'] + ' ',
    }
    postfix = {"title" : "❞",}
    # Labels
    if type == "label":
        if show_ref_nb:
            if ref and is_equation:
                new_sym_line = (prefix["label"] + 'Eq. (' + ref +')'
                                + prefix["copy"] + prefix["takealook"] + '{' + sym + '}')
            elif ref:
                new_sym_line = (prefix["label"] + env_type + ' ' + ref 
                                + prefix["copy"] + prefix["takealook"] + '{' + sym + '}')
            else:
                new_sym_line = (prefix["label"] + env_type + ' *' 
                                + prefix["copy"] + prefix["takealook"] + '{' + sym + '}')
        elif show_env_names:
            new_sym_line = (prefix["label"] + env_type + ' ' + prefix["copy"] 
                            + prefix["takealook"] + '{' + sym + '}')
        else:
            new_sym_line = prefix["label"] + sym + prefix["copy"] + prefix["takealook"]
    # Sections
    elif type == "title":
        new_sym_line = prefix["title"] + sym + postfix["title"] +"\n"
    else:
        simple_sym = re.sub(r'\\(emph|textbf)\{([^}]*)\}', r'\2', sym)
        simple_sym = re.sub(r'\\label\{[^\}]*\}\s*', '', simple_sym)
        simple_sym = re.sub(r'\\mbox\{([^\}]*)\}', r'\1', simple_sym)
        simple_sym = re.sub(r'\s*~\s*', r' ', simple_sym)
        if '*' in type:
            new_sym_line = prefix[type[:-1]] + '* ' + simple_sym + prefix["takealook"]
        elif show_ref_nb and ref:
            new_sym_line = prefix[type] + ref + ' ' + simple_sym + prefix["takealook"]
        else:
            new_sym_line = prefix[type] + simple_sym + prefix["takealook"]

        new_sym_line = re.sub(r'\\(emph|textbf)\{([^}]*)\}', r'\2', new_sym_line)
        new_sym_line = re.sub(r'\\label\{[^\}]*\}\s*', '', new_sym_line)
        new_sym_line = re.sub(r'\\mbox\{([^\}]*)\}', r'\1', new_sym_line)
        new_sym_line = re.sub(r'\s*~\s*', r'', new_sym_line)

    return new_sym_line


# --------------------------
class GetEnvNamesTask(threading.Thread):
    def __init__(self, active_view):
        super().__init__()
        self.active_view = active_view

    def run(self):

        lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
        if not lo_view:
            return
        symlist = lo_view.settings().get('symlist')
        lo_settings = sublime.load_settings('latexoutline.sublime-settings')
        show_env_names = lo_settings.get('show_environments_names')

        path = lo_view.settings().get('current_file')
        out_data = get_out_file_data(path)

        shift = 0
        if "part" in [sym["type"] for sym in symlist]:
            shift = 2
        elif "chapter" in [sym["type"] for sym in symlist]:
            shift = 1

        tex_files = lo_view.settings().get('file_list')

        if len(tex_files) == 0:
            tex_files = get_all_latex_files(self.active_view.file_name())
            
        for file_path in tex_files:
            if not os.path.exists(file_path):
                pass
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    contents = f.read()
            except:  
                pass
            # Look for matching \begin{...}/\end{...} pairs in the document
            st_begins = [(m.start(), m.end()) for m in re.finditer(begin_re, contents)]
            st_ends = [(m.start(), m.end()) for m in re.finditer(end_re, contents)]
            begins = filter_non_comment_regions(contents, st_begins)
            ends = filter_non_comment_regions(contents, st_ends)
            pairs = match_envs(contents, begins, ends)

            for i in range(len(symlist)):
                sym = symlist[i]
                if sym["file"] != file_path:
                    continue

                if sym["type"] != "label":
                    if out_data is not None and len(out_data)>0 and sym["type"] != "title":
                        # Adds section names from the .out file
                        for l, data in enumerate(out_data):
                            if data[0] == sym["type"] and data[1] == sym["ref"]:
                                new_content = data[2]
                                out_data.pop(l)
                                symlist[i]["fancy_content"] = new_lo_line(
                                                                new_content,
                                                                sym["ref"], 
                                                                sym["type"], 
                                                                False,
                                                                env_type="",
                                                                show_ref_nb=True,
                                                                show_env_names=show_env_names,
                                                                shift=shift)
                                break
                    else:
                        continue
                else:
                    rgn = sym["region"]
                    env_regions = find_env_regions(contents, rgn[0], pairs)

                    if (len(env_regions) == 0 
                            or contents[env_regions[0][0]:env_regions[0][1]] == "document"):
                        env_type = " ↪ Ref."
                        is_equation = False
                    else:
                        env_type = contents[env_regions[0][0]:env_regions[0][1]]
                        is_equation = equation_test(env_type)
                        env_type = env_type.title()

                    symlist[i]["env_type"] = env_type
                    symlist[i]["is_equation"] = is_equation
                    symlist[i]["fancy_content"] = new_lo_line(
                                                    sym["content"],
                                                    sym["ref"], 
                                                    sym["type"], 
                                                    is_equation,
                                                    env_type=env_type,
                                                    show_ref_nb=True,
                                                    show_env_names=show_env_names,
                                                    shift=shift)

        # If it changed in the meantime
        lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
        if lo_view:
            lo_view.settings().set('symlist', symlist)
            outline_type = lo_view.settings().get('current_outline_type')
            fill_sidebar(lo_view, symlist, outline_type)

        
# --------------------------

def refresh_regions(lo_view, active_view):
    '''
    Merely refresh the regions in the symlist
    '''
    in_sync = lo_view.settings().get('regions_refreshed_recently')
    if in_sync:
        return
    lo_view.settings().set('regions_refreshed_recently', True)
    path = active_view.file_name()
    symlist = lo_view.settings().get('symlist')
    content = active_view.substr(sublime.Region(0, active_view.size()))
    new_symlist = extract_symbols_from_content(content, path)

    for i in range(0, len(symlist)-1):
        if symlist[i]["file"] != path:
            pass
        first = None
        item = symlist[i]
        for k, it in enumerate(new_symlist):
            if it["content"] == item["content"]:
                first = new_symlist.pop(k)
                break      

        if first:
            region = first["region"]
            symlist[i]["region"] = region

    lo_view.settings().set('symlist', symlist)
    sublime.set_timeout(
        lambda: lo_view.settings().set('regions_refreshed_recently', False), 20000)
    return 

# --------------------------

def light_refresh(lo_view, active_view, outline_type):
    '''
    Refresh the regions, add new/remove old entries
    '''
    symlist = lo_view.settings().get('symlist')
    lo_settings = sublime.load_settings('latexoutline.sublime-settings')
    show_ref_nb = lo_settings.get('show_ref_numbers')
    show_env_names = lo_settings.get('show_environments_names')
    path = active_view.file_name()
    unfiltered_st_symlist, tex_files = get_symbols(path)

    shift = 0
    if "part" in [sym["type"] for sym in symlist]:
        shift = 2
    elif "chapter" in [sym["type"] for sym in symlist]:
        shift = 1

    new_symlist = []
    for sym in unfiltered_st_symlist:
        item = {}
        key_unfound = True
        for i in range(len(symlist)):
            if sym["content"] == symlist[i]["content"]:
                reg = symlist[i]["region"]
                item=symlist.pop(i)
                item["region"] = reg
                key_unfound = False
                break

        if key_unfound:
            is_equation = False
            fancy_content = new_lo_line(sym["content"], "…", sym["type"], 
                                        is_equation, show_ref_nb=show_ref_nb, 
                                        show_env_names=show_env_names, 
                                        shift=shift)
            item = {"region": sym["region"],
                    "type": sym["type"],
                    "content": sym["content"],
                    "is_equation": is_equation,
                    "fancy_content": fancy_content,
                    "file": path,
                    "ref": "…",
                    "level": get_symbol_level(sym["type"]),
                    "env_type": ""}

        new_symlist.append(item)
        
    lo_view.settings().set('symlist', new_symlist)
    return new_symlist

# --------------------------

def copy_label(active_view, region_position):
    if active_view and region_position:
        text_from_region = active_view.substr(
            sublime.Region(region_position[1], active_view.size()))

        label_match = re.search(r'\\label\{([^}]*)\}', text_from_region)
        command_match = re.search(r'\\\w*\{', text_from_region)
        if label_match and (
          not command_match
          or label_match.start() <= command_match.start()
        ):
            label = label_match.group(1)
            sublime.set_clipboard(label)
            sublime.active_window().status_message(
                f" ✓ Copied reference '{label}' to the clipboard")
        else:
            section = active_view.substr(
                sublime.Region(region_position[0], region_position[1]))
            sublime.active_window().status_message(
                f" ⨉ No \\label found for '{section}'")

# --------------------------

def create_outline_view(window):

    active_view = window.active_view()
    view = window.new_file()
    view.set_syntax_file('Packages/LaTeXOutline/latexoutline.sublime-syntax')
    view.set_scratch(True)
    
    if view.settings().get('outline_inherit_color_scheme'):
        view.settings().set(
            'color_scheme', active_view.settings().get('color_scheme'))
    else:
        view.settings().add_on_change(
            'color_scheme', lambda: set_proper_scheme(view))
        
    return view

# --------------------------

def set_proper_scheme(view):

    lo_settings = sublime.load_settings('latexoutline.sublime-settings')
    if view.settings().get('color_scheme') == lo_settings.get('color_scheme'):
        return
    view.settings().set('color_scheme', lo_settings.get('outline_color_scheme'))
    view.settings().set('word_wrap', lo_settings.get('line_wrap'))

# --------------------------

def arrange_layout(view, side):
    """
    Arranges the window layout after the outline view is open.
    """
    window = view.window()
    width = calc_width(view)

    current_layout = window.layout()
    rows = current_layout["rows"]
    cols = current_layout["cols"]
    cells = current_layout["cells"]

    x_max = max([c[2] for c in cells])
    y_max = max([c[3] for c in cells])

    if side == "right":
        left_cols = [c * (1-width) for c in cols if c < 1.0]
        right_cols = [1 - width, 1.0]
        cols = left_cols + right_cols
        new_cell = [x_max, 0, x_max+1, y_max]
        cells.append(new_cell)
        new_layout = {"cols": cols, "rows": rows, "cells": cells}
        window.set_layout(new_layout)
        
    elif side == "left":
        right_cols = [width + c * (1-width) for c in cols if c > 0.0]
        left_cols = [0.0, width]
        cols = left_cols + right_cols
        cells = [[c[0]+1, c[1], c[2]+1, c[3]] for c in cells]
        new_cell = [0, 0, 1, y_max]
        cells.append(new_cell)
        new_layout = {"cols": cols, "rows": rows, "cells": cells}
        window.set_layout(new_layout)

    elif side == "other":
        return

# --------------------------

def reduce_layout(window, lo_view, lo_group, sym_side):
    '''Determine the new layout when closing LO'''

    current_layout = window.layout()
    rows = current_layout["rows"]
    cols = current_layout["cols"]
    cells = current_layout["cells"]
    x_min, y_min, x_max, y_max = cells[lo_group]
    width = cols[x_min + 1] - cols[x_min]
    new_cells = [c for c in cells if c[2] <= x_min] \
        + [[c[0]-1, c[1], c[2]-1, c[3]] for c in cells if c[0] >= x_max] 
    
    if sym_side == "right":
        new_cols = [c / (1-width) for c in cols if c < 1 - width] \
                + [c for c in cols if c > 1 - width]
    elif sym_side == "left":
        new_cols = [c for c in cols if c < width] \
                + [(c - width) / (1-width) for c in cols if c > width]
    else:
        return None

    return {"cols": new_cols, "rows": rows, "cells": new_cells}

# --------------------------

def calc_width(view):
    ''' Return float width, which must be 0.0 < width < 1.0'''
    width = view.settings().get('outline_width', 0.3)
    if isinstance(width, float) and width > 0 and width < 1:
        width = round(width, 2) + 0.00001
    else:
        sublime.error_message(f'Impossible to set outline_width to {width}.'
                              f'Fallback to default 0.3 for now.')
        width = 0.30001
    return width

# --------------------------

def get_sidebar_view_and_group(window):
    '''
    In which view and group LO is
    '''
    views = window.views()
    lo_view = None
    lo_group = None
    for v in views:
        if 'latexoutline.sublime-syntax' in v.settings().get('syntax'):
            lo_view = v
            lo_group, i = window.get_view_index(lo_view)
    return (lo_view, lo_group)

# --------------------------

def get_sidebar_status(window):
    '''
    Is LO on or not
    '''
    sidebar_on = False
    for v in window.views():
        if 'latexoutline.sublime-syntax' in v.settings().get('syntax'):
            sidebar_on = True

    return sidebar_on

# --------------------------

def get_symbols(file_path):
    tex_files = get_all_latex_files(file_path)
    all_symbols = []
    comment_pkg_in = False
    for f in tex_files:
        content = get_contents_from_latex_file(f)
        if content:
            if uses_comment_package(content):
                comment_pkg_in = True
            more_symbols = extract_symbols_from_content(content, f)
            if comment_pkg_in:
                comment_blocks = find_comment_blocks(content)
                more_symbols = [item for item in more_symbols 
                                if not point_in_block(item["region"][0], comment_blocks)]

        else:
            more_symbols = []
        all_symbols.extend(more_symbols)
    file_order = {path: index for index, path in enumerate(tex_files)}
    all_symbols.sort(key=lambda s: (file_order.get(s["file"], 9999), s["region"][0]))
    return all_symbols, tex_files

# --------------------------

def get_aux_file_data(path):
    '''
    Given a .tex file, gather information from the .aux file
    '''
    if path:
        aux_file = os.path.splitext(path)[0] + ".aux"
        if os.path.exists(aux_file):
            all_data = parse_aux_file(aux_file)
            return all_data
    else:
        return None

# --------------------------

def get_out_file_data(path):
    '''
    Given a .tex file, gather information from the .out file
    '''
    if path:
        out_file = os.path.splitext(path)[0] + ".out"
        if os.path.exists(out_file):
            out_data = parse_out_file(out_file)
            return out_data
    else:
        return None
           
# --------------------------

def binary_search(array, x):
    '''
    Given a sorted array, returns the location of x if inserted into the array
    '''
    low = 0
    high = len(array) - 1
    mid = 0
    while low < high:
        mid = (high + low) // 2
        if array[mid] <= x:
            low = mid + 1
        else:
            high = mid
    return low

# --------------------------

def normalize_for_comparison(s):
    s = re.sub(r'\n', ' ', s)
    s = re.sub(r'\$[^\$]*?\$', '', s)
    s = re.sub(r'\\nonbreakingspace\s+', '~', s)
    # s = re.sub(r'\\label\{[^\}]*\}\s*', '', s)
    s = re.sub(r'\\[a-zA-Z]*(?:\{[^\}]*\})\s*', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    return unicodedata.normalize("NFC", s)

# --------------------------

def get_contents_from_latex_file(file_path):

    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            return content
    except:
        return None

# --------------------------

def extract_symbols_from_content(content, file_path):
    symbols = []    
    for sym_regex, base_type, level in symbols_patterns:
        for match in sym_regex.finditer(content):
            cmd_name = match.group(1)
            if is_comment(content, (match.start(),match.end())):
                continue
            has_star = match.group(2)
            sym_type = cmd_name + (has_star or "")

            brace_start = match.end() - 1
            name, brace_end = extract_brace_group(content, brace_start)
            if name:
                symbols.append({
                    "content": name,
                    "type": sym_type,
                    "file": file_path,
                    "region": [match.start(), brace_end],
                    "level": level,
                })

    return symbols

# --------------------------

def get_all_latex_files(file_path):
    all_files = [file_path]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        included_files = re.findall(r"\\(?:input|include)\{(.+?)\}", content)
        base_dir = os.path.dirname(file_path)
        for rel in included_files:
            full_path = os.path.join(base_dir, rel)
            if not full_path.endswith(".tex"):
                full_path += ".tex"
            if os.path.exists(full_path):
                all_files.append(full_path)
    except:
        pass
    return all_files

# --------------------------

def equation_test(type):
    return bool(eq_pattern.match(type))

# --------------------------

def navigate_to(view, pos, lo_view):
    if view.is_loading():
        sublime.set_timeout(lambda: navigate_to(view, pos, lo_view), 100)
    else:
        region = sublime.Region(pos, pos)
        view.sel().clear()
        view.sel().add(region)
        view.window().focus_view(view)
        view.show_at_center(region)
        lo_view.settings().set('active_view', view.id())

# --------------------------

def takealook(file, region, view):
    window = view.window()
    contents = get_contents_from_latex_file(file)
    panel = window.find_output_panel('lo_takealook')
    if panel is None:
        panel = window.create_output_panel('lo_takealook')
    panel.run_command('lo_insert_in_view', {'text': contents})
    window.run_command('show_panel', {'panel': 'output.lo_takealook'})
    st_region = sublime.Region(region[0], region[0])
    panel.sel().add(st_region)
    panel.show_at_center(st_region)
    panel.add_regions(
            "takealook", 
            panel.lines(sublime.Region(region[0],region[1])),
            icon='Packages/LaTeXOutline/images/chevron.png',
            scope='region.bluish',
            flags=1024,
        )
    sublime.set_timeout_async(lambda: panel.erase_regions("takealook"), 5000)
    panel.set_syntax_file('Packages/LaTeX/LaTeX.sublime-syntax')
    panel.set_read_only(True)
    window.focus_view(view)

# --------------------------

def next_in_cycle(item, my_list):
    if not my_list:
        return None 
    if item in my_list:
        index = my_list.index(item)
        return my_list[(index + 1) % len(my_list)]
    else:
        return my_list[0]

# --------------------------

def get_symbol_level(symbol):
    for pattern in symbols_list:
        if symbol == pattern[0]:
            return pattern[2]
    return 999

# --------------------------

def level_filter(outline_type):
    label_level = get_symbol_level("label")
    if outline_type == "toc":
        type_nb = label_level - 1
    elif outline_type == "full":
        type_nb = label_level
    else:
        type_nb = get_symbol_level(outline_type)
    return type_nb

# -------------------

def refresh_with_new_aux(aux_file=None, window=None, i=0, step=0):
    if aux_file is None or window is None:
        return
    if i < 50:
        i += 1
        if os.path.exists(aux_file):
            modification_time = os.path.getmtime(aux_file)
            current_time = time.time()
            if current_time - modification_time < 0.3:
                new_step = 1
            else:
                new_step = 2 if step == 1 else 0
            if new_step == 2:
                # .aux file has been recently modified, but not for the past 0.3s
                lo_view, lo_group = get_sidebar_view_and_group(window)
                outline_type = lo_view.settings().get('current_outline_type')
                refresh_lo_view(lo_view, window.active_view().file_name(),
                                window.active_view(), outline_type)
                return
        else:
            new_step = 0
        sublime.set_timeout_async(
            lambda: refresh_with_new_aux(aux_file, window, i, new_step), 300)
    return

# -------------------

class LoInsertInView(TextCommand):
    def run(self, edit, text):
        self.view.erase(edit, Region(0, self.view.size()))
        self.view.insert(edit, 0, text)
        self.view.sel().clear()

# -------------------

def uses_comment_package(content):

    pattern = re.compile(r'\\usepackage(?:\[[^\]]*\])?{[^}]*\bcomment\b[^}]*}')
    for match in pattern.finditer(content):
        start = match.start()
        line_start = content.rfind('\n', 0, start) + 1
        line_end = content.find('\n', start)
        if line_end == -1:
            line_end = len(content)
        line = content[line_start:line_end]
        if not line.strip().startswith('%'):
            return True
    return False

# -------------------

def find_comment_blocks(text):
    start_tag = r"\begin{comment}"
    end_tag = r"\end{comment}"
    stack = []
    top_level_blocks = []

    index = 0
    while index < len(text):
        next_start = text.find(start_tag, index)
        next_end = text.find(end_tag, index)

        if next_start != -1 and (next_start < next_end or next_end == -1):
            stack.append(next_start)
            index = next_start + len(start_tag)
        elif next_end != -1:
            if not stack:
                # Unmatched \\end{comment}
                break
            start_pos = stack.pop()
            if not stack: 
                top_level_blocks.append((start_pos, next_end + len(end_tag)))
            index = next_end + len(end_tag)
        else:
            break

    # if stack:
    #  Unmatched \\begin{comment}
        # pass
    return top_level_blocks

# -------------------

def point_in_block(point, blocks):
    for start, end in blocks:
        if start <= point < end:
            return True
    return False

