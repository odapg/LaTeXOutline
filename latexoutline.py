#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sublime
import sublime_plugin
from sublime import Region, set_timeout_async
from sublime_plugin import WindowCommand, EventListener
from .lo_functions import * 
import re
import os

# ----------------------------------------------------------------------------#
#                                                                             #
#                                MAIN COMMANDS                                #
#                                                                             #
# ----------------------------------------------------------------------------#

# ----------------------------------------------------
# Main command: toggle the layout

class LatexOutlineCommand(WindowCommand):

    def is_visible(self):
        view = self.window.active_view()
        return view and view.match_selector(0, "text.tex.latex")

    def run(self, side="right", outline_type="toc", close_on_repeated_use=True):

        # If the outline view already exists:
        # close the panel and possibly replace it
        if get_sidebar_status(self.window):
            lo_view, lo_group = get_sidebar_view_and_group(self.window)

            current_type = lo_view.settings().get('current_outline_type')
            current_side = lo_view.settings().get('side')

            if current_side == side and current_type == outline_type and not close_on_repeated_use:
                return

            current_symlist = lo_view.settings().get('symlist')
            path = lo_view.settings().get('current_file')

            if side != current_side:
                self.window.run_command('latex_outline_close_sidebar')
                if outline_type == "both":
                    new_outline_type = current_type
                else:
                    new_outline_type = outline_type
                
                show_outline(self.window, side=side, outline_type=new_outline_type, path=path)
                lo_view, lo_group = get_sidebar_view_and_group(self.window)
                lo_view.settings().set('symlist', current_symlist)
                lo_view.settings().set('active_view', self.window.active_view().id())
                fill_sidebar(lo_view, current_symlist, new_outline_type)

            else:
                if outline_type != current_type and outline_type != "both":
                    new_outline_type = outline_type
                elif outline_type == "both" and current_type == "toc":
                    new_outline_type = "full"
                elif outline_type == "both" and current_type == "full" and not close_on_repeated_use:
                    new_outline_type = "toc"
                else:
                    self.window.run_command('latex_outline_close_sidebar')
                    new_outline_type = None
                    
                if new_outline_type:
                    fill_sidebar(lo_view, current_symlist, new_outline_type)
                    lo_view.settings().set('current_outline_type', new_outline_type)
            
        # Open it otherwise
        else:
            if outline_type == "full":
                show_outline(self.window, side=side, outline_type="full")
            else:
                show_outline(self.window, side=side, outline_type="toc")


# ----------------------------------------------------
# Close the outline view and adjust the layout

class LatexOutlineCloseSidebarCommand(WindowCommand):

    def is_visible(self):
        return get_sidebar_status(self.window)

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
# Command to refresh the contents of the outline view

class LatexOutlineRefreshCommand(WindowCommand):

    def is_visible(self):
        return get_sidebar_status(self.window)

    def run(self):
        lo_view, lo_group = get_sidebar_view_and_group(self.window)
        if lo_view:
            outline_type = lo_view.settings().get('current_outline_type')
            active_view_id = lo_view.settings().get('active_view')
            possible_views = [v for v in self.window.views() if v.id() == active_view_id]
            active_view = None if not possible_views else possible_views[0]
            path = lo_view.settings().get('current_file')
        if outline_type and active_view and path:
            refresh_lo_view(lo_view, path, active_view, outline_type)


# ----------------------------------------------------#
#                   Sync event handler                #
# ----------------------------------------------------#

class LatexOutlineSyncEventHandler(EventListener):

# ------- 
# Synchronizes the highlight in the outline 
# depending on the cursor's place in the LaTeX file

    def on_selection_modified(self, view):
        if view.sheet().is_transient():
            return
        if view.window() == None:
            return
        if view.window().get_view_index(view)[0] == -1:
            return
        if 'LaTeX.sublime-syntax' not in view.window().active_view().settings().get('syntax'):
            return
        # Debouncer
        if view.settings().get('sync_in_progress'):
            return
        if not get_sidebar_status(view.window()):
            return

        view.settings().set('sync_in_progress', True)
        sublime.set_timeout_async(sync_lo_view, 1000)


# ----------------------------------------------------#
#                   Main event handler                #
# ----------------------------------------------------#

class LatexOutlineEventHandler(EventListener):

# ------- 
# Reset the outline when the user opens LO or focuses on another LaTeX document

    def on_activated(self, view):
        if not view.match_selector(0, "text.tex.latex"):
            return 
        if not get_sidebar_status(view.window()):
            return

        lo_view, lo_group = get_sidebar_view_and_group(view.window())

        if lo_view is not None:
            if (view.file_name() is not None and 
                    lo_view.settings().get('current_file') == view.file_name()):
                return
            else:
                lo_view.settings().set('current_file', view.file_name())
                outline_type = lo_view.settings().get('current_outline_type')
                refresh_lo_view(lo_view, view.file_name(), view, outline_type)

# ------- 
# Partially refresh the outline when the LaTeX file is saved

    def on_pre_save(self, view):
        if not get_sidebar_status(view.window()):
            return
        if not view.match_selector(0, "text.tex.latex"):
            return 
        if view.file_name() == None:
            return


        lo_view, lo_group = get_sidebar_view_and_group(view.window())

        if lo_view != None:
            if lo_view.settings().get('current_file') != view.file_name():
                lo_view.settings().set('current_file', view.file_name())

        outline_type = lo_view.settings().get('current_outline_type')
        sym_list = light_refresh(lo_view, view, outline_type)
        fill_sidebar(lo_view, sym_list, outline_type)
        sync_lo_view()

# ------- 
# When the user clicks the outline,
# go to the corresponding place in the LaTeX file
# or copy the label when asked

    def on_selection_modified(self, view):
        if 'latexoutline' not in view.settings().get('syntax'):
            return
        if view.window().get_view_index(view)[0] == -1:
            return
        window = sublime.active_window()
        lo_view = view

        # Get the LaTeX view from the settings
        active_view_id = lo_view.settings().get('active_view')
        possible_views = [v for v in window.views() if v.id() == active_view_id]
        active_view = None if not possible_views else possible_views[0]

        if active_view is not None:
            # Position and nature of the selected item in the outline
            if len(lo_view.sel()) == 0:
                return None
            lo_view_sel = lo_view.sel()[0]
            (row, col) = lo_view.rowcol(lo_view.sel()[0].begin())
            sel_scope = lo_view.scope_name(lo_view.sel()[0].begin())
            
            # Refresh the regions (only) in the symlist
            outline_type = lo_view.settings().get('current_outline_type')
            refresh_regions(lo_view, active_view)
            full_symlist = lo_view.settings().get('symlist')
            if outline_type == "toc":
                symlist = [sym for sym in full_symlist if sym["type"] != "label"]
            else:
                symlist = full_symlist

            # Get the region corresponding to the selected item
            if not symlist or row is None:
                return None
            region = symlist[row]["region"]
            
            # If the copy symbol ❐ was pressed
            if 'copy' in sel_scope:
                label = symlist[row]["content"]
                sublime.set_clipboard(label)
                sublime.active_window().status_message(
                f" ✓ Copied reference '{label}' to the clipboard")
                lo_view.sel().clear()
                sublime.active_window().focus_view(active_view)
                return

            # If the takealook symbol ◎ was pressed
            if 'takealook' in sel_scope:
                active_view.add_regions(
                    "takealook", 
                    active_view.lines(Region(region[0],region[1])),
                    icon='Packages/LaTeXOutline/images/chevron.png',
                    scope='region.bluish',
                    flags=1024,
                )
                active_view.show_at_center(region[0])
                sublime.active_window().focus_view(active_view)
                sublime.set_timeout_async(lambda: active_view.erase_regions("takealook"), 5000)
                return

            # otherwise, go to the corresponding region or copy the section label
            # if the bullet is pressed
            if 'bullet' in sel_scope:
                copy_label(active_view, region)
            else:
                goto_region(active_view, region)          

# ------- 
# Arranges the layout when one closes the outline manually

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
# Completely refresh the view after .tex has been built (with LaTeXTools)

    def on_post_window_command(self, window, command_name, args):
        if not get_sidebar_status(window):
            return
        if not window.active_view() or not window.active_view().match_selector(0, "text.tex.latex"):
            return
        if command_name != "show_panel":
            return
        if not args["panel"] or args["panel"] != "output.latextools":
            return
        lo_view, lo_group = get_sidebar_view_and_group(window)
        outline_type = lo_view.settings().get('current_outline_type')
        refresh_lo_view(lo_view, window.active_view().file_name(), window.active_view(), outline_type)

