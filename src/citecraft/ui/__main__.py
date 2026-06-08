# src/citecraft/ui/__main__.py
"""Main runtime entrypoint for the UI package interface."""

from citecraft.ui.app import CiteCraftApp

if __name__ == "__main__":
    app = CiteCraftApp()
    app.mainloop()
