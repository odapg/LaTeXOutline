#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
from sublime import Region, set_timeout_async
from sublime_plugin import WindowCommand, TextCommand, EventListener
from .lo_functions import * 
import re

# --------------------------------------------------------------------------------------#
#                                                                                       #
#                                     MAIN COMMANDS                                     #
#                                                                                       #
# --------------------------------------------------------------------------------------#

class LatexOutlineCommand(WindowCommand):
    def run(self, side="right"):
        show(self.window, side=side)

# ----------------------------------------------------

class LatexOutlineCloseSidebarCommand(WindowCommand):
    def run(self):
        active_view = self.window.active_view()
        sym_view, sym_group = get_sidebar_view_and_group(self.window)
        if sym_view:
            sym_side = sym_view.settings().get('side')
            current_layout = self.window.layout()
            rows = current_layout["rows"]
            cols = current_layout["cols"]
            cells = current_layout["cells"]
            x_min, y_min, x_max, y_max = cells[sym_group]
            width = cols[x_min +1] - cols[x_min]
            new_cells = [c for c in cells if c[2] <= x_min ] \
                    + [ [c[0]-1, c[1], c[2]-1, c[3]] for c in cells if c[0] >= x_max] 
            
            if sym_side == "right":
                new_cols = [c / (1-width) for c in cols if c < 1 - width ] \
                        + [c for c in cols if c > 1 - width ]
            elif sym_side == "left":
                new_cols = [c for c in cols if c < width ] \
                        + [(c - width) / (1-width) for c in cols if c >  width ]
            else:
                return

            self.window.focus_view(sym_view)
            self.window.run_command('close_file')

            self.window.set_layout({"cols": new_cols, "rows": rows, "cells": new_cells})
            self.window.focus_view(active_view)

# ----------------------------------------------------

class LatexOutlineRefreshCommand(TextCommand):
    def run(self, edit, symlist=None, symkeys=None, path=None, active_view=None):
        self.view.erase(edit, Region(0, self.view.size()))
        self.view.insert(edit, 0, "\n".join(symlist))
        # self.view.add_regions(
        #     "lines", 
        #     self.view.lines(Region(0, self.view.size())),
        #     icon='Packages/LaTeXOutline/chevron.png',
        #     scope='region.bluish"',
        #     flags=128
        # )
        self.view.settings().set('symlist', symlist)
        self.view.settings().set('symkeys', symkeys)
        if active_view:
            self.view.settings().set('active_view', active_view)
        self.view.settings().set('current_file', path)
        self.view.sel().clear()

# ----------------------------------------------------

class LatexOutlineSyncEventHandler(EventListener):

    def on_selection_modified(self, view):
        if view.sheet().is_transient():
            return
        if view.window() == None:
            return
        if view.window().get_view_index(view)[0] == -1:
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        if view.settings().get('sync_in_progress'):
            return
        if not get_sidebar_status(view.window()):
            return
        
        view.settings().set('sync_in_progress', True)
        sublime.set_timeout_async(delayed_sync_symview,1000)

# ----------------------------------------------------

class LatexOutlineEventHandler(EventListener):

    def on_activated(self, view):
        if not get_sidebar_status(view.window()):
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        # Avoid error message when console opens, as console has group index -1
        if view.window().get_view_index(view)[0] == -1:
            return

        sym_view, sym_group = get_sidebar_view_and_group(view.window())

        if sym_view != None:
            if sym_view.settings().get('current_file') == view.file_name() and view.file_name() != None:
                return
            else:
                sym_view.settings().set('current_file', view.file_name())
            
        refresh_sym_view(sym_view, view.file_name(), view)

# --------------

    def on_pre_save(self, view):
        if not get_sidebar_status(view.window()):
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        if view.file_name() == None:
            return

        sym_view, sym_group = get_sidebar_view_and_group(view.window())

        if sym_view != None:
            # Note here is the only place that differs from on_activate_view
            if sym_view.settings().get('current_file') != view.file_name():
                sym_view.settings().set('current_file', view.file_name())

        refresh_sym_view(sym_view, view.file_name(), view)
        symlist = sym_view.settings().get('symlist')
        delayed_sync_symview()

# --------------

    def on_selection_modified(self, view):
        if 'latexoutline' not in view.settings().get('syntax'):
            return
        if view.window().get_view_index(view)[0] == -1:
            return

        if found_selection := find_selected_section():
            active_view, region_position, label_copy = found_selection
            if label_copy:
                copy_label(active_view, region_position)
            else:
                goto_region(active_view, region_position)

