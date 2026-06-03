# Contributing to CiteCraft 🎓

 <img src="citecraft_logo_64.png" alt="CiteCraft automated bibliography generator logo" align="left" width="64" height="72" style="margin-right: 15px; margin-bottom: 10px;"> Thank you so much for stopping by! CiteCraft is built to save researchers, scientists, and students from the headache of manual citation formatting, and we are incredibly grateful for your time, energy, and ideas. Every contribution helps make the academic workflow a little smoother for everyone.

---

## How to Get Involved

### 1. Reporting Issues

* If something isn't parsing correctly or an API call goes sideways, please let us know by opening an issue!
* To help us fix it quickly, please use our **Issue Templates** rather than opening a blank issue, and include a small snippet of the text or the journal title that caused the problem.

### 2. Suggesting Enhancements

* Have an idea for a smarter metadata fallback, a CLI quality-of-life tweak, or a new feature? Open a **Feature Request** or kick off a thread in our **Discussions** tab. We love talking through new concepts!

### 3. Submitting Code (Pull Requests)

If you are looking to dive into the codebase and fix a bug or build a feature, you are incredibly welcome here! To make sure your hard work integrates smoothly, we just ask that you follow a few guidelines:

* **Let’s Chat First:** For anything beyond a quick typo fix, please open an issue to discuss your planned approach before writing a large patch. This saves you from accidental duplicate work!
* **Keep it Focused:** Try to keep your Pull Requests focused on a single bug fix or feature. It makes reviewing a breeze and gets your code merged much faster.
* **Write Tests:** CiteCraft relies heavily on its test suite to keep the data pipeline stable. Please include matching unit or integration tests for your changes using our `pytest` markers.

---

## Code Quality & Python Guidelines

We take a lot of pride in keeping the CiteCraft codebase clean, efficient, and maintainable. If you're submitting code, here are a few gentle guidelines and modern Python practices we try to stick to:

### 🐍 Use Modern Python 3.12+ Syntax

We love leveraging the latest features of the language to keep our code expressive and clean. Where applicable, please make use of:

* **Advanced Type Hinting:** Fully type your function signatures and data structures.
* **Syntactic Improvements:** Utilize modern generics syntax, definitive `isinstace` checks, and clear `f-strings`.

### 🛡️ Be Specific with Exceptions

To prevent silent failures and keep our debugging logs informative, we avoid catching broad, generic exceptions.

* **Do:** Wrap network calls or file parsing in targeted blocks, catching exact errors like `KeyError`, `ValueError`, or HTTP-specific exceptions.
* **Don't:** Use a blanket `except Exception:` unless you are explicitly logging and re-raising it at the absolute top level of the application.

```python
# Preferred approach 
try:
    journal_issn = payload["message"]["issn"][0]
except (KeyError, IndexError):
    logger.debug("ISSN missing or malformed in response payload.")
    # Handle the incomplete state safely

```

### 🔁 Safe Loop Control

Infinite loops (`while True:`) can easily lock up a data pipeline if a remote API drops a connection or a parsing boundary is missed.

* Please ensure all loops have explicit, deterministic exit conditions, maximum retry counts, or timeout bounds so the application always fails safely and gracefully.

### 💡 Readability Over Cleverness

As a rule of thumb, we prioritize code that is easy to read and reason about over hyper-optimized, single-line "clever" tricks. Clear variable names, modular functions, and helpful docstrings go a long way in keeping the project accessible to developers and scientists alike.

---

Thank you for being a part of the open-science community and helping us build CiteCraft! 👋