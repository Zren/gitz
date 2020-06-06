#!/bin/python3

import os
import sys
import signal
import subprocess
import re
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

cwd = os.getcwd()
cwdAbs = os.path.abspath(os.path.expanduser(cwd))



LOG_PATTERN = r'^([ \*\|\\\/]+)((\w{6,}) (\([^)]+\) )?(.+))?$'


#---
def log(*args):
	# print(*args) # Comment to hide debug log
	return

def applyTagForGroup(buf, match, group, tag):
	start = match.start(group)
	end = match.end(group)
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
		self.override_color(Gtk.StateFlags.NORMAL, textColor)
		# self.tag_summary = buf.create_tag("summary", foreground="#1abc9c") # Normal

	def getAllText(self):
		buf = self.get_buffer()
		return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), include_hidden_chars=True)

	def getLineAt(self, offset):
		buf = self.get_buffer()
		startIter = buf.get_iter_at_offset(offset)
		startIter = buf.get_iter_at_line(startIter.get_line())
		endIter = startIter.copy()
		endIter.forward_to_line_end()
		line = buf.get_text(startIter, endIter, include_hidden_chars=True)
		return line

	def timeit(self, label=None, *args):
		if label:
			t2 = time.time()
			d = t2 - self.t
			log("{} {}: {:.4f}s".format(self.__class__.__name__, label, d), *args)
			self.t = t2
		else:
			self.t = time.time()
			log()



class HistoryView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		self.override_font(Pango.font_description_from_string('Monospace 10'))
		self.tagsReady = False

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
		self.tagsReady = True

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
		process = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
		self.timeit('process')
		logStdout = process.stdout.strip()
		self.timeit('strip')

		# This is faster than get_buffer().set_text(logStdout)
		# textBuffer = Gtk.TextBuffer()
		# textBuffer.set_text(logStdout)
		# self.tagsReady = False
		# self.set_buffer(textBuffer)
		# self.timeit('TextBuffer')

		buf = self.get_buffer()
		buf.set_text(logStdout)
		self.timeit('set_text')

		self.initTags()
		self.timeit('initTags')

		buf = self.get_buffer()
		buf.place_cursor(buf.get_start_iter())
		self.timeit('place_cursor')

		self.formatView()
		self.timeit('formatView')

	def formatView(self):
		buf = self.get_buffer()
		for match in re.finditer(LOG_PATTERN, self.getAllText(), re.MULTILINE):
			applyTagForGroup(buf, match, 1, self.tag_graph)
			applyTagForGroup(buf, match, 3, self.tag_sha)
			applyTagForGroup(buf, match, 4, self.tag_decorations)
			# applyTagForGroup(buf, match, 5, self.tag_summary)

			def highlightGroup(groupStart, subMatch, group, tag):
				start = groupStart + subMatch.start(group)
				end = groupStart + subMatch.end(group)
				startIter = buf.get_iter_at_offset(start)
				endIter = buf.get_iter_at_offset(end)
				buf.apply_tag(tag, startIter, endIter)

			if match.group(4):
				groupStart = match.start(4)
				for subMatch in re.finditer(r'(\(|, )(tag: .+?)(,|\))', match.group(4)):
					highlightGroup(groupStart, subMatch, 2, self.tag_tag)
				for subMatch in re.finditer(r'(\(|, )((HEAD ->) (.+?))(,|\))', match.group(4)):
					highlightGroup(groupStart, subMatch, 3, self.tag_head)
					highlightGroup(groupStart, subMatch, 4, self.tag_local)
				for subMatch in re.finditer(r'(\(|, )([^\/]+)(,|\))', match.group(4)):
					highlightGroup(groupStart, subMatch, 2, self.tag_local)




class CommitView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		# self.set_wrap_mode(Gtk.WrapMode.WORD)
		self.override_font(Pango.font_description_from_string('Monospace 13'))
		self.tagsReady = False

	def initTags(self):
		if self.tagsReady:
			return
		buf = self.get_buffer()

		viewBg = rgba("#2d2d2d") # Adwaita Dark

		self.tag_oldline = buf.create_tag("oldline", foreground="#dca3a3") # Red / Color2
		oldlineFg = self.tag_oldline.get_property('foreground-rgba')
		oldlineBg = lerpColor(viewBg, oldlineFg, 0.1)
		self.tag_oldline.set_property('paragraph-background', oldlineBg.to_string())

		self.tag_newline = buf.create_tag("newline", foreground="#72d5a3") # Green / Color3
		newlineFg = self.tag_newline.get_property('foreground-rgba')
		newlineBg = lerpColor(viewBg, newlineFg, 0.1)
		self.tag_newline.set_property('paragraph-background', newlineBg.to_string())

		self.tag_hunkheader = buf.create_tag("hunkheader", foreground="#a6acb9") # Light Gray
		self.tag_diffheader = buf.create_tag("diffheader", foreground="#c695c6") # Purple
		self.tagsReady = True

	def selectSha(self, sha):
		if sha == self.selectSha:
			return

		self.timeit()
		cmd = [
			'git',
			'-C',
			cwdAbs,
			'show',
			sha,
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

	def formatView(self):
		buf = self.get_buffer()
		allText = self.getAllText()
		OLDLINE_PATTERN = r'^\-.*$'
		for match in re.finditer(OLDLINE_PATTERN, allText, re.MULTILINE):
			applyTagForGroup(buf, match, 0, self.tag_oldline)
		NEWLINE_PATTERN = r'^\+.*$'
		for match in re.finditer(NEWLINE_PATTERN, allText, re.MULTILINE):
			applyTagForGroup(buf, match, 0, self.tag_newline)
		HUNKHEADER_PATTERN = r'^@@.+$'
		for match in re.finditer(HUNKHEADER_PATTERN, allText, re.MULTILINE):
			applyTagForGroup(buf, match, 0, self.tag_hunkheader)
		COMMITHEADER_PATTERN = r'^(commit ((.|\n)+?))\ndiff'
		for match in re.finditer(COMMITHEADER_PATTERN, allText):
			applyTagForGroup(buf, match, 1, self.tag_hunkheader)
		DIFF_PATTERN = r'\n(diff ((.|\n)+?))\n(\-\-\-|\+\+\+)'
		for match in re.finditer(DIFF_PATTERN, allText):
			applyTagForGroup(buf, match, 1, self.tag_diffheader)



class MainWindow(Gtk.ApplicationWindow):

	def __init__(self, app):
		Gtk.Window.__init__(self, title="gitz", application=app)
		self.set_icon_name("git-gui")
		self.set_default_size(1800, 720)
		self.set_position(Gtk.WindowPosition.CENTER)

		# Force dark theme
		settings = Gtk.Settings.get_default()
		settings.set_property("gtk-theme-name", "Adwaita")
		settings.set_property("gtk-application-prefer-dark-theme", True)

		#--- Left
		self.historyView = HistoryView()
		historyTextBuffer = self.historyView.get_buffer()
		historyTextBuffer.connect('notify::cursor-position', self.onHistoryViewMoveCursor)

		self.filterEntry = Gtk.Entry()
		self.filterEntry.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, 'search')
		self.filterEntry.set_placeholder_text('Search')

		self.leftPane = Gtk.ScrolledWindow()
		self.leftPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.leftPane.add(self.historyView)

		self.leftPaneBox = Gtk.VBox()
		self.leftPaneBox.pack_start(self.filterEntry, expand=False, fill=True, padding=0)
		self.leftPaneBox.pack_start(self.leftPane, expand=True, fill=True, padding=0)

		#--- Right
		self.selectedSha = ''

		self.commitView = CommitView()

		self.rightPane = Gtk.ScrolledWindow()
		self.rightPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.rightPane.add(self.commitView)

		#---
		self.pane = Gtk.HPaned()
		self.pane.add1(self.leftPaneBox)
		self.pane.add2(self.rightPane)
		self.pane.set_position(600)
		self.add(self.pane)

		#---
		self.connect("key-press-event", self.onKeyPress)

	def onKeyPress(self, widget, event, *args):
		state = event.state
		ctrl = (state & Gdk.ModifierType.CONTROL_MASK)
		if ctrl and event.keyval == 113: # Ctrl+Q
			self.close()
		elif ctrl and event.keyval == 119: # Ctrl+W
			self.close()
		elif event.keyval == 65307: # Esc
			self.close()


	def onHistoryViewMoveCursor(self, buffer, data=None):
		if not self.historyView.tagsReady:
			return # Not yet ready

		line = self.historyView.getLineAt(buffer.props.cursor_position)
		match = re.match(LOG_PATTERN, line)
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
					startIter = historyBuf.get_iter_at_line_offset(lineNumber, start)
					endIter = historyBuf.get_iter_at_line_offset(lineNumber, end)
					historyBuf.apply_tag(self.historyView.tag_selected, startIter, endIter)
				highlightGroup(3)


				self.commitView.selectSha(sha)



class App(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self)
		GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

	def do_activate(self):
		self.timeit()
		self.win = MainWindow(self)
		self.timeit('construct')
		self.win.show_all()
		self.timeit('show_all')
		self.win.historyView.populate()
		self.timeit('populate')

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
