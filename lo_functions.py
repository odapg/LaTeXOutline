#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sublime
import sublime_plugin
import re
from sublime import Region


# -------------------------- Characters --------------------------
# Changes here should also be reported in latexoutline.sublime-syntax
# Suggestions: ▪ ⌑ ⦾ ⁌ ∙ ◦ ⦿ ■ 𑗕 ◉ • ⸱ ‣ ▫ ⊙ ⊛ ⏺
part_char = '■'
chap_char = '𑗕'
sec_char = '⏺'
ssec_char = '⊛'
sssec_char = '‣'
par_char = '⸱'
ftitle_char = '▫'
# ----------------------------------------------------------------

# --------------------------------------------------------------------------------------#
#                                                                                       #
#                      Functions directly associated with commands                      #
#                                                                                       #
# --------------------------------------------------------------------------------------#

def show(window, side="right"):
    """
    Toggles the outline view. Filling it will be taken care of by the EventHandler.
    """

    # Closes the outline view if it already exists
    if get_sidebar_status(window):
        sym_view, sym_group = get_sidebar_view_and_group(window)
        previous_side = sym_view.settings().get('side')
        window.run_command('latex_outline_close_sidebar')
        if side != previous_side:
            show(window, side=side)
        return

    # Creates the outline view otherwise
    prev_focus = window.active_view()
    new_view = create_outline_view(window)
    view_name = "Table of contents"
    name = u"𝌆 {0}".format(view_name)
    new_view.set_name(name)
    new_view.settings().set('side', side)

    arrange_layout(new_view, side)
    
    nb_groups = window.num_groups()
    window.set_view_index(new_view, nb_groups-1, 0)

    window.focus_view(prev_focus)

# --------------------------

def refresh_sym_view(sym_view, path, view):

    # Get the symbol list
    # unfiltered_st_sym_list = view.get_symbols()
    unfiltered_st_sym_list = [(v.region,v.name) for v in view.symbol_regions() if v.kind[1]=='f']
    st_sym_list = filter_symlist(unfiltered_st_sym_list)

    l = []
    k = []
    active_view_id = view.id()

    for symbol in st_sym_list:
        rng, sym = symbol
        l.append(sym)
        k.append((rng.a, rng.b))
    if sym_view != None:
        sym_view.settings().erase('symlist')
        sym_view.settings().erase('symkeys')
        sym_view.run_command(
            'latex_outline_refresh', 
            {'symlist': l, 'symkeys': k, 'path': path, 'active_view': active_view_id})

# --------------------------

def delayed_sync_symview():
    view = sublime.active_window().active_view()
    sym_view, sym_group = get_sidebar_view_and_group(sublime.active_window())
    if not sym_view.settings().get('outline_sync'):
        return
    if sym_view != None:
        unfiltered_st_sym_list = [(v.region,v.name) for v in view.symbol_regions() if v.kind[1]=='f']
        st_symlist = filter_symlist(unfiltered_st_sym_list)
        sync_symview(sym_view, st_symlist)
    view.settings().set('sync_in_progress', False)


# --------------------------

def find_selected_section():
    window = sublime.active_window()
    sym_view, sym_group = get_sidebar_view_and_group(window)

    if len(sym_view.sel()) == 0:
        return None
    
    active_view_id = sym_view.settings().get('active_view')
    possible_views = [v for v in window.views() if v.id() == active_view_id]
    active_view = None if not possible_views else possible_views[0]

    if active_view != None:
        (row, col) = sym_view.rowcol(sym_view.sel()[0].begin())
        sel_scope = sym_view.scope_name(sym_view.sel()[0].begin())
        
        refresh_sym_view(sym_view, active_view.file_name(), active_view)
        symkeys = sym_view.settings().get('symkeys')
        symlist = sym_view.settings().get('symlist')
        if not symkeys or not symlist or row == None:
            return None
        region_position = symkeys[row]
        label_copy = False
        if 'bullet' in sel_scope:
            label_copy = True
        return (active_view, region_position, label_copy)
    else:
        return None

# --------------------------

def goto_region(active_view, region_position):
    if active_view and region_position:
        r = Region(region_position[0], region_position[1])
        active_view.show_at_center(r)
        active_view.sel().clear()
        active_view.sel().add(r)
        active_view.window().focus_view(active_view)
        delayed_sync_symview()    

# --------------------------

def copy_label(active_view, region_position):
    if active_view and region_position:
        text_from_region = active_view.substr(sublime.Region(region_position[1],active_view.size()))

        label_match = re.search(r'\\label\{([^}]*)\}', text_from_region)
        command_match = re.search(r'\\\w*\{', text_from_region)
        if label_match and (not command_match or label_match.start() <= command_match.start()):
            label = label_match.group(1)
            sublime.set_clipboard(label)
            sublime.active_window().status_message(f" ✓ Copied reference '{label}' to the clipboard")
        else:
            section = active_view.substr(sublime.Region(region_position[0],region_position[1]))
            sublime.active_window().status_message(f" ⨉ No \\label found for '{section}'")


# --------------------------------------------------------------------------------------#
#                                                                                       #
#                                Intermediate functions                                 #
#                                                                                       #
# --------------------------------------------------------------------------------------#


def sync_symview(sym_view, st_symlist):
    '''
    sync the outline view with current file location
    '''
    view = sublime.active_window().active_view()
    point = view.sel()[0].end()
    range_lows = [view.line(range.a).begin() for range, symbol in st_symlist]
    range_sorted = [0] + range_lows[1:len(range_lows)] + [view.size()]
    sym_line = binary_search(range_sorted, point) - 1

    if (sym_view is not None):
        sym_point_start = sym_view.text_point_utf8(sym_line, 0)
        sym_view.show_at_center(sym_point_start, animate=True)
        sym_view.sel().clear()
        sym_view.sel().add(sym_point_start)
        # For some reason, the following makes the outline highlighting more reliable.
        sym_view.set_syntax_file('Packages/LaTeXOutline/latexoutline.sublime-syntax')

# --------------------------

def create_outline_view(window):
    active_view = window.active_view()
    view = window.new_file()
    view.set_syntax_file('Packages/LaTeXOutline/latexoutline.sublime-syntax')
    view.set_scratch(True)
    
    if view.settings().get('outline_inherit_color_scheme'):
        view.settings().set('color_scheme', active_view.settings().get('color_scheme'))
    else:
        view.settings().add_on_change('color_scheme', lambda: set_proper_scheme(view))
        
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
    views = window.views()
    sym_view = None
    sym_group = None
    for v in views:
        if 'latexoutline.sublime-syntax' in v.settings().get('syntax'):
            sym_view = v
            sym_group, i = window.get_view_index(sym_view)
    return (sym_view, sym_group)

# --------------------------

def get_sidebar_status(window):
    sidebar_on = False
    for v in window.views():
        if 'latexoutline.sublime-syntax' in v.settings().get('syntax'):
            sidebar_on = True

    return sidebar_on

# --------------------------

def filter_symlist(unfiltered_symlist):
    '''
    Filters the symlist to only show LaTeX sections in indented manner
    '''
    pattern = r'(?:Part|Chapter|Section|Subsection|Subsubsection|Paragraph|Frametitle):.*'
    filtered_symlist = [x for x in unfiltered_symlist if re.match(pattern, x[1])]
    part_symlist = [x for x in unfiltered_symlist if x[1].startswith("Part:")]
    chapter_symlist = [x for x in unfiltered_symlist if x[1].startswith("Chapter:")]
    
    shift =0
    if len(part_symlist) > 0:
        shift=2
    elif len(chapter_symlist) > 0:
        shift=1

    rs = ' ' * shift + sec_char + ' '
    rss = ' ' * (shift + 1) + ssec_char + ' '
    rsss = ' ' * (shift + 2) + sssec_char + ' '
    rpar = ' ' * (shift + 3) + par_char + ' '
    rpt = part_char + ' '
    rch = ' ' + chap_char + ' ' if shift==2 else chap_char + ' '
    rftt= ftitle_char + ' '

    cleaned_symlist = [
        (i, j.replace('\n','') \
            .replace('Part: ', rpt) \
            .replace('Chapter: ', rch) \
            .replace('Section: ', rs) \
            .replace('Subsection: ', rss) \
            .replace('Subsubsection: ', rsss) \
            .replace('Paragraph: ', rpar) \
            .replace('Frametitle: ', rftt) ) for i,j in filtered_symlist
    ]
    return cleaned_symlist


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
