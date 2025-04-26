#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
from sublime import Region, set_timeout_async
from sublime_plugin import WindowCommand, TextCommand, EventListener
from .lo_functions import * 
import re
import os

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
        lo_view, lo_group = get_sidebar_view_and_group(self.window)

        if lo_view:
            lo_side = lo_view.settings().get('side')
            lo_new_layout = reduce_layout(self.window, lo_view, lo_group, lo_side)
            self.window.focus_view(lo_view)
            self.window.run_command('close_file')
            self.window.set_layout(lo_new_layout)
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
        if path:
            aux_file = os.path.splitext(path)[0] + ".aux"
            if os.path.exists(aux_file):
                print("---------- Yeah, found it")
            else:
                print("---------- Nope")
        self.view.sel().clear()

# ----------------------------------------------------

class LatexOutlineSyncEventHandler(EventListener):

# ------- Synchronizes the highlight in the outline depending on the cursor's place
#         in the LaTeX file

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
        sublime.set_timeout_async(delayed_sync_lo_view,1000)

# ----------------------------------------------------

class LatexOutlineEventHandler(EventListener):

# ------- Reset the outline when the user focuses on another LaTeX 

    def on_activated(self, view):
        if not get_sidebar_status(view.window()):
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        # Avoid error message when console opens, as console has group index -1
        if view.window().get_view_index(view)[0] == -1:
            return

        lo_view, lo_group = get_sidebar_view_and_group(view.window())

        if lo_view != None:
            if view.file_name() != None and lo_view.settings().get('current_file') == view.file_name():
                return
            else:
                lo_view.settings().set('current_file', view.file_name())
                refresh_lo_view(lo_view, view.file_name(), view)

# ------- Reset the outline when the LaTeX file is saved

    def on_pre_save(self, view):
        if not get_sidebar_status(view.window()):
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        if view.file_name() == None:
            return

        lo_view, lo_group = get_sidebar_view_and_group(view.window())

        if lo_view != None:
            # Note here is the only place that differs from on_activate_view
            if lo_view.settings().get('current_file') != view.file_name():
                lo_view.settings().set('current_file', view.file_name())

        refresh_lo_view(lo_view, view.file_name(), view)
        # symlist = lo_view.settings().get('symlist')
        delayed_sync_lo_view()

# ------- Go to the corresponding place in the LaTeX file when the outline is clicked on

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

# ------- Arranges the layout when one closes the outline manually

    def on_pre_close(self, view):
        if 'latexoutline' not in view.settings().get('syntax'):
            return
        window = view.window()
        lo_view, lo_group = get_sidebar_view_and_group(window)
        
        if lo_view:
            lo_side = lo_view.settings().get('side')
            lo_new_layout = reduce_layout(window, lo_view, lo_group, lo_side)
            window.settings().set('lo_new_layout', lo_new_layout)

    def on_close(self, view):
        window = sublime.active_window()
        if not window.settings().get('lo_new_layout'):
            return
        window.set_layout(window.settings().get('lo_new_layout'))
        window.settings().erase('lo_new_layout')

# --------------

    def on_post_window_command(self, window, command_name, args):
        if not window.active_view() or 'LaTeX.sublime-syntax' not in window.active_view().settings().get('syntax'):
            return
        if command_name != "show_panel":
            return
        if not args["panel"] or args["panel"] != "output.latextools":
            return
        print("youpi")

