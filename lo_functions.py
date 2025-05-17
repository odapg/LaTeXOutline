#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sublime
import sublime_plugin
from sublime_plugin import TextCommand
import re
import unicodedata
from sublime import Region
from .parse_aux import parse_aux_file
from .detect_environment import _find_env_regions
import time
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
    'takealook': '⌖',}

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
    particular calls the fill_sidebar command.
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

def fill_symlist(unfiltered_symlist, path, view):
    '''
    Filters the symlist to only show sections and labels
    Prepares their presentation in the LO view, put it in the 'symlist' setting
    '''
    lo_settings = sublime.load_settings('latexoutline.sublime-settings')
    show_ref_nb = lo_settings.get('show_ref_numbers')
    show_env_names = lo_settings.get('show_environments_names')

    pattern = r'(?:Part|Chapter|Section|Subsection|Subsubsection|Paragraph|Frametitle)\*?:.*|[^\\].*'
    filtered_symlist = [x for x in unfiltered_symlist if re.match(pattern, x[1])]
        
    part_pattern = re.compile(r"^Part")
    chap_pattern = re.compile(r"^Chapter:")
    
    shift = 0
    if any(part_pattern.search(b) for _, b in filtered_symlist):
        shift = 2
    elif any(chap_pattern.search(b) for _, b in filtered_symlist):
        shift = 1

    aux_data = get_aux_file_data(path)
    
    sym_list = []

    for item in filtered_symlist:
        rgn, sym, type, true_sym = extract_from_sym(item)

        if show_ref_nb and aux_data:
            ref, is_equation = get_ref(true_sym, type, aux_data)
        else:
            ref = None
            is_equation = None

        fancy_content = new_lo_line(true_sym, ref, type, is_equation=is_equation, 
                                    show_ref_nb=show_ref_nb, shift=shift)

        # Creates the entry of the generated symbol list
        sym_list.append(
            {"region": (rgn.a, rgn.b),
             "type": type,
             "content": sym,
             "truesym": true_sym,
             "is_equation": is_equation,
             "fancy_content": fancy_content,
             "ref": ref,
             "env_type": ""}
            )

    # Getting environment names can take some time; better let it in the background
    if show_env_names:
        thread = GetEnvNamesTask(view)
        thread.start()

    return sym_list


# --------------------------

def refresh_lo_view(lo_view, path, view, outline_type):
    '''Completely refresh the contents of the outline view'''

    # Get the section/label list
    unfiltered_st_symlist = get_st_symbols(view)
    sym_list = fill_symlist(unfiltered_st_symlist, path, view)
    active_view_id = view.id()

    if lo_view is not None:
        # Save variables to the sidebar view settings
        lo_view.settings().erase('symlist')
        lo_view.settings().set('symlist', sym_list)
        if active_view_id:
            lo_view.settings().set('active_view', active_view_id)
        if path:
            lo_view.settings().set('current_file', path)
        # Fills the sidebar contents
        fill_sidebar(lo_view, sym_list, outline_type)


# --------------------------

def fill_sidebar(lo_view, sym_list, outline_type):
    '''Fills the contents of the outline view'''
    lo_view.run_command('latex_outline_fill_sidebar', 
                                {'symlist': sym_list, 'outline_type': outline_type})

# --------------------------

class LatexOutlineFillSidebarCommand(TextCommand):
    '''Text command for the latter'''
    def run(self, edit, symlist=None, outline_type="full"):
        
        if outline_type == "toc":
            symlist_contents = [item["fancy_content"] for item in symlist 
                                if item["type"] != "label"]
        else:
            symlist_contents = [item["fancy_content"] for item in symlist]
            
        self.view.erase(edit, Region(0, self.view.size()))    
        self.view.insert(edit, 0, "\n".join(symlist_contents))
        self.view.sel().clear()
       

# --------------------------

def sync_lo_view():
    ''' sync the outline view with current place in the LaTeX file '''

    lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
    if not lo_view or not lo_view.settings().get('outline_sync'):
        return
    if lo_view is not None:
        outline_type = lo_view.settings().get('current_outline_type')
        view = sublime.active_window().active_view()

        # Refresh the regions (only) in the current symlist
        refresh_regions(lo_view, view)
        settings_sym_list = lo_view.settings().get('symlist')
        if outline_type == "toc":
            sym_list = [item for item in settings_sym_list
                                if item["type"] != "label"]
        else:
            sym_list = settings_sym_list
        
        point = view.sel()[0].end()
        range_lows = [view.line(item['region'][0]).begin() for item in sym_list]
        range_sorted = [0] + range_lows[1:len(range_lows)] + [view.size()]
        lo_line = binary_search(range_sorted, point) - 1
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


def get_ref(true_sym, type, aux_data):
    '''Obtains the reference of the entry'''
    
    ref = None
    is_equation = False

    # Labels
    if type == "label":
        ref, name = next(((entry['reference'], entry['entry_type']) for entry in aux_data
                                if true_sym == entry['main_content']), ('',''))
        if ref and name == 'equation':
            is_equation = True
    # Sections
    else:
        ts = normalize_for_comparison(true_sym)
        for i, data_item in enumerate(aux_data):
            # Minimal check, this is not very precise, but should work
            # in most cases
            if ts == normalize_for_comparison(data_item['main_content']):
                correct_item = aux_data.pop(i)
                ref = correct_item['reference']
                break

    return ref, is_equation


# --------------------------

def new_lo_line(true_sym, ref, type, is_equation=False,
                 env_type="Ref.", show_ref_nb=False, shift=0):
    '''Creates the content to be displayed'''
    
    prefix = {
    "part" : lo_chars['part'] + ' ',
    "chapter" : ' ' + lo_chars['chapter'] + ' ' if shift==2 else lo_chars['chapter'] + ' ',
    "section" : ' ' * shift + lo_chars['section'] + ' ',
    "subsection" : ' ' * (shift + 1) + lo_chars['subsection'] + ' ',
    "subsubsection" : ' ' * (shift + 2) + lo_chars['subsubsection'] + ' ',
    "paragraph" : ' ' * (shift + 3) + lo_chars['paragraph'] + ' ',
    "frametitle" : lo_chars['frametitle'] + ' ',
    "label" : '  ' + lo_chars['label'],
    "copy" : ' ' + lo_chars['copy'], # + ' ',
    "takealook" : ' ' + lo_chars['takealook'] + ' ',
    }
    
    # Labels
    if type == "label":
        if show_ref_nb and ref and is_equation:
            new_sym_line = (prefix["label"] + 'Eq. (' + ref +')'
                        + prefix["copy"] + prefix["takealook"] + '{' + true_sym + '}')
        elif show_ref_nb and ref:
            # env_type = "Ref."
            new_sym_line = (prefix["label"] + env_type + ' ' + ref 
                + prefix["copy"] + prefix["takealook"] + '{' + true_sym + '}')
        else:
            new_sym_line = prefix["label"] + true_sym + prefix["copy"] + prefix["takealook"]
    # Sections
    else:
        simple_sym = re.sub(r'\\(emph|textbf)\{([^}]*)\}', r'\2', true_sym)
        simple_sym = re.sub(r'\\label\{[^\}]*\}\s*', '', simple_sym)
        simple_sym = re.sub(r'\\mbox\{([^\}]*)\}', r'\1', simple_sym)
        simple_sym = re.sub(r'\s*~\s*', r' ', simple_sym)
        if '*' in type:
            new_sym_line = prefix[type[:-1]] + '* ' + simple_sym + prefix["takealook"]
        elif ref:
            new_sym_line = prefix[type] + ref + ' ' + simple_sym + prefix["takealook"]
        else:
            new_sym_line = prefix[type] + simple_sym + prefix["takealook"]

        new_sym_line = re.sub(r'\\(emph|textbf)\{([^}]*)\}', r'\2', new_sym_line)
        new_sym_line = re.sub(r'\\label\{[^\}]*\}\s*', '', new_sym_line)
        new_sym_line = re.sub(r'\\mbox\{([^\}]*)\}', r'\1', new_sym_line)
        new_sym_line = re.sub(r'\s*~\s*', r' ', new_sym_line)

    return new_sym_line


# --------------------------
class GetEnvNamesTask(threading.Thread):
    def __init__(self, active_view):
        super().__init__()
        self.active_view = active_view

    def run(self):
        view = self.active_view

        lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
        if not lo_view:
            return
        symlist = lo_view.settings().get('symlist')

        shift = 0
        if "part" in [sym["type"] for sym in symlist]:
            shift = 2
        elif "chapter" in [sym["type"] for sym in symlist]:
            shift = 1

        begin_re = r"\\begin(?:\[[^\]]*\])?\{([^\}]*)\}"
        end_re = r"\\end\{([^\}]*)\}"
        sec_re = (
                r'^\\(part\*?|chapter\*?|section\*?|subsection\*?|'
                r'subsubsection\*?|paragraph\*?|frametitle)'
            )
        begins = view.find_all(begin_re, sublime.IGNORECASE)
        ends = view.find_all(end_re, sublime.IGNORECASE)
        secs = view.find_all(sec_re, sublime.IGNORECASE)
        
        for i in range(len(symlist)):
            sym = symlist[i]
            if sym["type"] != "label" or sym["is_equation"]:
                pass
            rgn = sym["region"]
            env_regions = _find_env_regions(view, rgn[0], begins, ends, secs)
            if len(env_regions) == 0 or view.substr(env_regions[0]) == "document":
                env_type = "↪ Ref."
            else:
                env_type = view.substr(env_regions[0])
                env_type = env_type.title()
            symlist[i]["env_type"] = env_type
            symlist[i]["fancy_content"] = new_lo_line(sym["truesym"],
                                             sym["ref"], sym["type"], 
                                             sym["is_equation"],
                                             env_type=env_type,
                                             show_ref_nb=True,
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
    sym_list = lo_view.settings().get('symlist')
    unfiltered_st_symlist = get_st_symbols(active_view)

    for item in sym_list:
        first=None
        key = item["content"]
        for i, (x, y) in enumerate(unfiltered_st_symlist):
            if re.sub(r'\n', ' ', y) == key:
                first = unfiltered_st_symlist.pop(i)
                break      

        if first:
            region = first[0]
            item["region"] = (region.a, region.b)

    lo_view.settings().set('symlist', sym_list)
    return 

# --------------------------

def light_refresh(lo_view, active_view, outline_type):
    '''
    Refresh the regions, add new/remove old entries
    '''
    symlist = lo_view.settings().get('symlist')
    unfiltered_st_symlist = get_st_symbols(active_view)

    shift = 0
    if "part" in [sym["type"] for sym in symlist]:
        shift = 2
    elif "chapter" in [sym["type"] for sym in symlist]:
        shift = 1

    new_symlist = []
    for sym in unfiltered_st_symlist:
        key = re.sub(r'\n', ' ', sym[1])
        item = {}
        key_unfound = True
        for i in range(len(symlist)):
            if key == symlist[i]["content"]:
                item=symlist.pop(i)
                key_unfound = False
                break

        if key_unfound:
            rgn, sym, type, true_sym = extract_from_sym(sym)
            fancy_content = new_lo_line(true_sym, None, type, is_equation=False, 
                                    show_ref_nb=False, shift=shift)
            item = {"region": (rgn.a, rgn.b),
             "type": type,
             "content": sym,
             "truesym": true_sym,
             "is_equation": None,
             "fancy_content": fancy_content,
             "ref": "",
             "env_type": ""}

        new_symlist.append(item)
        
    lo_view.settings().set('symlist', new_symlist)
    return new_symlist



# --------------------------

def goto_region(active_view, region_position):
    if active_view and region_position:
        r = Region(region_position[0], region_position[1])
        active_view.show_at_center(r)
        active_view.sel().clear()
        active_view.sel().add(r)
        active_view.window().focus_view(active_view)


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
        right_cols = [1 - width , 1.0]
        cols = left_cols + right_cols
        new_cell = [x_max, 0, x_max+1, y_max]
        cells.append(new_cell)
        new_layout = {"cols": cols, "rows": rows, "cells": cells}
        window.set_layout(new_layout)
        
    elif side == "left":
        right_cols = [width + c * (1-width) for c in cols if c > 0.0]
        left_cols = [0.0, width ]
        cols = left_cols + right_cols
        cells = [ [c[0]+1, c[1], c[2]+1, c[3]] for c in cells]
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
                + [c for c in cols if c > 1 - width ]
    elif sym_side == "left":
        new_cols = [c for c in cols if c < width ] \
                + [(c - width) / (1-width) for c in cols if c >  width ]
    else:
        return None

    return {"cols": new_cols, "rows": rows, "cells": new_cells}

# --------------------------

def calc_width(view):
    ''' Return float width, which must be 0.0 < width < 1.0'''
    width = view.settings().get('outline_width', 0.3)
    if isinstance(width, float) and width > 0 and width <1:
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

def get_st_symbols(view):
    '''
    Ask ST for the symbols list and apply a first filter according 
    to the chosen outline type
    '''
    unfiltered_st_symlist = [
        (v.region, v.name) for v in view.symbol_regions()
        if v.kind[1] == 'f' or v.kind[1] == 'l'
    ]
    return unfiltered_st_symlist

# --------------------------

def get_aux_file_data(path):
    '''
    Given a .tex file, gather information from the .aux file
    and store it in aux.data settings
    '''
    if path:
        aux_file = os.path.splitext(path)[0] + ".aux"
        if os.path.exists(aux_file):
            all_data = parse_aux_file(aux_file)
            return all_data
    else:
        return None
           
# --------------------------

def extract_from_sym(item):
    rgn = item[0]
    sym = re.sub(r'\n', ' ', item[1])

    # Get the ST symbol entry type and content
    pattern = (
        r'^(Part\*?|Chapter\*?|Section\*?|Subsection\*?|'
        r'Subsubsection\*?|Paragraph\*?|Frametitle): (.+)'
    )
    match = re.match(pattern, sym)
    if match:
        type = match.group(1).lower()
        true_sym = match.group(2)
    else:
       type = "label"
       true_sym = sym

    return rgn, sym, type, true_sym

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
    s = re.sub(r'\$[^\$]*?\$', '', s)
    s = re.sub(r'\\nonbreakingspace\s+', '~', s)
    s = re.sub(r'\\label\{[^\}]*\}\s*', '', s)
    s = re.sub(r'\\[a-z]+', '', s)
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    return unicodedata.normalize("NFC", s)

