import sublime, sublime_plugin
import functools
import os
import os.path
import subprocess
import sys
import threading

class AsyncGradleProcess(object):
  def __init__(self, listener, tasks, cwd):
    self.listener = listener
    self.tasks = tasks

    startupinfo = None

    settings = sublime.load_settings('SublimeGradle.sublime-settings')
    gradle_command = settings.get("gradle_command")
    if len(gradle_command) == 0:
      gradle_command = "gradle"

    proc_env = os.environ.copy()
    env = {}
    android_home = settings.get("android_home")
    if len(android_home) > 0:
      env['ANDROID_HOME'] = android_home
    proc_env.update(env)
    self.proc = subprocess.Popen([gradle_command] + tasks, stdout=subprocess.PIPE,
      stderr=subprocess.PIPE, startupinfo=startupinfo, cwd=cwd, env=proc_env, shell=False)

    if self.proc.stdout:
      threading.Thread(target=self.read_stdout).start()

    if self.proc.stderr:
      threading.Thread(target=self.read_stderr).start()

  def kill(self):
    if self.proc:
      self.proc.kill()
      self.proc = None
    self.listener = None

  def read_stdout(self):
    while self.proc.poll() is None:
      data = os.read(self.proc.stdout.fileno(), 2**15)
      if data != "":
        if self.listener:
          self.listener.on_data(self, data)
        else:
          self.proc.stdout.close()
          if self.listener:
            self.listener.on_finished(self)
          break

  def read_stderr(self):
    while self.proc.poll() is None:
      data = os.read(self.proc.stderr.fileno(), 2**15)
      if data != "":
        if self.listener:
          self.listener.on_data(self, data)
      else:
        self.proc.stderr.close()
        break

'''
Adapted from Default/exec.py with specific modifications
for the gradle process.
'''
class GradleProcessListener(object):
  def on_data(self, proc, data):
    pass

  def on_finished(self, proc):
    pass

class GradleCommand(sublime_plugin.WindowCommand, GradleProcessListener):
  GRADLE_STATUS_ID = "_gradle";

  output_view = None

  def run(self, tasks, props = None):
    if self.window.active_view():
      self.window.active_view().erase_status(self.GRADLE_STATUS_ID)

    self.tasks = tasks
    self.proc = None
    self.init()
    self.build_path = self.current_path()

    if len(tasks) == 0:
      self.window.show_input_panel('gradle', 'tasks', self.on_done, None, None)
    else:
      self.on_done(' '.join(tasks))

  def init(self):
    if not self.output_view:
      # Try not to call get_output_panel until the regexes are assigned
      self.output_view = self.window.get_output_panel("_gradle")
    self.output_view.run_command('erase_view')
    # self.output_view.set_syntax_file('Packages/Gradle/GradleOutputLog.tmLanguage')

  def output(self, text):
    self.output_view.run_command('append', {'characters': text})

  def finish(self, proc):
    self.output("[Finished]")
    self.proc.kill()

  def on_done(self, text):
    self.window.run_command("show_panel", {"panel": "output._gradle"})

    self.proc = AsyncGradleProcess(self, text.split(), self.build_path)

  def on_data(self, proc, data):
    sublime.set_timeout(functools.partial(self.append_data, proc, data), 0)

  def on_finished(self, proc):
    sublime.set_timeout(functools.partial(self.finish, proc), 0)

  def append_data(self, proc, data):
    if proc != self.proc:
      # a second call to exec has been made before the first one
      # finished, ignore it instead of intermingling the output.
      if proc:
        proc.kill()
      return

    try:
      str = data.decode("utf-8")
    except:
      str = "[Decode error - output not utf-8]"
      proc = None

    # Normalize newlines, Sublime Text always uses a single \n separator
    # in memory.
    str = str.replace('\r\n', '\n').replace('\r', '\n')
    self.output_view.set_read_only(False)
    self.output(str)
    self.output_view.set_read_only(True)
    self.output_view.show(self.output_view.size())

  '''
  Follows the google3 hierarchical directory structure to find the closest BUILD
  file to current open file. Returns the directory containing the BUILD file.
  '''
  def current_path(self):
    current_file = self.window.active_view().file_name()
    return os.path.dirname(current_file)
