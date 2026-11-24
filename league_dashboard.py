"""Second entry point for the same dashboard.

Streamlit Community Cloud allows only one app per repo + branch + main file, so
apps for other leagues use this file as their main file and set their own
LEAGUE_ID secret. Everything else comes from fpl_dashboard.py.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("fpl_dashboard.py")), run_name="__main__")
