"""Keyboard shortcuts. (Navigation lives in the top bar, so there's no separate menu bar.)"""

from .pages import PAGES


def bind_shortcuts(app):
    root = app.root
    root.bind_all("<Control-o>", lambda e: app.master_page.add_files())
    root.bind_all("<Control-i>", lambda e: app.checker.start())
    root.bind_all("<Control-b>", lambda e: app.preview.start("before"))
    root.bind_all("<Control-p>", lambda e: app.preview.start("after"))
    root.bind_all("<Control-Return>", lambda e: app.masterer.start())
    root.bind_all("<Control-q>", lambda e: app.quit())
    root.bind_all("<Escape>", lambda e: app.preview.stop())
    root.bind_all("<F1>", lambda e: app.show_page("help"))
    for i, (key, *_) in enumerate(PAGES, start=1):
        root.bind_all(f"<Control-Key-{i}>", lambda e, k=key: app.show_page(k))
