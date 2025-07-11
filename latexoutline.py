#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sublime
import time
from sublime_plugin import TextCommand, WindowCommand, EventListener
from .lo_functions import *

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

    def run(self, side="right", outline_cycle=["toc", "close"]):

        # If the outline view already exists
        if get_sidebar_status(self.window):
            lo_view, lo_group = get_sidebar_view_and_group(self.window)

            current_type = lo_view.settings().get('current_outline_type')
            current_side = lo_view.settings().get('side')
            
            outline_type = next_in_cycle(current_type, outline_cycle)

            current_symlist = lo_view.settings().get('symlist')
            path = lo_view.settings().get('current_file')

            if side != current_side:
                self.window.run_command('latex_outline_close_sidebar')
                new_outline_type = outline_cycle[0]
                
                show_outline(self.window, side=side, 
                             outline_type=new_outline_type, path=path)
                lo_view, lo_group = get_sidebar_view_and_group(self.window)
                lo_view.settings().set('symlist', current_symlist)
                lo_view.settings().set('active_view', self.window.active_view().id())
                fill_sidebar(lo_view, current_symlist, new_outline_type)

            else:
                if outline_type == current_type:
                    return
                elif outline_type != "close": 
                    new_outline_type = outline_type
                else:
                    self.window.run_command('latex_outline_close_sidebar')
                    new_outline_type = None

                if new_outline_type:
                    fill_sidebar(lo_view, current_symlist, new_outline_type)
                    lo_view.settings().set('current_outline_type', new_outline_type)
            
        # Open it otherwise
        else:
            show_outline(self.window, side=side, outline_type=outline_cycle[0])
            


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
            self.window.destroy_output_panel('lo_takealook')


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
            possible_views = [v for v in self.window.views() 
                              if v.id() == active_view_id]
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
        if not view.match_selector(0, "text.tex.latex"):
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
            if (view.file_name() is not None 
                    and lo_view.settings().get('current_file') == view.file_name()):
                return
            tex_files = lo_view.settings().get('file_list')
            if (view.file_name() is not None and tex_files is not None
                    and view.file_name() in tex_files):
                lo_view.settings().set('current_file', view.file_name())
                lo_view.settings().set('active_view', view.id())
                return
            else:
                lo_view.settings().set('current_file', view.file_name())
                lo_view.settings().set('active_view', view.id())
                outline_type = lo_view.settings().get('current_outline_type')
                refresh_lo_view(lo_view, view.file_name(), view, outline_type)

# ------- 
# Partially refresh the outline when the LaTeX file is saved

    def on_post_save(self, view):
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
# When the user clicks the outline, go to the corresponding place in the LaTeX file
# or copy the label when asked
                
    def on_selection_modified(self, view):
        view_syntax = view.settings().get('syntax')
        if not view_syntax or 'latexoutline' not in view_syntax:
            return
        if view.window().get_view_index(view)[0] == -1:
            return
        just_clicked = view.settings().get('just_clicked')
        if just_clicked is not None and just_clicked:
            return
        window = sublime.active_window()
        lo_view = view

        current_view_id = lo_view.settings().get('active_view')
        possible_views = [v for v in window.views() if v.id() == current_view_id]
        current_view = None if not possible_views else possible_views[0]

        # Position and nature of the selected item in the outline
        if len(lo_view.sel()) == 0 or current_view is None:
            return None
        lo_view_sel = lo_view.sel()[0]
        (row, col) = lo_view.rowcol(lo_view.sel()[0].begin())
        sel_scope = lo_view.scope_name(lo_view.sel()[0].begin())
        
        # Refresh the regions (only) in the symlist
        refresh_regions(lo_view, current_view)
        outline_type = lo_view.settings().get('current_outline_type')
        full_symlist = lo_view.settings().get('symlist')
        alt_clicked = lo_view.settings().get('alt_clicked')
        if alt_clicked is None:
            alt_clicked = False
        lo_view.settings().set('alt_clicked', False)

        type_nb = level_filter(outline_type)
        symlist = [sym for sym in full_symlist if sym["level"] <= type_nb]

        is_title = any([s for s in symlist if s["type"] == "title"])
        if is_title and row != 0:
            row -= 1

        # Get the region corresponding to the selected item
        if not symlist or row is None:
            return None
        file = symlist[row]["file"]
        region = symlist[row]["region"]
        start = region[0]
        
        target_view = None
        for v in sublime.active_window().views():
            if v.file_name() == file:
                target_view = v
                break

        # If the copy symbol ❐ was pressed
        if 'copy' in sel_scope:
            label = symlist[row]["content"]
            if alt_clicked:
                is_equation = symlist[row]["is_equation"]
                if is_equation:
                    copied_label = "\\eqref{" + label + "}"
                else:
                    copied_label = "\\ref{" + label + "}"
            else:
                copied_label = label
            sublime.set_clipboard(copied_label)
            sublime.active_window().status_message(
                f" ✓ Copied reference '{copied_label}' to the clipboard")
            # lo_view.sel().clear()
            sublime.active_window().focus_view(current_view)
            return

        # If the takealook symbol ⌖ was pressed
        if 'takealook' in sel_scope:
            takealook(file, region, current_view)
            return

        # otherwise, go to the corresponding region or copy the section label
        # if the bullet is pressed
        if 'bullet' in sel_scope:
            copy_label(target_view, region)
        else:
            if not target_view:
                current_view.window().focus_view(current_view)
                target_view = sublime.active_window().open_file(file)
                sublime.set_timeout(lambda: navigate_to(target_view, start, lo_view), 500)
            else:
                navigate_to(target_view, start, lo_view)          

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
# Completely refresh the view after .tex has been built (with build command)

    def on_post_window_command(self, window, command_name, args):
        if (not window.active_view() 
                or not window.active_view().match_selector(0, "text.tex.latex")):
            return
        if not get_sidebar_status(window):
            return
        if command_name != "build":
            return
        path = window.active_view().file_name()
        aux_file = os.path.splitext(path)[0] + ".aux"
        refresh_with_new_aux(aux_file, window, i=0, step=0)

# -------------------

class AltClickedCommand(TextCommand):
    def run_(self, edit, args):
        view_syntax = self.view.settings().get('syntax')
        if not view_syntax or 'latexoutline' not in view_syntax:
            return
        self.view.settings().set('alt_clicked', True)
        self.view.run_command("drag_select", {'event': args['event']})
        self.view.settings().set('just_clicked', True)
        sublime.set_timeout_async(lambda: self.view.settings().set('just_clicked', False), 200)
