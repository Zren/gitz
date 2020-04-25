#!/bin/python3

import os
import sys
import subprocess
import re

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango

cwd = '~/Code/plasma-applets/simpleweather/'
cwdAbs = os.path.abspath(os.path.expanduser(cwd))



LOG_PATTERN = r'^([ \*\|\\\/]+)((\w{7}) (\([^)]+\) )?(.+))?$'


#---
def applyTagForGroup(buf, match, group, tag):
	start = match.start(group)
	end = match.end(group)
	# print(match, start, end)
	startIter = buf.get_iter_at_offset(start)
	endIter = buf.get_iter_at_offset(end)
	buf.apply_tag(tag, startIter, endIter)


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

	def getAllText(self):
		buf = self.get_buffer()
		return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

	def getLineAt(self, offset):
		buf = self.get_buffer()
		startIter = buf.get_iter_at_offset(offset)
		startIter = buf.get_iter_at_line(startIter.get_line())
		endIter = startIter.copy()
		endIter.forward_to_line_end()
		line = buf.get_text(startIter, endIter, True)
		return line

class HistoryView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		self.override_font(Pango.font_description_from_string('Monospace 10'))
		#---
		buf = self.get_buffer()
		self.tag_bold = buf.create_tag("bold", weight=Pango.Weight.BOLD)
		self.tag_graph = buf.create_tag("graph", foreground="#1abc9c") # Normal
		self.tag_sha = buf.create_tag("sha", foreground="#dfaf8f") # Orange / Color4
		self.tag_head = buf.create_tag("head", foreground="#8cd0d3") # Cyan / Color7
		self.tag_remote = buf.create_tag("remote", foreground="#dca3a3") # Red / Color2
		self.tag_local = buf.create_tag("local", foreground="#72d5a3") # Green / Color3
		self.tag_tag = buf.create_tag("tag", foreground="#f0dfaf") # Yellow / Color4
		self.tag_summary = buf.create_tag("summary", foreground="#1abc9c") # Normal

	def populate(self):
		cmd = [
			'git',
			'-C',
			cwdAbs,
			'log',
			'--oneline',
			'--graph',
			'--decorate',
			'--all',
			# '--color',
		]
		process = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
		logStdout = process.stdout
		buf = self.get_buffer()
		buf.set_text(logStdout)
		self.formatView()
		buf.place_cursor(buf.get_start_iter())

	def formatView(self):
		buf = self.get_buffer()
		for match in re.finditer(LOG_PATTERN, self.getAllText(), re.MULTILINE):
			applyTagForGroup(buf, match, 1, self.tag_graph)
			applyTagForGroup(buf, match, 3, self.tag_sha)
			applyTagForGroup(buf, match, 4, self.tag_head)
			applyTagForGroup(buf, match, 5, self.tag_summary)



class CommitView(MonospaceView):
	def __init__(self):
		MonospaceView.__init__(self)
		# self.set_wrap_mode(Gtk.WrapMode.WORD)
		self.override_font(Pango.font_description_from_string('Monospace 13'))
		buf = self.get_buffer()
		self.tag_oldline = buf.create_tag("oldline", foreground="#dca3a3") # Red / Color2
		self.tag_newline = buf.create_tag("newline", foreground="#72d5a3") # Green / Color3
		self.tag_hunkheader = buf.create_tag("hunkheader", foreground="#a6acb9") # Light Gray
		self.tag_diffheader = buf.create_tag("diffheader", foreground="#c695c6") # Purple

	def selectSha(self, sha):
		if sha == self.selectSha:
			return

		cmd = [
			'git',
			'-C',
			cwdAbs,
			'show',
			sha,
		]
		self.commitProcess = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
		commitStdout = self.commitProcess.stdout
		self.get_buffer().set_text(commitStdout)
		self.formatView()

	def formatView(self):
		buf = self.get_buffer()
		allText = self.getAllText()
		OLDLINE_PATTERN = r'^\-.+$'
		for match in re.finditer(OLDLINE_PATTERN, allText, re.MULTILINE):
			applyTagForGroup(buf, match, 0, self.tag_oldline)
		NEWLINE_PATTERN = r'^\+.+$'
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
		Gtk.Window.__init__(self, title="TextView Example", application=app)
		self.set_default_size(1800, 720)
		self.set_position(Gtk.WindowPosition.CENTER)

		# Force dark theme
		settings = Gtk.Settings.get_default()
		settings.set_property("gtk-theme-name", "Adwaita")
		settings.set_property("gtk-application-prefer-dark-theme", True)

		#--- Left
		self.historyView = HistoryView()
		leftTextBuffer = self.historyView.get_buffer()
		leftTextBuffer.connect('notify::cursor-position', self.onHistoryViewMoveCursor)

		self.leftPane = Gtk.ScrolledWindow()
		self.leftPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.leftPane.add(self.historyView)

		#--- Right
		self.selectedSha = ''

		self.commitView = CommitView()
		self.rightTextBuffer = self.commitView.get_buffer()

		self.rightPane = Gtk.ScrolledWindow()
		self.rightPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.rightPane.add(self.commitView)

		#---
		self.pane = Gtk.HPaned()
		self.pane.add1(self.leftPane)
		self.pane.add2(self.rightPane)
		self.pane.set_position(600)
		self.add(self.pane)

		self.historyView.populate()


	def onHistoryViewMoveCursor(self, buffer, data=None):
		line = self.historyView.getLineAt(buffer.props.cursor_position)
		match = re.match(LOG_PATTERN, line)
		if match:
			sha = match.group(3)
			if sha:
				self.commitView.selectSha(sha)



class App(Gtk.Application):
	def __init__(self):
		Gtk.Application.__init__(self)

	def do_activate(self):
		self.win = MainWindow(self)
		self.win.show_all()

	def do_startup(self):
		Gtk.Application.do_startup(self)



app = App()
exit_status = app.run(sys.argv)
sys.exit(exit_status)
