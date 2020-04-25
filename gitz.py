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

cmd = [
	'git',
	'-C',
	cwdAbs,
	'log',
	# '--oneline',
	'--pretty=oneline',
	'--abbrev-commit',
	'--graph',
	'--decorate',
	'--all',
	# '--color',
]
process = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
logStdout = process.stdout

# logStdout = re.sub('\x1B' + r'\[.*?m', r'', logStdout)

# logTags = ''
# logText = ''
# for line in logStdout.splitlines():
# 	# line = re.sub(r' (\w{7}) ', r' <b>\1</b> ', line)
# 	for match in line.
# 	line = line.split('')
# 	# logText += line + '\n'


class MainWindow(Gtk.ApplicationWindow):

	def __init__(self, app):
		Gtk.Window.__init__(self, title="TextView Example", application=app)
		self.set_default_size(1280, 720)

		# Force dark theme
		settings = Gtk.Settings.get_default()
		settings.set_property("gtk-theme-name", "Adwaita")
		settings.set_property("gtk-application-prefer-dark-theme", True)

		#--- Left
		# self.leftTextBuffer = Gtk.TextBuffer()
		# self.leftTextBuffer.set_text(logText)

		self.leftTextView = Gtk.TextView()
		# self.leftTextView.set_wrap_mode(Gtk.WrapMode.WORD)
		self.leftTextView.set_monospace(True)

		leftTextBuffer = self.leftTextView.get_buffer()
		leftTextBuffer.set_text(logStdout)
		self.tag_bold = leftTextBuffer.create_tag("bold", weight=Pango.Weight.BOLD)
		self.tag_graph = leftTextBuffer.create_tag("graph", foreground="#1abc9c") # Normal
		self.tag_sha = leftTextBuffer.create_tag("sha", foreground="#dfaf8f") # Orange / Color4
		self.tag_head = leftTextBuffer.create_tag("head", foreground="#8cd0d3") # Cyan / Color7
		self.tag_remote = leftTextBuffer.create_tag("remote", foreground="#dca3a3") # Red / Color2
		self.tag_local = leftTextBuffer.create_tag("local", foreground="#72d5a3") # Green / Color3
		self.tag_tag = leftTextBuffer.create_tag("tag", foreground="#f0dfaf") # Yellow / Color4
		self.tag_summary = leftTextBuffer.create_tag("summary", foreground="#1abc9c") # Normal


		pattern = r'^([ \*\|\\\/]+)((\w{7}) (\([^)]+\) )?(.+))?$'
		print(pattern)

		def applyTagForGroup(match, group, tag):
			start = match.start(group)
			end = match.end(group)
			print(match, start, end)
			startIter = leftTextBuffer.get_iter_at_offset(start)
			endIter = leftTextBuffer.get_iter_at_offset(end)
			leftTextBuffer.apply_tag(tag, startIter, endIter)

		for match in re.finditer(pattern, logStdout, re.MULTILINE):
			applyTagForGroup(match, 1, self.tag_graph)
			applyTagForGroup(match, 3, self.tag_sha)
			applyTagForGroup(match, 4, self.tag_head)
			applyTagForGroup(match, 5, self.tag_summary)

		self.leftPane = Gtk.ScrolledWindow()
		self.leftPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.leftPane.add(self.leftTextView)

		#--- Right
		self.rightTextBuffer = Gtk.TextBuffer()

		self.rightTextView = Gtk.TextView(buffer=self.rightTextBuffer)
		# self.rightTextView.set_wrap_mode(Gtk.WrapMode.WORD)
		self.leftTextView.set_monospace(True)

		self.rightPane = Gtk.ScrolledWindow()
		self.rightPane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
		self.rightPane.add(self.rightTextView)

		#---
		# self.box = Gtk.Box(spacing=6)
		# self.box.pack_start(self.leftPane, expand=True, fill=True, padding=0)
		# self.box.pack_start(self.rightPane, expand=True, fill=True, padding=0)
		# self.add(self.box)

		self.pane = Gtk.HPaned()
		self.pane.add1(self.leftPane)
		self.pane.add2(self.rightPane)
		self.pane.set_position(600)
		self.add(self.pane)

	def applyTag(self, textbuffer, tag):
		start = textbuffer.get_start_iter()
		end = textbuffer.get_end_iter()
		match = start.forward_search(text, 0, end)

		if match is not None:
			match_start, match_end = match
			textbuffer.apply_tag(self.tag_bold, match_start, match_end)
			self.search_and_mark(text, match_end)

	def markCommitSha(self):
		pass


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
