import sublime, sublime_plugin
import os
import os.path
import subprocess
import sys
import threading

class GradleView(object):
  def __init__(self, cmd, working_dir, view, env):
    self.__cmd = cmd
    self.__view = view
    self.__view.set_read_only(True)
    self.__view.set_syntax_file("Packages/SublimeGradle/GradleOutputLog.tmLanguage")
    print("running: %s" % cmd)
    info = None
    if os.name == 'nt':
      info = subprocess.STARTUPINFO()
      info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    self.__process = subprocess.Popen(cmd, startupinfo=info,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=working_dir, env=env, shell=False, close_fds=True)
    threading.Thread(target=self.__output_thread,
        args=(self.__process.stdout, self.__finish)).start()
    threading.Thread(target=self.__output_thread, args=(self.__process.stderr,)).start()

  def process_lines(self, lines):
    self.__view.set_read_only(False)
    for line in lines.split("\r\n"):
      line = line.strip()
      if len(line) > 0:
        self.__view.run_command('append', {'characters': "%s\n" % line})
    self.__view.set_read_only(True)
    self.__view.show(self.__view.size())

  def close(self):
    if self.__process != None and self.__process.poll() is None:
      self.__process.kill()

  @property
  def view(self):
      return self.__view

  def __finish(self):
    self.add_line("[Finished]")

  def __output_thread(self, pipe, on_finish=None):
    def decode(ind):
      try:
        return ind.decode(sys.getdefaultencoding())
      except:
        return ind

    while self.__process.poll() is None:
      data = decode(os.read(pipe.fileno(), 2**15))
      if len(data) > 0:
        self.process_lines(data)
    if on_finish:
      sublime.set_timeout(on_finish, 0)

class GradleCommand(sublime_plugin.WindowCommand):
  def run(self, tasks):
    cwd = self.current_path()
    if len(tasks) == 0:
      self.window.show_input_panel("gradle", "tasks", self.on_done, None, None)
    else:
      self.launch(tasks)

  def launch(self, tasks):
    working_dir = self.current_path()
    env = os.environ.copy()
    settings = sublime.load_settings('SublimeGradle.sublime-settings')
    gradle_cmd = settings.get("gradle_command")
    if len(gradle_cmd) == 0:
      gradle_cmd = "gradle"
    android_home = settings.get("android_home")
    if len(android_home) > 0:
      env["ANDROID_HOME"] = android_home
    cmd = [gradle_cmd] + tasks
    GradleView(cmd, working_dir, self.window.get_output_panel("_gradle"), env)
    self.window.run_command("show_panel", {"panel": "output._gradle"})

  def on_done(self, text):
    launch(text.split())

  def current_path(self):
    current_file = self.window.active_view().file_name()
    return os.path.dirname(current_file)