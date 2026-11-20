"""3Blue1Brown-style GIFs that show how to set up the project, on Windows and on Mac.

    python docs/animations/setup_gifs.py            # both GIFs
    python docs/animations/setup_gifs.py windows    # only Windows
    python docs/animations/setup_gifs.py mac        # only Mac

Needs Manim CE, LaTeX and FFmpeg. Output: docs/images/setup/setup-windows.gif and
setup-mac.gif. The commands on screen must match setup.ps1, setup.sh and the README.
"""
import subprocess
import sys
from pathlib import Path

from manim import (
    DOWN, LEFT, UP, RIGHT, WHITE, AddTextLetterByLetter, Circle, FadeIn, FadeOut,
    Rectangle, RoundedRectangle, Text, VGroup,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_gifs import BLUE, GREEN, GREY, RED, TEAL, YELLOW, MONO, TaskScene  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "setup"

REPO_URL = "https://github.com/aerlab-deanza/Arm_Robot_Sorting_Machine.git"
TEXT = "#D8D8D8"
FONT_SIZE = 17
LINE_HEIGHT = 0.34
CENTER_Y = 0.35
WIDTH, HEIGHT = 12.6, 5.5


class SetupScene(TaskScene):
    """A fake terminal that types the real setup commands. Subclasses fill in the commands."""

    # Overridden by Windows / Mac.
    title = ""
    window_color = "#0C0C0C"
    bar_color = "#2B2B2B"
    prompt_color = YELLOW
    start_prompt = ""
    folder_prompt = ""
    venv_prompt = ""

    def setup(self):
        super().setup()
        self.caption = None
        self.lines = VGroup()
        self.cursor_y = 0.0
        self.prompt = self.start_prompt
        self.build_window()

    # ------------------------------------------------------------ window

    def build_window(self):
        self.window = Rectangle(width=WIDTH, height=HEIGHT, stroke_color=GREY, stroke_width=2)
        self.window.set_fill(self.window_color, 1).move_to([0, CENTER_Y, 0])
        self.top = self.window.get_top()[1]
        self.left = self.window.get_left()[0] + 0.3
        self.bar = Rectangle(width=WIDTH, height=0.42, stroke_width=0).set_fill(self.bar_color, 1)
        self.bar.align_to(self.window, UP).align_to(self.window, LEFT)
        self.add(self.window, self.bar)
        self.decorate_bar()
        self.cursor_y = self.top - 0.42 - 0.35

    def decorate_bar(self):
        raise NotImplementedError

    # ------------------------------------------------------------ lines

    def mono(self, text, color=TEXT):
        return Text(text, font=MONO, font_size=FONT_SIZE, color=color)

    def place(self, mob):
        mob.shift(RIGHT * (self.left - mob.get_left()[0]))
        mob.set_y(self.cursor_y)
        self.cursor_y -= LINE_HEIGHT
        self.lines.add(mob)

    def clear_screen(self):
        if len(self.lines):
            self.play(FadeOut(self.lines), run_time=0.3)
        self.lines = VGroup()
        self.cursor_y = self.top - 0.42 - 0.35

    def type_command(self, command, prompt=None):
        """Show the prompt, then type the command one letter at a time."""
        prompt_text = self.mono(prompt if prompt is not None else self.prompt, self.prompt_color)
        cmd = self.mono(command)
        row = VGroup(prompt_text, cmd).arrange(RIGHT, buff=0.14, aligned_edge=DOWN)
        if row.width > WIDTH - 0.6:
            row.scale_to_fit_width(WIDTH - 0.6)
        self.place(row)
        self.add(prompt_text)
        self.play(AddTextLetterByLetter(cmd, time_per_char=0.03), run_time=0.03 * len(command) + 0.2)
        self.wait(0.4)

    def show_prompt(self):
        """An empty prompt line, as the terminal shows after a command ends."""
        row = self.mono(self.prompt, self.prompt_color)
        self.place(row)
        self.play(FadeIn(row), run_time=0.15)

    def output(self, text, color=TEXT, pause=0.25):
        if not text:  # blank line
            self.cursor_y -= LINE_HEIGHT
            return
        line = self.mono(text, color)
        self.place(line)
        self.play(FadeIn(line, shift=UP * 0.05), run_time=0.15)
        self.wait(pause)

    # ------------------------------------------------------------ captions

    def say(self, markup, *animations, run_time=1.0, hold=None):
        """Faster than the task GIFs: this GIF has many steps."""
        from task_gifs import rich
        text = rich(markup).to_edge(DOWN, buff=0.4)
        swap = [FadeOut(self.caption, shift=UP * 0.15)] if self.caption is not None else []
        self.play(*swap, FadeIn(text, shift=UP * 0.15), run_time=0.4)
        self.caption = text
        if animations:
            self.play(*animations, run_time=run_time)
        self.wait(hold if hold is not None else 0.3 + len(markup.split()) / 5)

    # ------------------------------------------------------------ the story

    def construct(self):
        self.get_the_code()
        self.run_setup()
        self.missing_python()
        self.turn_on_environment()
        self.run_vision()

    def get_the_code(self):
        raise NotImplementedError

    def run_setup(self):
        raise NotImplementedError

    def missing_python(self):
        raise NotImplementedError

    def turn_on_environment(self):
        raise NotImplementedError

    def run_vision(self):
        raise NotImplementedError

    def setup_output(self, python_line, tests=True):
        """The lines the setup script prints (shortened). Same on both systems."""
        self.output("==> Looking for Python 3.10 or newer", TEAL)
        self.output(python_line)
        self.output("==> Making the .venv environment", TEAL)
        self.output("==> Installing packages (needs internet, about 1 minute)", TEAL, pause=1.0)
        self.output("==> Checking the packages", TEAL)
        self.output("OpenCV 5.1.0 | NumPy 2.5.5")
        self.output("==> Running the tests (about 30 seconds)", TEAL, pause=0.8)
        self.output(".................................................  [100%]")
        self.output("==> Looking for cameras (not an error if none is found)", TEAL)
        self.output("Camera index found: [0]")
        self.output("")
        self.output("Setup done.", GREEN, pause=1.0)


# ---------------------------------------------------------------- Windows

class SetupWindows(SetupScene):
    title = "Set up on Windows"
    start_prompt = "PS C:\\Users\\you>"
    prompt_color = "#E5C07B"

    def setup(self):
        super().setup()
        self.folder_prompt = "PS C:\\Users\\you\\Arm_Robot_Sorting_Machine>"
        self.venv_prompt = "(.venv) PS C:\\Users\\you\\Arm_Robot_Sorting_Machine>"

    def decorate_bar(self):
        name = Text("Windows PowerShell", font_size=16, color=TEXT)
        name.move_to(self.bar.get_left() + RIGHT * 1.4)
        close = Text("X", font_size=16, color=TEXT).move_to(self.bar.get_right() + LEFT * 0.35)
        self.add(name, close)

    def get_the_code(self):
        self.say("**1.** Open __PowerShell__ and download the code", hold=0.5)
        self.type_command(f"git clone {REPO_URL}")
        self.output("Cloning into 'Arm_Robot_Sorting_Machine'...", pause=0.5)
        self.type_command("cd Arm_Robot_Sorting_Machine")
        self.prompt = self.folder_prompt
        self.wait(0.8)

    def run_setup(self):
        self.clear_screen()
        self.say("**2.** Run the setup script. It does everything", hold=0.4)
        self.type_command("powershell -ExecutionPolicy Bypass -File .\\setup.ps1")
        self.setup_output("Found Python 3.13")
        self.say("Wait for ++Setup done++. Takes about 2 minutes", hold=1.0)

    def missing_python(self):
        self.clear_screen()
        self.say("Python missing? The script tells you the fix", hold=0.4)
        self.type_command("powershell -ExecutionPolicy Bypass -File .\\setup.ps1")
        self.output("==> Looking for Python 3.10 or newer", TEAL)
        self.output("ERROR: Python 3.10 or newer was not found.", RED)
        self.output("Install it with:  winget install Python.Python.3.13", YELLOW, pause=0.6)
        self.type_command("winget install Python.Python.3.13")
        self.say("Install it, open a __new__ PowerShell, run the script again", hold=1.6)

    def turn_on_environment(self):
        self.clear_screen()
        self.say("**3.** In every new window, turn the environment **on**", hold=0.4)
        self.type_command(".\\.venv\\Scripts\\Activate.ps1")
        self.prompt = self.venv_prompt
        self.show_prompt()
        self.say("**(.venv)** at the start of the line means it is on", hold=1.6)

    def run_vision(self):
        self.clear_screen()
        self.say("**4.** Run the vision code", hold=0.4)
        self.type_command("python vision/tray_object_pipeline.py --camera-index 0")
        self.say("Windows open with the tray and caps. Press **q** to stop", hold=2.4)


# ---------------------------------------------------------------- Mac

class SetupMac(SetupScene):
    title = "Set up on Mac"
    window_color = "#1E1E1E"
    bar_color = "#3A3A3A"
    prompt_color = "#9AD17A"
    start_prompt = "you@Mac ~ %"

    def setup(self):
        super().setup()
        self.folder_prompt = "you@Mac Arm_Robot_Sorting_Machine %"
        self.venv_prompt = "(.venv) you@Mac Arm_Robot_Sorting_Machine %"

    def decorate_bar(self):
        dots = VGroup(*(Circle(0.075, stroke_width=0).set_fill(c, 1)
                        for c in ("#FF5F57", "#FEBC2E", "#28C840"))).arrange(RIGHT, buff=0.12)
        dots.move_to(self.bar.get_left() + RIGHT * 0.6)
        name = Text("Terminal", font_size=16, color=TEXT).move_to(self.bar)
        self.add(dots, name)

    def get_the_code(self):
        self.say("**1.** Open __Terminal__ and download the code", hold=0.5)
        self.type_command(f"git clone {REPO_URL}")
        self.output("Cloning into 'Arm_Robot_Sorting_Machine'...", pause=0.5)
        self.type_command("cd Arm_Robot_Sorting_Machine")
        self.prompt = self.folder_prompt
        self.wait(0.8)

    def run_setup(self):
        self.clear_screen()
        self.say("**2.** Run the setup script. It does everything", hold=0.4)
        self.type_command("bash setup.sh")
        self.setup_output("Found Python 3.13.0")
        self.say("Wait for ++Setup done++. Takes about 2 minutes", hold=1.0)

    def missing_python(self):
        self.clear_screen()
        self.say("Python missing? The script tells you the fix", hold=0.4)
        self.type_command("bash setup.sh")
        self.output("==> Looking for Python 3.10 or newer", TEAL)
        self.output("ERROR: Python 3.10 or newer was not found.", RED)
        self.output("Install it with Homebrew:  brew install python@3.13", YELLOW, pause=0.6)
        self.type_command("brew install python@3.13")
        self.say("Install it, open a __new__ Terminal, run the script again", hold=1.6)

    def turn_on_environment(self):
        self.clear_screen()
        self.say("**3.** In every new window, turn the environment **on**", hold=0.4)
        self.type_command("source .venv/bin/activate")
        self.prompt = self.venv_prompt
        self.show_prompt()
        self.say("**(.venv)** at the start of the line means it is on", hold=1.6)

    def run_vision(self):
        self.clear_screen()
        self.say("**4.** Run the vision code", hold=0.4)
        self.type_command("python vision/tray_object_pipeline.py --camera-index 0")
        self.camera_dialog()
        self.say("Windows open with the tray and caps. Press **q** to stop", hold=2.4)

    def camera_dialog(self):
        """macOS asks once to let Terminal use the camera."""
        box = RoundedRectangle(corner_radius=0.15, width=5.4, height=1.7, stroke_color=GREY, stroke_width=2)
        box.set_fill("#2E2E2E", 1).move_to([2.6, -0.6, 0])
        message = Text('"Terminal" would like to access the camera.', font_size=17, color=WHITE)
        message.move_to(box.get_center() + UP * 0.35)
        allow = RoundedRectangle(corner_radius=0.1, width=1.3, height=0.45, stroke_width=0).set_fill(BLUE, 1)
        allow.move_to(box.get_center() + DOWN * 0.45 + RIGHT * 1.3)
        allow_text = Text("Allow", font_size=17, color=WHITE).move_to(allow)
        deny = RoundedRectangle(corner_radius=0.1, width=1.9, height=0.45, stroke_width=0).set_fill("#555555", 1)
        deny.move_to(box.get_center() + DOWN * 0.45 + LEFT * 0.4)
        deny_text = Text("Don't Allow", font_size=17, color=WHITE).move_to(deny)
        group = VGroup(box, message, allow, allow_text, deny, deny_text)
        self.say("First time only: click **Allow** for the camera", FadeIn(group, shift=UP * 0.1), hold=2.0)
        self.play(FadeOut(group), run_time=0.3)


SCENES = {"windows": SetupWindows, "mac": SetupMac}


def render(key, width=800, fps=12):
    scene = SCENES[key].__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    OUT.mkdir(parents=True, exist_ok=True)
    gif = OUT / f"setup-{key}.gif"
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(gif)], check=True)
    print(f"{gif}  {gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    for key in sys.argv[1:] or SCENES:
        render(key)
