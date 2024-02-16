import sublime
from sublime import Region
from sublime_plugin import WindowCommand, TextCommand, EventListener
from .show import show, refresh_sym_view, get_sidebar_views_groups, get_sidebar_status, filter_symlist
import re

ST3 = int(sublime.version()) >= 3000

if ST3:
    from .common import first, set_proper_scheme, calc_width, get_group
else:
    from common import first, set_proper_scheme, calc_width, get_group


class OutlineCommand(WindowCommand):
	def run(self, immediate=False, single_pane=False, project=False, other_group=False, layout=0):
		show(self.window, single_pane=single_pane, other_group=other_group, layout=layout)

class OutlineStartCommand(TextCommand):
	def run(self, edit):
		immediate=True
		single_pane=True
		project=True		
		other_group="right"
		layout=2
		show(self.view.window(), single_pane=single_pane, other_group=other_group, layout=layout)


class OutlineCloseSidebarCommand(WindowCommand):
	def run(self):
		active_view = self.window.active_view()

		for v in self.window.views():
			if u'𝌆' in v.name():
				self.window.focus_view(v)
				self.window.run_command('close_file')

		self.window.set_layout({"cols": [0.0, 1.0], "rows": [0.0, 1.0], "cells": [[0, 0, 1, 1]]})
		self.window.focus_view(active_view)

class OutlineRefreshCommand(TextCommand):
	def run(self, edit, symlist=None, symkeys=None, path=None, to_expand=None, toggle=None, active_view=None):
		self.view.erase(edit, Region(0, self.view.size()))
		self.view.insert(edit, 0, "\n".join(symlist))
		self.view.settings().set('symlist', symlist)
		self.view.settings().set('symkeys', symkeys)
		if active_view:
			self.view.settings().set('active_view', active_view)
		self.view.settings().set('current_file', path)
		self.view.sel().clear()

class OutlineEventHandler(EventListener):
	def on_selection_modified(self, view):
		if 'outline.hidden-tmLanguage' not in view.settings().get('syntax'):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		sym_view = view
		window = view.window()
		sym_group, i = window.get_view_index(sym_view)
			
		if len(sym_view.sel()) == 0:
			return

		(row, col) = sym_view.rowcol(sym_view.sel()[0].begin())

		active_view =None
		active_view_id = sym_view.settings().get('active_view')
		if active_view_id:
			active_view = first(window.views(), lambda v: v.id() == active_view_id)

		#if there is no active view set yet
		if active_view == None:
			for group in range(window.num_groups()):
				if group != sym_group and group != fb_group:
					active_view = window.active_view_in_group(group)

		if active_view != None:
			symkeys = sym_view.settings().get('symkeys')
			if not symkeys:
				return
			region_position = symkeys[row]
			r = Region(region_position[0], region_position[1])
			active_view.show_at_center(r)
			active_view.sel().clear()
			active_view.sel().add(r)
			window.focus_view(active_view)

	def on_activated(self, view):
		if u'𝌆' in view.name():
			return
		# Avoid error message when console opens, as console is also a view, albeit with a group index of -1
		if view.window().get_view_index(view)[0] == -1:
			return

		if not get_sidebar_status(view):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		if sym_view != None:
			if sym_view.settings().get('current_file') == view.file_name() and view.file_name() != None:
				return
			else:
				sym_view.settings().set('current_file', view.file_name())
			
		# get the symbol list
		unfiltered_symlist = view.get_symbols()
		symlist = filter_symlist(unfiltered_symlist)

		refresh_sym_view(sym_view, symlist, view.file_name(), view)

	def on_pre_save(self, view):
		if u'𝌆' in view.name():
			return
		# this is not absolutely necessary, and prevents views that do not have a file reference from displaying 
		# the symbol list
		# but it solves a console error if the console is activiated, as console is also a view....
		if view.file_name() == None:
			return

		if not get_sidebar_status(view):
			return

		sym_view, sym_group, fb_view, fb_group = get_sidebar_views_groups(view)

		if sym_view != None:
			# Note here is the only place that differs from on_activate_view
			if sym_view.settings().get('current_file') != view.file_name():
				sym_view.settings().set('current_file', view.file_name())
			
		# get the symbol list
		unfiltered_symlist = view.get_symbols()
		symlist = filter_symlist(unfiltered_symlist)
		refresh_sym_view(sym_view, symlist, view.file_name(), view)

		# sync the outline view with current file location
		if view.window() is None or not sym_view.settings().get('outline_sync'):
			return
		# get the current cursor location
		point = view.sel()[0].begin()
		# get the current symbol and its line in outline
		range_lows = [view.line(range.a).begin() for range, symbol in symlist]
		range_sorted = [0] + range_lows[1:len(range_lows)] + [view.size()]
		sym_line = binary_search(range_sorted, point) - 1

		if (sym_view is not None):
			sym_point_start = sym_view.text_point(sym_line, 0)
			# center symview at the point
			sym_view.show_at_center(sym_point_start)
			sym_view.sel().clear()
			sym_view.sel().add(sym_view.line(sym_point_start))
			view.window().focus_view(view)
