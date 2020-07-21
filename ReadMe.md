# gitz

Replacement for `gitk`.

Closes with `Ctrl+W`, `Ctrl+Q`, or `Esc`. Arrow Keys select commits. `Tab` switches focus between history and commit view.

![](https://i.imgur.com/qa2S5IX.png)

## Installation

```
git clone https://github.com/Zren/gitz.git
cd gitz
chmod +x ./gitz.py
sudo cp ./gitz.py /usr/local/bin/gitz
```

## Tips

### Open a subdir in `gitz`

Run

```
cd ~/kde/src/plasma-workspace
gitz ./applets/digital-clock
```

or


```
cd ~/kde/src/plasma-workspace/applets/digital-clock
gitz .
```

to only list commits from `./applets/digital-clock` in the history view, and only the changes to files in that folder in the commit view. There is a "Show full commit" button if you want to read the entire commit.


### Bind `Ctrl+Shift+K` to open `gitz` in SublimeText

Create `~/.config/sublime-text-3/Packages/User/gitz.py` with:

```
subl ~/.config/sublime-text-3/Packages/User/gitz.py
```

Then add the following code to run `gitz` when we call the `open_gitz` sublime command.

```
# Based on Terminal.py

import sublime
import sublime_plugin
import os
import sys
import subprocess


class OpenGitzCommand(sublime_plugin.WindowCommand):
	def get_path(self, paths):
		if paths:
			return paths[0]
		# DEV: On ST3, there is always an active view.
		#   Be sure to check that it's a file with a path (not temporary view)
		elif self.window.active_view() and self.window.active_view().file_name():
			return self.window.active_view().file_name()
		elif self.window.folders():
			return self.window.folders()[0]
		else:
			sublime.error_message('Terminal: No place to open terminal to')
			return False

	def run(self, paths=[], parameters=None, terminal=None):
		path = self.get_path(paths)
		if not path:
			return

		if os.path.isfile(path):
			path = os.path.dirname(path)

		subprocess.Popen([
			'gitz'
		], cwd=path)
```

Then open the Command Palette `Ctrl+Shift+P` and search for `Preferences: Key Bindings`. Paste the following shortcut to bind `Ctrl+Shift+K` to run the `open_gitz` command.

```
	, { "keys": ["ctrl+shift+k"], "command": "open_gitz" }
```
