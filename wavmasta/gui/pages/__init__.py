"""One module per page (one tab each in the top bar)."""

from .help import HelpPage
from .history import HistoryPage
from .master import MasterPage
from .settings import SettingsPage

# (key, tab label, page title, page subtitle)
PAGES = [
    ("master", "Master", "Master", "Add your songs, pick a sound, hear before and after, then master"),
    ("history", "History", "History", "What Check, Before/After and Master did, newest first"),
    ("settings", "Settings", "Settings", "Where masters are saved, the file format and the peak ceiling"),
    ("help", "Help", "Help", "How to get the best results from WavMasta"),
]

__all__ = ["PAGES", "HelpPage", "HistoryPage", "MasterPage", "SettingsPage"]
