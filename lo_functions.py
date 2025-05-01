#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sublime
import sublime_plugin
import re
from sublime import Region


# -------------------------- Characters --------------------------
# Changes here should also be reported in latexoutline.sublime-syntax
# Suggestions: ▪ ⌑ ⦾ ⁌ ∙ ◦ ⦿ ■ 𑗕 ◉ • ⸱ ‣ ▫ ⊙ ⊛ ⏺ ⏿
lo_chars = {
    'part': '■',
    'chapter': '𑗕',
    'section': '⏺',
    'subsection': '⊛',
    'subsubsection': '‣',
    'paragraph': '⸱',
    'frametitle': '▫',
    'label': '›',
    'copy': '❐',}

# ----------------------------------------------------------------

# ----------------------------------------------------------------------------#
#                                                                             #
#                 Functions directly associated with commands                 #
#                                                                             #
# ----------------------------------------------------------------------------#


def show_outline(window, side="right", outline_type="toc"):
    """
    Toggle the outline view. 
    Filling it will be taken care of by LatexOutlineEventHandler which in
    particular calls the LatexOutlineRefresh command.
    """

    # Closes the outline view if it already exists
    if get_sidebar_status(window):
        lo_view, lo_group = get_sidebar_view_and_group(window)
        previous_side = lo_view.settings().get('side')
        window.run_command('latex_outline_close_sidebar')
        if side != previous_side:
            show_outline(window, side=side)
        return

    # Creates the outline view otherwise
    prev_focus = window.active_view()
    new_view = create_outline_view(window)
    view_name = "Table of contents"
    name = u"𝌆 {0}".format(view_name)
    new_view.set_name(name)
    new_view.settings().set('side', side)
    new_view.settings().set('outline_type', outline_type)

    arrange_layout(new_view, side)
    
    nb_groups = window.num_groups()
    window.set_view_index(new_view, nb_groups-1, 0)

    window.focus_view(prev_focus)

# --------------------------

def refresh_lo_view(lo_view, path, view, outline_type):
    '''Prepare the use of latex_outline_refresh command'''

    # Get the section list
    unfiltered_st_sym_list = get_st_symbols(view, outline_type)
    new_list = filter_and_decorate_symlist(unfiltered_st_sym_list, outline_type)
    active_view_id = view.id()

    if lo_view is not None:
        lo_view.settings().erase('symlist')
        lo_view.run_command('latex_outline_refresh', 
                            {'symlist': new_list,
                             'path': path,
                             'active_view': active_view_id}
                            )

# --------------------------

def sync_lo_view():
    ''' sync the outline view with current file location '''

    lo_view, lo_group = get_sidebar_view_and_group(sublime.active_window())
    if not lo_view or not lo_view.settings().get('outline_sync'):
        return
    if lo_view is not None:
        outline_type = lo_view.settings().get('outline_type')
        view = sublime.active_window().active_view()

        unfiltered_st_sym_list = get_st_symbols(view, outline_type)
        new_list = filter_and_decorate_symlist(unfiltered_st_sym_list, outline_type)
        
        point = view.sel()[0].end()
        range_lows = [view.line(item['region'][0]).begin() for item in new_list]
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

# --------------------------------------------------------------------------#
#                                                                           #
#                          Intermediate functions                           #
#                                                                           #
# --------------------------------------------------------------------------#


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

    outline_settings = sublime.load_settings('latexoutline.sublime-settings')
    if view.settings().get('color_scheme') == outline_settings.get('color_scheme'):
        return
    view.settings().set('color_scheme', outline_settings.get('outline_color_scheme'))

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

def calc_width(view):
    ''' Return float width, which must be 0.0 < width < 1.0 '''
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

def filter_and_decorate_symlist(unfiltered_symlist, outline_type):
    '''
    Filters the symlist to only show sections and labels
    Prepares their presentation in the LO view, put it in the 'symlist' setting
    '''
    if outline_type == "toc":
        pattern = r'(?:Part|Chapter|Section|Subsection|Subsubsection|Paragraph|Frametitle):.*'
        sym_list = [x for x in unfiltered_symlist if re.match(pattern, x[1])]
    else:
        pattern = r'(?:Part|Chapter|Section|Subsection|Subsubsection|Paragraph|Frametitle):.*|[^\\].*'
        sym_list = [x for x in unfiltered_symlist if re.match(pattern, x[1])]
        
    part_list = [x for x in unfiltered_symlist if x[1].startswith("Part:")]
    chapter_list = [x for x in unfiltered_symlist if x[1].startswith("Chapter:")]
    
    shift = 0
    if len(part_list) > 0:
        shift = 2
    elif len(chapter_list) > 0:
        shift = 1

    rpt = lo_chars['part'] + ' '
    rch = ' ' + lo_chars['chapter'] + ' ' if shift==2 else lo_chars['chapter'] + ' '
    rs = ' ' * shift + lo_chars['section'] + ' '
    rss = ' ' * (shift + 1) + lo_chars['subsection'] + ' '
    rsss = ' ' * (shift + 2) + lo_chars['subsubsection'] + ' '
    rpar = ' ' * (shift + 3) + lo_chars['paragraph'] + ' '
    rftt = lo_chars['frametitle'] + ' '
    rlab = '  ' + lo_chars['label']
    rcopy = ' ' + lo_chars['copy'] + ' '

    print(sym_list)

    new_list = []
    for i in sym_list:
        rgn = i[0]
        sym = i[1]
        if sym.startswith('Part: '):
            new_sym = rpt + sym[6:]
            type = "part"
        elif sym.startswith('Chapter: '):
            new_sym = rch + sym[9:]
            type = "chapter"
        elif sym.startswith('Section: '):
            new_sym = rs + sym[9:]
            type = "section"
        elif sym.startswith('Subsection: '):
            new_sym = rss + sym[12:]
            type = "subsection"
        elif sym.startswith('Subsubsection: '):
            new_sym = rsss + sym[15:]
            type = "subsubsection"
        elif sym.startswith('Paragraph: '):
            new_sym = rpar + sym[11:]
            type = "paragraph"
        else:
            new_sym = rlab + sym + rcopy
            type ="label"

        new_list.append(
            {"region": (rgn.a, rgn.b),
             "type": type,
             "content": sym,
             "fancy_content": new_sym}
        )
        
    return new_list

# --------------------------

def get_st_symbols(view, outline_type):
    '''
    Ask ST for the symbol list and apply a first filter according 
    to the outline chose type
    '''
    if outline_type == "toc":
        unfiltered_st_sym_list = [
            (v.region, v.name) for v in view.symbol_regions() if v.kind[1] == 'f'
        ]
    else:
        unfiltered_st_sym_list = [
            (v.region, v.name) for v in view.symbol_regions()
            if v.kind[1] == 'f' or v.kind[1] == 'l'
        ]
    return unfiltered_st_sym_list

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
