"""Record a short tour of the repo docs on GitHub, for the README GIF.

Needs Playwright (`pip install playwright`, then `playwright install chromium`)
and FFmpeg. Records the live GitHub pages, so push doc changes first.

    python docs/animations/record_docs_tour.py docs_tour.webm
    ffmpeg -i docs_tour.webm -filter_complex "setpts=PTS/1.6,fps=5,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" docs/images/docs-tour.gif
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
REPO = "https://github.com/aerlab-deanza/Arm_Robot_Sorting_Machine"

CAPTION_JS = """
(text) => {
  let el = document.getElementById('tour-caption');
  if (!el) {
    el = document.createElement('div');
    el.id = 'tour-caption';
    el.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);'
      + 'z-index:99999;background:rgba(13,17,23,0.92);color:#fff;'
      + 'font:600 26px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
      + 'padding:14px 26px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.35);'
      + 'max-width:90%;text-align:center;';
    document.body.appendChild(el);
  }
  el.textContent = text;
}
"""

HIDE_JS = """
() => {
  for (const sel of ['.js-notification-shelf', '.flash-full', 'react-app[app-name="signup-prompt"]',
                     '.signup-prompt-bg', '#cookie-consent-banner', '.cookie-consent-banner']) {
    document.querySelectorAll(sel).forEach(e => e.style.display = 'none');
  }
}
"""


def settle(page):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)  # GitHub re-draws the page after loading
    page.evaluate(HIDE_JS)


def center_on(locator, tries=5):
    for _ in range(tries):
        try:
            locator.evaluate("e => e.scrollIntoView({block: 'center'})")
            return
        except Exception:
            locator.page.wait_for_timeout(500)
    raise RuntimeError("could not scroll to element")


def caption(page, text):
    page.evaluate(CAPTION_JS, text)


def scroll(page, total, steps=40, pause=60):
    for _ in range(steps):
        page.mouse.wheel(0, total / steps)
        page.wait_for_timeout(pause)


def highlight(page, link):
    link.evaluate("e => { e.style.outline = '4px solid #f2c94c'; e.style.outlineOffset = '3px';"
                  " e.style.borderRadius = '4px'; }")


def open_doc(page, link_text, title):
    link = page.locator("article").get_by_role("link", name=link_text).first
    center_on(link)
    highlight(page, link)
    caption(page, "Click " + title)
    page.wait_for_timeout(1300)
    link.click()
    settle(page)


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1280, "height": 760},
        record_video_dir=str(OUT.parent),
        record_video_size={"width": 1280, "height": 760},
    )
    page = context.new_page()
    page.goto(REPO)
    settle(page)

    # 1. README: point to the Documents list.
    links = page.locator("article ul").first
    center_on(links)
    page.wait_for_timeout(400)
    highlight(page, links)
    caption(page, "The README links to guides in the docs folder")
    page.wait_for_timeout(2600)

    # 2. Current pipeline: animations + text for each step.
    open_doc(page, "Current pipeline", "“Current pipeline”")
    caption(page, "Each step has an animation and a short explanation")
    page.wait_for_timeout(800)
    scroll(page, 1500, steps=8, pause=30)
    page.wait_for_timeout(2600)
    scroll(page, 1300, steps=8, pause=30)
    page.wait_for_timeout(2400)

    # 3. Pipeline limits: problem / fix animations.
    page.go_back()
    settle(page)
    open_doc(page, "Pipeline limits", "“Pipeline limits”")
    caption(page, "What's missing, with a problem and fix animation")
    page.wait_for_timeout(600)
    scroll(page, 1500, steps=8, pause=30)
    page.wait_for_timeout(2800)

    # 4. Task delegation: what each person builds.
    page.go_back()
    settle(page)
    open_doc(page, "Task Delegation", "“Task Delegation”")
    caption(page, "Team tasks, each with an animated walkthrough")
    page.wait_for_timeout(600)
    gif = page.locator('article img[alt^="Task 1"]').first
    gif.evaluate("e => e.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(4500)
    caption(page, "Start here: README → Documents")
    page.wait_for_timeout(2000)

    video = page.video
    context.close()
    browser.close()
    Path(video.path()).replace(OUT)
    print("saved", OUT)
