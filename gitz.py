#!/bin/python3

import os
import sys
import signal
import subprocess
import re
import time

import gi
try:
	gi.require_version('Gtk', '3.0')
except:
	gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio, GLib, Pango

def isGtk(major):
	return major == Gtk.get_major_version()

cwd = os.getcwd()
cwdAbs = os.path.abspath(os.path.expanduser(cwd))

class SearchBar(Gtk.SearchBar):
	def add(self, child):
		if isGtk(3):
			super().add(child)
		elif isGtk(4):
			self.set_child(child)

class ScrolledWindow(Gtk.ScrolledWindow):
	def add(self, child):
		if isGtk(3):
			super().add(child)
		elif isGtk(4):
			self.set_child(child)

class ApplicationWindow(Gtk.ApplicationWindow):
	def add(self, child):
		if isGtk(3):
			super().add(child)
		elif isGtk(4):
			self.set_child(child)

class HPaned(Gtk.Paned):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
	def add1(self, child):
		if isGtk(3):
			super().add1(child)
		elif isGtk(4):
			self.set_start_child(child)
	def add2(self, child):
		if isGtk(3):
			super().add2(child)
		elif isGtk(4):
			self.set_end_child(child)

class VBox(Gtk.Box):
	def __init__(self, *args, **kwargs):
		super().__init__(*args,
			orientation=Gtk.Orientation.VERTICAL,
			homogeneous=False,
			**kwargs
		)
	def pack_start(self, child, expand, fill, padding):
		if isGtk(3):
			super().pack_start(child, expand, fill, padding)
		elif isGtk(4):
			child.set_vexpand(expand)
			# child.set_fill(fill)
			self.append(child)

def GtkTextBuffer_parseTextIter(obj):
	if isinstance(obj, Gtk.TextIter):
		return obj
	elif isinstance(obj, tuple) and len(obj) == 2:
		result, textIter = obj
		if isinstance(textIter, Gtk.TextIter):
			return textIter
	raise NotImplemented()

def GtkTextBuffer_get_iter_at_line(buf, line_number):
	line_iter = buf.get_iter_at_line(line_number)
	return GtkTextBuffer_parseTextIter(line_iter)

def GtkTextBuffer_get_iter_at_line_offset(buf, line_number, char_offset):
	line_iter = buf.get_iter_at_line_offset(line_number, char_offset)
	return GtkTextBuffer_parseTextIter(line_iter)



LOG_PATTERN = re.compile(r'^([ \*\|\\\/]+)((\w{6,}) (\([^)]+\) )?(.+))?$', re.MULTILINE)
OLDLINE_PATTERN = re.compile(r'^\-.*$', re.MULTILINE)
NEWLINE_PATTERN = re.compile(r'^\+.*$', re.MULTILINE)
HUNKHEADER_PATTERN = re.compile(r'^@@.+$', re.MULTILINE)
COMMITHEADER_PATTERN = re.compile(r'^(commit ((.|\n)+?))(\n(---\n)((.|\n)+?))?(\ndiff|$)')
STATFILE_PATTERN = re.compile(r' (.+?)\s+\|\s+(\d+) (\+*)(\-*)')
DIFF_PATTERN = re.compile(r'\n(diff ((.|\n)+?))\n(\-\-\-|\+\+\+)')

#---
def log(*args):
	# print(*args) # Comment to hide debug log
	return

def applyTagForGroup(buf, match, group, tag, searchOffset=0):
	start = searchOffset + match.start(group)
	end = searchOffset + match.end(group)
	# print(match, start, end)
	startIter = buf.get_iter_at_offset(start)
	endIter = buf.get_iter_at_offset(end)
	buf.apply_tag(tag, startIter, endIter)

def rgba(hexstr):
	c = Gdk.RGBA()
	c.parse(hexstr)
	return c

def lerpColor(c1, c2, x):
	red = c1.red + (c2.red - c1.red) * x
	green = c1.green + (c2.green - c1.green) * x
	blue = c1.blue + (c2.blue - c1.blue) * x
	return Gdk.RGBA(red, green, blue)


#---
class MonospaceView(Gtk.TextView):
	def __init__(self):
		Gtk.TextView.__init__(self)
		self.set_monospace(True)
		self.set_editable(False)
		padding = 10
		self.set_left_margin(padding)
		self.set_right_margin(padding)
		self.set_top_margin(padding)
		self.set_bottom_margin(padding)

		textColor = Gdk.RGBA()
		textColor.parse("#1abc9c")
		if isGtk(3):
			self.override_color(Gtk.StateFlags.NORMAL, textColor)

		self.lineFormattedMap = {}
		self.yscoll = None
		self.formatVisibleTimer = 0

		self.tagsReady = False

		self.searchMatches = []
		self.currentSearch = ''
		self.applySearchTimer = 0

	def initTags(self):
		if self.tagsReady:
			return
		buf = self.get_buffer()
		self.tag_found = buf.create_tag("found", background="#45452e")
		self.tagsReady = True

	def getAllText(self):
		buf = self.get_buffer()
		return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), include_hidden_chars=True)

	def getLineAt(self, offset):
		buf = self.get_buffer()
		startIter = buf.get_iter_at_offset(offset)
		# startIter = buf.get_iter_at_line(startIter.get_line())
		startIter = GtkTextBuffer_get_iter_at_line(buf, startIter.get_line()) # PyGTK GTK4 Workaround
		endIter = startIter.copy()

		endIter.forward_to_line_end()
		line = buf.get_text(startIter, endIter, include_hidden_chars=True)
		return line

	def iterLines(self, y1, y2):
		buf = self.get_buffer()
		for y in range(y1, y2+1):
			# startIter = buf.get_iter_at_line(y)
			startIter = GtkTextBuffer_get_iter_at_line(buf, y) # PyGTK GTK4 Workaround
			endIter = startIter.copy()
			endIter.forward_to_line_end()
			text = buf.get_text(startIter, endIter, include_hidden_chars=True)
			yield text, startIter, endIter, y


	def timeit(self, label=None, *args):
		if label:
			t2 = time.time()
			d = t2 - self.t
			log("{} {}: {:.4f}s".format(self.__class__.__name__, label, d), *args)
			self.t = t2
		else:
			self.t = time.time()
			log()

	def initScroll(self):
		if not self.yscoll:
			# self.yscoll = self.get_vadjustment() # Deprecated
			self.yscoll = Gtk.Scrollable.get_vadjustment(self)
			self.yscoll.connect('value-changed', self.onViewScroll)

	def onViewScroll(self, adjustment, data=None):
		# print("onViewScroll", adjustment.get_value())
		self.formatVisible()

	def formatVisible(self):
		self.resetFormatVisibleTimer()
		buf = self.get_buffer()
		r = self.get_visible_rect()
		iterTop, yTop = self.get_line_at_y(r.y)
		iterBottom, yBottom = self.get_line_at_y(r.y + r.height)
		lineTop = iterTop.get_line()
		lineBottom = iterBottom.get_line()
		# print("formatVisible", (lineTop, lineBottom), (r.x, r.y, r.width, r.height))
		if lineTop == 0 and lineBottom == 0:
			# The TextView isn't ready yet.
			self.scheduleFormatVisible(delay=20)
		else:
			for text, startIter, endIter, y in self.iterLines(lineTop, lineBottom):
				self.checkFormatLine(buf, text, startIter, endIter, y)

	def resetFormatVisibleTimer(self):
		if self.formatVisibleTimer != 0:
			GLib.source_remove(self.formatVisibleTimer)
			self.formatVisibleTimer = 0

	def scheduleFormatVisible(self, delay=400):
		self.formatVisibleTimer = GLib.timeout_add(delay, self.formatVisible)

	def checkFormatLine(self, buf, text, startIter, endIter, y):
		if self.lineFormattedMap.get(y, False):
			return

		self.formatLine(buf, text, startIter, endIter, y)
		self.lineFormattedMap[y] = True

	def formatLine(self, buf, text, startIter, endIter, y):
		pass

	#---
	def clearAllMatches(self):
		buf = self.get_buffer()
		buf.remove_tag(self.tag_found, buf.get_start_iter(), buf.get_end_iter())

	def highlightAllMatches(self, newSearch):
		buf = self.get_buffer()
		buf.remove_tag(self.tag_found, buf.get_start_iter(), buf.get_end_iter())

	def applySearch(self, newSearch):
		if newSearch == '':
			self.clearAllMatches()
		else:
			buf = self.get_buffer()
			if self.currentSearch == newSearch:
				# Continue from cursor
				cursor_mark = buf.get_insert()
				start = buf.get_iter_at_mark(cursor_mark)
				start.forward_line()
			else:
				# Start from top
				start = buf.get_start_iter()
			end = buf.get_end_iter()
			searchFlags = Gtk.TextSearchFlags.CASE_INSENSITIVE
			match = start.forward_search(newSearch, searchFlags, end)
			if match is not None:
				matchStart, matchEnd = match
				buf.apply_tag(self.tag_found, matchStart, matchEnd)
				buf.place_cursor(matchStart)
				self.scroll_to_iter(
					matchStart,
					within_margin=0.0,
					use_align=True,
					xalign=1.0, # Right Align so that we still see the log graph
					yalign=0.0, # Top Align
				)

		self.currentSearch = newSearch

		self.applySearchTimer = 0
		return False # Cancel applySearchTimer interval

	def resetApplySearchTimer(self):
		if self.applySearchTimer != 0:
			GLib.source_remove(self.applySearchTimer)
			self.applySearchTimer = 0

	def debouncedApplySearch(self, newSearch):
		self.resetApplySearchTimer()
		self.applySearchTimer = GLib.timeout_add(400, self.applySearch, newSearch)



class HistoryView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		if isGtk(3):
			self.override_font(Pango.font_description_from_string('Monospace 10'))
		self.logStdout = ''
		self.currentFilter = ''
		self.applyFilterTimer = 0
		self.dirPath = None

	def initTags(self):
		if self.tagsReady:
			return
		buf = self.get_buffer()
		self.tag_graph = buf.create_tag("graph", foreground="#1abc9c") # Normal
		self.tag_sha = buf.create_tag("sha", foreground="#dfaf8f") # Orange / Color4
		self.tag_decorations = buf.create_tag("decorations", foreground="#dca3a3") # Red / Color2
		self.tag_head = buf.create_tag("head", foreground="#93e0e3") # Cyan / Color7
		self.tag_remote = buf.create_tag("remote", foreground="#dca3a3") # Red / Color2
		self.tag_local = buf.create_tag("local", foreground="#72d5a3") # Green / Color3
		self.tag_tag = buf.create_tag("tag", foreground="#f0dfaf") # Yellow / Color4
		# self.tag_summary = buf.create_tag("summary", foreground="#1abc9c") # Normal
		self.tag_selected = buf.create_tag("selected", weight=Pango.Weight.BOLD, foreground="#111111", background="#dfaf8f")
		MonospaceView.initTags(self)

	def setDirPath(self, dirPath):
		self.dirPath = dirPath

	def populate(self):
		self.timeit()
		cmd = [
			'git',
			'-C',
			cwdAbs,
			'log',
			'--oneline',
			'--graph',
			'--decorate',
			'--all',
		]

		if self.dirPath != None:
			cmd.append(self.dirPath)

		process = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
		self.timeit('process')
		self.logStdout = process.stdout.strip()
		self.timeit('strip')

		self.setAndFormatText(self.logStdout)

	def setAndFormatText(self, text):
		# This is faster than get_buffer().set_text(logStdout)
		# textBuffer = Gtk.TextBuffer()
		# textBuffer.set_text(text)
		# self.tagsReady = False
		# self.set_buffer(textBuffer)
		# self.timeit('TextBuffer')

		buf = self.get_buffer()
		buf.set_text(text)
		self.timeit('set_text')

		self.initTags()
		self.timeit('initTags')

		self.selectHead()
		self.timeit('place_cursor')

		self.lineFormattedMap.clear()
		self.formatVisible()
		self.initScroll()
		self.timeit('formatVisible')

	def selectHead(self):
		buf = self.get_buffer()
		for match in LOG_PATTERN.finditer(self.getAllText()):
			if match.group(4):
				groupStart = match.start(4)
				for subMatch in re.finditer(r'(\(|, )(HEAD)( -> (.+?))?(,|\))', match.group(4)):
					start = groupStart + subMatch.start(0)
					startIter = buf.get_iter_at_offset(start)
					buf.place_cursor(startIter)

					# Scroll to cursor doesn't work this early it seems.
					self.scroll_to_iter(
						startIter,
						within_margin=0.0,
						use_align=True,
						xalign=0.0, # Left Align
						yalign=0.0, # Top Align
					)
					return

		# Could not find HEAD, select start of buffer.
		buf.place_cursor(buf.get_start_iter())

	def formatLine(self, buf, text, startIter, endIter, y):
		searchOffset = startIter.get_offset()
		# print('formatLine', searchOffset, text)

		for match in LOG_PATTERN.finditer(text):
			applyTagForGroup(buf, match, 1, self.tag_graph, searchOffset=searchOffset)
			applyTagForGroup(buf, match, 3, self.tag_sha, searchOffset=searchOffset)
			applyTagForGroup(buf, match, 4, self.tag_decorations, searchOffset=searchOffset)
			# applyTagForGroup(buf, match, 5, self.tag_summary, searchOffset=searchOffset)

			if match.group(4):
				groupOffset = searchOffset + match.start(4)
				for subMatch in re.finditer(r'(\(|, )(tag: .+?)(,|\))', match.group(4)):
					applyTagForGroup(buf, subMatch, 2, self.tag_tag, searchOffset=groupOffset)
				for subMatch in re.finditer(r'(\(|, )((HEAD ->) (.+?))(,|\))', match.group(4)):
					applyTagForGroup(buf, subMatch, 3, self.tag_head, searchOffset=groupOffset)
					applyTagForGroup(buf, subMatch, 4, self.tag_local, searchOffset=groupOffset)
				for subMatch in re.finditer(r'(\(|, )([^\/]+)(,|\))', match.group(4)):
					applyTagForGroup(buf, subMatch, 2, self.tag_local, searchOffset=groupOffset)

	#---
	def applyFilter(self, newFilter):
		if newFilter == '':
			self.setAndFormatText(self.logStdout)

			pass
		else:
			# We need to re-populate then filter
			filteredLines = []
			for line in self.logStdout.splitlines():
				if newFilter in line:
					filteredLines.append(line)
			self.setAndFormatText('\n'.join(filteredLines))

		self.currentFilter = newFilter

		self.applyFilterTimer = 0
		return False # Cancel applyFilterTimer interval

	def resetApplyFilterTimer(self):
		if self.applyFilterTimer != 0:
			GLib.source_remove(self.applyFilterTimer)
			self.applyFilterTimer = 0

	def debouncedApplyFilter(self, newFilter):
		self.resetApplyFilterTimer()
		self.applyFilterTimer = GLib.timeout_add(400, self.applyFilter, newFilter)



class CommitView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		# self.set_wrap_mode(Gtk.WrapMode.WORD)
		if isGtk(3):
			self.override_font(Pango.font_description_from_string('Monospace 13'))
		self.dirPath = None
		self.currentSha = ''
		self.showingAll = False

	def initTags(self):
		if self.tagsReady:
			return
		buf = self.get_buffer()

		viewBg = rgba("#2d2d2d") # Adwaita Dark

		self.tag_commitstat = buf.create_tag("commitstat", foreground="#a6acb9") # Light Gray
		if isGtk(3):
			commitstatFg = self.tag_commitstat.get_property('foreground-rgba')
			commitstatBg = lerpColor(viewBg, commitstatFg, 0.1)
			self.tag_commitstat.set_property('paragraph-background', commitstatBg.to_string())

		self.tag_statfilename = buf.create_tag("statfilename", weight=Pango.Weight.BOLD)

		self.tag_oldline = buf.create_tag("oldline", foreground="#dca3a3") # Red / Color2
		if isGtk(3):
			oldlineFg = self.tag_oldline.get_property('foreground-rgba')
			oldlineBg = lerpColor(viewBg, oldlineFg, 0.1)
			self.tag_oldline.set_property('paragraph-background', oldlineBg.to_string())

		self.tag_newline = buf.create_tag("newline", foreground="#72d5a3") # Green / Color3
		if isGtk(3):
			newlineFg = self.tag_newline.get_property('foreground-rgba')
			newlineBg = lerpColor(viewBg, newlineFg, 0.1)
			self.tag_newline.set_property('paragraph-background', newlineBg.to_string())

		self.tag_hunkheader = buf.create_tag("hunkheader", foreground="#a6acb9") # Light Gray
		self.tag_diffheader = buf.create_tag("diffheader", foreground="#c695c6") # Purple

		MonospaceView.initTags(self)

	def setDirPath(self, dirPath):
		self.dirPath = dirPath

	def selectSha(self, sha, showAll=False):
		if sha == self.currentSha and showAll == self.showingAll:
			return

		self.timeit()
		cmd = [
			'git',
			'-C',
			cwdAbs,
			'show',
			sha,
			'--patch-with-stat',
		]
		if self.dirPath is None:
			showAll = True
		if self.dirPath is not None and not showAll:
			cmd += [
				'--relative',
				self.dirPath,
			]

		self.commitProcess = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
		commitStdout = self.commitProcess.stdout
		self.timeit('process')

		buf = self.get_buffer()
		buf.set_text(commitStdout)
		self.timeit('set_text')

		self.initTags()
		self.timeit('initTags')

		buf.place_cursor(buf.get_start_iter())
		self.timeit('place_cursor')

		self.formatView()
		self.timeit('formatView')

		self.lineFormattedMap.clear()
		self.formatVisible()
		self.initScroll()
		self.timeit('formatVisible')

		self.currentSha = sha
		self.showingAll = showAll

	def showAll(self):
		self.selectSha(self.currentSha, showAll=True)

	def formatLine(self, buf, text, startIter, endIter, y):
		searchOffset = startIter.get_offset()
		# print('formatLine', searchOffset, text)

		if len(startIter.get_tags()) >= 1:
			return # formatView already handled this line

		for match in OLDLINE_PATTERN.finditer(text):
			applyTagForGroup(buf, match, 0, self.tag_oldline, searchOffset=searchOffset)
		for match in NEWLINE_PATTERN.finditer(text):
			applyTagForGroup(buf, match, 0, self.tag_newline, searchOffset=searchOffset)
		for match in HUNKHEADER_PATTERN.finditer(text):
			applyTagForGroup(buf, match, 0, self.tag_hunkheader, searchOffset=searchOffset)

	def formatView(self):
		buf = self.get_buffer()
		allText = self.getAllText()

		for match in COMMITHEADER_PATTERN.finditer(allText):
			applyTagForGroup(buf, match, 1, self.tag_hunkheader)
			applyTagForGroup(buf, match, 5, self.tag_hunkheader)
			applyTagForGroup(buf, match, 6, self.tag_commitstat)

			for statFileMatch in STATFILE_PATTERN.finditer(allText, match.start(6), match.end(6)):
				applyTagForGroup(buf, statFileMatch, 1, self.tag_statfilename)
				applyTagForGroup(buf, statFileMatch, 3, self.tag_newline)
				applyTagForGroup(buf, statFileMatch, 4, self.tag_oldline)

		for match in DIFF_PATTERN.finditer(allText):
			applyTagForGroup(buf, match, 1, self.tag_diffheader)


class TextSearchBar(SearchBar):
	def __init__(self):
		Gtk.SearchBar.__init__(self)
		self.set_show_close_button(True)

		self.entry = Gtk.SearchEntry()
		if isGtk(3):
			self.entry.set_placeholder_text('Search (Ctrl+F)')
		self.entry.connect('activate', self.onSearchChanged)
		self.entry.connect('stop-search', self.onStopSearch)
		self.connect_entry(self.entry)
		self.add(self.entry)

		self.textView = None

	def setTextView(self, textView):
		self.textView = textView

	def onSearchChanged(self, buffer, data=None):
		if not self.textView:
			raise Exception("TextSearchBar.textView not set")
		if not self.textView.tagsReady:
			raise Exception("TextSearchBar.tagsReady=False. Call initTags().")

		newSearch = self.entry.get_text()
		self.textView.debouncedApplySearch(newSearch)

	def onStopSearch(self, entry, user_data=None):
		print('onStopSearch')
		self.textView.grab_focus()
		self.textView.clearAllMatches()


class MainWindow(ApplicationWindow):
	def __init__(self, app):
		Gtk.Window.__init__(self, title="gitz", application=app)
		self.set_title("gitz - {}".format(cwdAbs))
		self.set_icon_name("git-gui")
		self.set_default_size(1800, 720)
		if isGtk(3):
			self.set_position(Gtk.WindowPosition.CENTER)

		# Force dark theme
		settings = Gtk.Settings.get_default()
		settings.set_property("gtk-theme-name", "Adwaita")
		settings.set_property("gtk-application-prefer-dark-theme", True)

		#--- Left
		self.historyView = HistoryView()
		historyTextBuffer = self.historyView.get_buffer()
		historyTextBuffer.connect('notify::cursor-position', self.onHistoryViewMoveCursor)

		self.historySearchBar = TextSearchBar()
		self.historySearchBar.setTextView(self.historyView)

		self.leftPane = ScrolledWindow()
		self.leftPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.leftPane.add(self.historyView)

		self.leftPaneBox = VBox()
		self.leftPaneBox.pack_start(self.historySearchBar, expand=False, fill=True, padding=0)
		self.leftPaneBox.pack_start(self.leftPane, expand=True, fill=True, padding=0)

		#--- Right
		self.commitView = CommitView()

		self.commitSearchBar = TextSearchBar()
		self.commitSearchBar.setTextView(self.commitView)

		self.rightPane = ScrolledWindow()
		self.rightPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.rightPane.add(self.commitView)

		self.showAllButton = Gtk.Button.new_with_label("Show Full Commit")
		self.showAllButton.connect('clicked', self.onCommitViewShowAll)

		self.rightPaneBox = VBox()
		self.rightPaneBox.pack_start(self.commitSearchBar, expand=False, fill=True, padding=0)
		self.rightPaneBox.pack_start(self.rightPane, expand=True, fill=True, padding=0)
		self.rightPaneBox.pack_start(self.showAllButton, expand=False, fill=True, padding=0)

		#---
		self.pane = HPaned()
		self.pane.add1(self.leftPaneBox)
		self.pane.add2(self.rightPaneBox)
		self.pane.set_position(600)
		self.add(self.pane)

		#---
		if isGtk(3):
			self.connect("key-press-event", self.onKeyPress)

		#---
		self.historyView.grab_focus()

	def setDirPath(self, dirPath):
		self.historyView.setDirPath(dirPath)
		self.commitView.setDirPath(dirPath)
		self.set_title("gitz - {}".format(dirPath))

	def onKeyPress(self, widget, event, *args):
		state = event.state
		ctrl = (state & Gdk.ModifierType.CONTROL_MASK)
		if ctrl and event.keyval == 113: # Ctrl+Q
			self.close()
		elif ctrl and event.keyval == 119: # Ctrl+W
			self.close()
		elif ctrl and event.keyval == 102: # Ctrl+F
			if self.get_focus() == self.historyView:
				self.historySearchBar.set_search_mode(True)
			elif self.get_focus() == self.commitView:
				self.commitSearchBar.set_search_mode(True)
		elif event.keyval == 65307: # Esc
			if self.get_focus() == self.historySearchBar.entry:
				pass
			elif self.get_focus() == self.commitSearchBar.entry:
				pass
			else:
				self.close()

	def onCommitViewShowAll(self, button):
		self.commitView.showAll()
		self.showAllButton.set_visible(False)

	def onHistoryViewMoveCursor(self, buffer, data=None):
		if not self.historyView.tagsReady:
			return # Not yet ready

		line = self.historyView.getLineAt(buffer.props.cursor_position)
		match = LOG_PATTERN.match(line)
		if match:
			sha = match.group(3)
			if sha:
				historyBuf = self.historyView.get_buffer()

				historyBuf.remove_tag(self.historyView.tag_selected, historyBuf.get_start_iter(), historyBuf.get_end_iter())

				cursorIter = historyBuf.get_iter_at_offset(buffer.props.cursor_position)
				lineNumber = cursorIter.get_line()

				def highlightGroup(group):
					start = match.start(group)
					end = match.end(group)
					# startIter = historyBuf.get_iter_at_line_offset(lineNumber, start)
					# endIter = historyBuf.get_iter_at_line_offset(lineNumber, end)
					startIter = GtkTextBuffer_get_iter_at_line_offset(historyBuf, lineNumber, start) # PyGTK GTK4 Workaround
					endIter = GtkTextBuffer_get_iter_at_line_offset(historyBuf, lineNumber, end) # PyGTK GTK4 Workaround
					historyBuf.apply_tag(self.historyView.tag_selected, startIter, endIter)
				highlightGroup(3)


				self.commitView.selectSha(sha)
				self.showAllButton.set_visible(not self.commitView.showingAll)



class App(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self, flags=Gio.ApplicationFlags.HANDLES_OPEN)
		GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)
		self.dirPath = None

	def do_activate(self):
		self.timeit()
		self.win = MainWindow(self)
		if self.dirPath is not None:
			self.win.setDirPath(self.dirPath)
		self.timeit('construct')

		if isGtk(3):
			self.win.show_all()
		elif isGtk(4):
			self.win.present()
		self.timeit('show_all')

		self.win.historyView.populate()
		self.timeit('populate')

	# Note: The docs mention it's (self, files, hints) but in reality it's (self, files, n_files, hints).
	# The doc text mentions a n_files argument, but it's not mentioned in the argument list.
	# I used (self, *args) and print(args) to confirm this.
	# https://lazka.github.io/pgi-docs/Gio-2.0/classes/Application.html#Gio.Application.do_open
	def do_open(self, files, n_files, hints):
		if n_files >= 1:
			self.dirPath = files[0].get_path()
			print('do_open', self.dirPath)
			self.activate()

	def do_startup(self):
		Gtk.Application.do_startup(self)

	def timeit(self, label=None, *args):
		if label:
			t2 = time.time()
			d = t2 - self.t
			log("{} {}: {:.4f}s".format(self.__class__.__name__, label, d), *args)
			self.t = t2
		else:
			self.t = time.time()
			log()



app = App()
exit_status = app.run(sys.argv)
sys.exit(exit_status)
