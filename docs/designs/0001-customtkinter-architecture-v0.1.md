---
status: active  
date: 2026-06-06
---
<!-- docs/designs/0001-customtkinter-architecture-v0.1.md -->
<!-- SPDX-FileCopyrightText: Copyright (C) 2026 Sebastien Lenard <sebastien.lenard@gmail.com> and Contributors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# 0001: CustomTkinter Architecture v0.1

### Architecture Overview

The desktop wrapper for CiteCraft uses a Model-View-Controller (MVC) style separation of concerns. This ensures the visual interface can be developed, styled, and unit-tested across multiple operating systems without mutating or tightly coupling with the underlying CLI and processing core.

```
                  ┌────────────────────────────────────────┐
                  │                 Window                 │
                  │   (CustomTkinter Application Engine)   │
                  └───────────────────┬────────────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           ▼                                                     ▼
┌──────────────────────────────────────┐             ┌──────────────────────┐
│                 View                 │             │      Controller      │
│  • CTk Frame Layouts                 │             │  • Event Listeners   │
│  • CTk Inputs, Entries, FilePickers  │ ◄────────── │  • Pipeline Runner   │
│  • CTk Log Console Textbox           │             │  • Thread Dispatcher │
└──────────────────────────────────────┘             └──────────┬───────────┘
                                                                │
                                                                ▼
                                                     ┌──────────────────────┐
                                                     │     Logging/I/O      │
                                                     │      Redirector      │
                                                     └──────────┬───────────┘
                                                                │
                                                                ▼
                                                     ┌──────────────────────┐
                                                     │    CiteCraft Core    │
                                                     │  (Pipeline/Services) │
                                                     └──────────────────────┘
```

#### Core Components
1. **The View (`CiteCraftApp`):** Direct subclass of `ctk.CTk`. It instantiates layout frames (`CTkFrame`, `CTkScrollableFrame`), UI typography (`CTkFont`), and input components. No business logic lives in this class.
2. **The Controller / Event Layer:** Glues user inputs (e.g., button clicks, entry validations) to execution states. Translates configuration values to `PipelineOptions`.
3. **The I/O and Log Redirector:** A custom thread-safe logging handler and stream proxy that redirects standard output and logger messages to the custom `CTkTextbox` console widget using Tkinter's safe `.after()` synchronization.
4. **Execution Sandbox:** Runs the synchronous processing logic in a secondary background thread to prevent GUI lockups on long-running network queries.

#### Cross-Platform Testing Strategy
UI unit testing across Windows, Ubuntu, and macOS will bypass full window loops. By instantiating widgets in headlessly mocked configurations or using platform-agnostic testing setups (e.g., standard OS loop avoidance), tests can programmatically trigger callbacks and inspect the layout elements without triggering OS-level graphic driver hangs.

---

### Step-by-Step Implementation Plan

To prevent unexpected failures, the interface layout design is strictly decoupled from functional execution. We progress from high-level visual scaffolding to interactive properties, then to backend integration, and finally to testing verification.

```
┌────────────────────────────────────────────────────────┐
│ Visual Layout Scaffolding                              │ (Steps 1–3)
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ UI State and Event Layer                               │ (Steps 4–7)
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Threading, Output Redirection, & Integration          │ (Steps 8–10)
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ Cross-Platform Test Suite                              │ (Step 11)
└────────────────────────────────────────────────────────┘
```

#### Phase 1: Visual Layout Scaffolding
* **Step 1: Application Window Scaffolding**
  * Instantiate the root class `CiteCraftApp(ctk.CTk)`.
  * Set up title, default window dimensions, grid configuration (`columnconfigure`, `rowconfigure`), and standard ctk theme options.
  * *Constraint:* Avoid legacy geometry-management parameters. Use flat, explicit modern grid margins.
* **Step 2: Input Selection Layout**
  * Implement the sidebar configuration frame.
  * Add static layout components for API type selection (`CTkComboBox`), journal title input (`CTkEntry`), reference style input (`CTkEntry`), and boolean logic skips (`CTkSwitch`).
  * *Constraint:* Hardcode input labels and static text; do not write active state handling.
* **Step 3: Document IO & Log Console Layout**
  * Implement file paths display fields and placeholder buttons for Manuscript Input File and Output CSV File.
  * Add a read-only `CTkTextbox` block to represent the mock system console terminal on the right.
  * *Constraint:* Render layout structures cleanly across varied window sizes. No button event handlers.

#### Phase 2: UI State and Event Layer
* **Step 4: Local State Isolation**
  * Define a clean configuration holder class (`UIState`) or standard dynamic properties to store paths and parameters.
  * Bind hardcoded values into input variables so the application loads with stable default parameters on startup.
* **Step 5: File Dialog Pickers**
  * Bind standard path pickers to the File selection buttons.
  * *Step 5.1:* Build visual pickers that display temporary log prompts.
  * *Step 5.2:* Store and update chosen file paths inside the localized state holder, reflecting the change dynamically on the UI labels.
* **Step 6: Input Parameter Serialization**
  * Implement a converter function that inspects the current visual elements (`CTkEntry` values, `CTkComboBox` options, `CTkSwitch` states) and outputs a valid CLI-compatible parameters dictionary.
  * Highlight invalid states in the UI (e.g., empty style configurations).
* **Step 7: Event Action Hooks**
  * Create a single "Run Pipeline" button with visual feedback mechanisms (disabled states, custom highlight color changes).
  * Separate the button's layout configurations from its action execution logic.

#### Phase 3: Threading, Output Redirection, & Integration
* **Step 8: Console and Logger Redirection**
  * Develop a custom thread-safe `TextRedirector` implementing a stream interface (`write`, `flush`) that pushes stdout and stderr directly to the `CTkTextbox` console using the GUI thread's `.after()` queue.
  * Configure a standard python logging `Handler` pointing to this redirector class.
* **Step 9: Background Pipeline Execution**
  * Implement a standard worker queue to launch the processing runner in a separate thread.
  * Ensure user interactions are safely disabled or blocked during runtime execution, restoring active controls on task finalization.
* **Step 10: Progress Bar Interceptor**
  * Adapt `ProgressBarContext` to trigger callback events within CustomTkinter's GUI event loop, feeding real-time progression statistics directly to a modern `CTkProgressBar`.

#### Phase 4: Cross-Platform Testing
* **Step 11: Headless Automated Tests**
  * Write `pytest` unit tests targeting platform stability.
  * Standardize testing setups to mock the root event loops (`update`, `update_idletasks`) so execution runs seamlessly on headless CI/CD systems across Linux, macOS, and Windows.

---

### Step-by-Step Testing

Implementing and executing unit tests at the conclusion of each individual step is
highly recommended. 

By testing incrementally, we isolate layout construction, event bindings, state
changes, and threading. This prevents layout bugs from masking themselves as threading
issues, or vice-versa. 

Each subsequent step will include:
*   The production code adjustments.
*   A dedicated `pytest` suite validating the behavior introduced in that step.
*   Headless-friendly test execution assertions that do not require an active display
    server (vital for GitHub Actions / CI environments).

---

### Execution Mechanisms on VS Code Windows PowerShell

To verify the visual output during development on Windows with PowerShell, use the
following methods:

#### Method A: Direct Module Invocation (Recommended)
Run the UI module directly from your workspace root. Ensure your virtual environment is
active:

```powershell
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"
python -m citecraft.ui.app
```
```
uv run python -m citecraft.ui
```

#### Method B: CLI Integration Flag
If we bind the UI execution directly to the existing Click entry point (e.g., running
`citecraft` without arguments or with a `--gui` flag), you can test via the local development installation:

```powershell
pip install -e .
citecraft --gui
```

#### Method C: Fast Isolation Script
For quick structural testing of isolated components (like checking custom buttons or the console text box layout), you can execute the target file directly:

```powershell
uv run python src/citecraft/ui/components/sidebar.py
```
*(This is supported by adding a conditional `if __name__ == "__main__":` layout block at the bottom of individual component files during drafting).*