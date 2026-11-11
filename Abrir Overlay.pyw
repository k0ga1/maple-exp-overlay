"""Double-click to open the overlay with no console window (.pyw files run with pythonw)."""
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
sys.path.insert(0, here)
runpy.run_path(os.path.join(here, "maple_exp.py"), run_name="__main__")
