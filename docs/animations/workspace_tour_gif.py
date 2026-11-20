"""3Blue1Brown-style GIF: a tour of the folders and files in the workspace (for the README).

    python docs/animations/workspace_tour_gif.py

Needs Manim CE, LaTeX and FFmpeg. Output: docs/images/workspace-tour.gif.
Keep the lists below in step with the folder map in README.md.
"""
import subprocess
import sys
from pathlib import Path

from manim import (
    DOWN, LEFT, RIGHT, UP, Create, FadeIn, FadeOut, Indicate, LaggedStart, Rectangle,
    SurroundingRectangle, Tex, Text, Transform, VGroup,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_gifs import BLUE, GREY, MONO, TEAL, YELLOW, TaskScene, rich  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "images" / "workspace-tour.gif"

# (name, short note, stages). A stage is (caption, files inside as (name, note)).
# Names with "_" go in Text, not Tex. Order matters: docs come before vision.
ENTRIES = [
    ("README.md", "front page", [("**README.md** is the front page. Start here", [])]),
    ("setup.ps1 / setup.sh", "install everything",
     [("Run the setup script **once**: it installs everything",
       [("setup.ps1", "Windows (PowerShell)"), ("setup.sh", "Mac (Terminal)")])]),
    ("requirements.txt", "Python packages",
     [("**requirements.txt** lists the Python packages the code needs", [])]),
    ("docs/", "guides and open tasks",
     [("**docs/** has the guides. Read these before the code",
       [("computer_vision_pipeline.md", "How the pipeline works, step by step"),
        ("documentation.md", "Findings and why we chose this setup"),
        ("task_delegation.md", "The 3 open tasks to do next"),
        ("arm_vision.md", "Arm modeling: research and method")])]),
    ("vision/", "Python code for the PC",
     [("**vision/** is the Python code. Part 1: the **main pipeline** that finds caps",
       [("tray_object_pipeline.py", "Run this. It runs every step"),
        ("camera.py", "Opens the camera"),
        ("tray.py", "Finds and straightens the tray"),
        ("caps.py", "Finds the caps by color")]),
      ("Part 2: **arm modeling**, the arm's shape from a camera",
       [("arm_vision.py", "Finds the arm's backbone curve"),
        ("shape_models.py", "Curve models of the arm")])]),
]


def mono(text, size=20, color="#FFFFFF"):
    return Text(text, font=MONO, font_size=size, color=color)


class WorkspaceTour(TaskScene):
    title = "Tour of the workspace"

    def setup(self):
        super().setup()
        self.caption = None

    def say(self, markup, *animations, run_time=1.0, hold=None):
        text = rich(markup).to_edge(DOWN, buff=0.4)
        swap = [FadeOut(self.caption, shift=UP * 0.15)] if self.caption is not None else []
        self.play(*swap, FadeIn(text, shift=UP * 0.15), run_time=0.4)
        self.caption = text
        if animations:
            self.play(*animations, run_time=run_time)
        self.wait(hold if hold is not None else 0.3 + len(markup.split()) / 5)

    @staticmethod
    def row(name, note):
        """One row of the left list: file name in color, plain note in grey."""
        return VGroup(mono(name, 21, TEAL), Tex(note, font_size=22, color=GREY)).arrange(
            DOWN, aligned_edge=LEFT, buff=0.08)

    @staticmethod
    def inside(files):
        """The right panel: what is inside the selected folder."""
        rows = [VGroup(mono(n, 20, BLUE), Tex(d, font_size=24)).arrange(DOWN, aligned_edge=LEFT, buff=0.07)
                for n, d in files]
        panel = VGroup(*rows).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        return panel.move_to([3.3, 0.3, 0])

    def construct(self):
        rows = VGroup(*(self.row(n, note) for n, note, _ in ENTRIES)).arrange(
            DOWN, aligned_edge=LEFT, buff=0.2)
        rows.move_to([-4.2, 0.2, 0])
        rows.shift(RIGHT * (-6.6 - rows.get_left()[0]))
        divider = Rectangle(width=0.02, height=5.6, stroke_width=0).set_fill(GREY, 0.6).move_to([-0.6, 0.25, 0])

        self.say("Every file and folder, in the order to read them",
                 LaggedStart(*(FadeIn(r, shift=RIGHT * 0.2) for r in rows), lag_ratio=0.12),
                 FadeIn(divider), run_time=1.6, hold=0.6)

        box = SurroundingRectangle(rows[0], color=YELLOW, buff=0.1, stroke_width=3)
        panel = None
        for i, (_, _, stages) in enumerate(ENTRIES):
            target = SurroundingRectangle(rows[i], color=YELLOW, buff=0.1, stroke_width=3)
            move = [Create(box)] if i == 0 else [Transform(box, target)]
            for caption, files in stages:
                drop = [FadeOut(panel)] if panel is not None else []
                panel = self.inside(files) if files else None
                shown = [FadeIn(panel, shift=LEFT * 0.2)] if panel is not None else []
                self.say(caption, *drop, *move, *shown, run_time=0.8,
                         hold=1.0 + 0.55 * len(files))
                move = []  # the box moves only once per row

        if panel is not None:
            self.play(FadeOut(panel), run_time=0.3)
        self.say("New here? **README**, then **setup**, then **docs**",
                 Indicate(rows[0], color=YELLOW), Indicate(rows[1], color=YELLOW),
                 Indicate(rows[3], color=YELLOW), run_time=1.6, hold=1.8)


def render(width=800, fps=12):
    scene = WorkspaceTour.__name__
    media = HERE / "media"
    subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", str(media),
                    "--disable_caching", str(Path(__file__).resolve()), scene], check=True)
    mp4 = next(media.glob(f"videos/**/{scene}.mp4"))
    vf = (f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=64:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", vf, str(OUT)], check=True)
    print(f"{OUT}  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    render()
