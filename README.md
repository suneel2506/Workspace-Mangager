<<<<<<< HEAD
# 🖥️ Workspace Manager

> **Launch predefined workspaces with one command or a voice command.**
>
> Say *"Open coding workspace"* and watch VS Code, ChatGPT, and GitHub spring to life — automatically.

---

## ✨ Features

| Feature              | Description                                          |
|----------------------|------------------------------------------------------|
| **CLI Launch**       | `python main.py coding` launches everything at once  |
| **Interactive Menu** | Numbered menu when no arguments are given            |
| **Voice Commands**   | Say "Open coding workspace" hands-free               |
| **Structured Logs**  | Every launch is timestamped in `logs.txt`             |
| **Modular Design**   | Easy to extend with GUI, scheduling, AI, and more    |

---

## 📁 Project Structure

```
WorkspaceManager/
│
├── main.py                  # Entry point — CLI, menu, voice
├── workspaces.json          # Workspace definitions
├── logs.txt                 # Auto-generated launch log
├── requirements.txt         # Python dependencies
├── README.md                # This file
│
├── core/
│   ├── __init__.py
│   ├── launcher.py          # Opens apps & URLs
│   ├── workspace_manager.py # Loads & queries workspaces.json
│   └── logger.py            # Writes logs.txt
│
├── voice/
│   ├── __init__.py
│   └── speech.py            # Microphone → text → workspace match
│
└── utils/
    ├── __init__.py
    └── helpers.py            # Colors, banners, formatting
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.12+** (tested on 3.12, 3.13, 3.14) — [Download](https://www.python.org/downloads/)
- **pip** — comes with Python

### Step 1 — Clone / Download

```bash
cd "C:\Users\sk600\Documents\WorkSpace Automation\WorkspaceManager"
```

### Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `SpeechRecognition`, `sounddevice`, and `scipy` are only needed
> for voice mode.  If you just want CLI + menu mode, you can skip this step.

---

## 🎮 Usage

### 1. Interactive Menu

```bash
python main.py
```

Output:

```
════════════════════════════════════════
            Workspace Manager
════════════════════════════════════════

  1. Coding
  2. College
  3. Embedded
  4. Hackathon
  5. VLSI
  6. 🎤 Voice Mode
  7. ❌ Exit

  Select an option:
```

### 2. Launch by Name (CLI)

```bash
python main.py coding
```

Output:

```
  ℹ  Launching workspace: Coding
  ────────────────────────────────────────
  ✔  Launched: VS Code
  ✔  Launched: ChatGPT
  ✔  Launched: GitHub
  ────────────────────────────────────────
  ✔  Workspace 'Coding' launched successfully!
```

### 3. Voice Mode

```bash
python main.py --voice
```

Say: **"Open coding workspace"**

Output:

```
  🎤  Listening… Say something like: 'Open coding workspace'
  …  Adjusted for ambient noise. Speak now!

  📝  You said: "open coding workspace"
  ✔  Matched workspace: coding

  ℹ  Launching workspace: Coding
  ────────────────────────────────────────
  ✔  Launched: VS Code
  ✔  Launched: ChatGPT
  ✔  Launched: GitHub
  ────────────────────────────────────────
  ✔  Workspace 'Coding' launched successfully!
```

### 4. List Workspaces

```bash
python main.py --list
```

### 5. Help

```bash
python main.py --help
```

---

## ⚙️ Configuration

Edit `workspaces.json` to add your own workspaces:

```json
{
  "research": [
    {
      "type": "app",
      "path": "C:\\Program Files\\Zotero\\zotero.exe",
      "name": "Zotero"
    },
    {
      "type": "url",
      "value": "https://scholar.google.com",
      "name": "Google Scholar"
    }
  ]
}
```

### Item Types

| Key      | Type  | Required | Description                              |
|----------|-------|----------|------------------------------------------|
| `type`   | `str` | ✅       | `"app"` or `"url"`                       |
| `path`   | `str` | apps     | Command name or full path to `.exe`      |
| `value`  | `str` | urls     | The URL to open                          |
| `name`   | `str` | ❌       | Display name (used in logs and messages) |

### App Path Tips

| App          | Path / Command                                       |
|--------------|------------------------------------------------------|
| VS Code      | `code`                                               |
| Notepad++    | `notepad++`                                          |
| Chrome       | `"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"` |
| File Explorer| `explorer`                                           |
| Terminal     | `wt` (Windows Terminal)                              |

---

## 📝 Logs

Every launch is recorded in `logs.txt`:

```
[2026-06-20 10:30:15]
Workspace: coding
Items:     VS Code, ChatGPT, GitHub
Status:    Success
──────────────────────────────

[2026-06-20 10:35:42]
Workspace: vlsi
Items:     Nandland, HDLBits
Status:    Success
──────────────────────────────
```

---

## 🎤 Voice Setup Guide

### Requirements

1. **A working microphone** connected to your computer.
2. **Internet connection** -- Google Web Speech API is used.
3. **SpeechRecognition**, **sounddevice**, and **scipy** installed.

### Supported Commands

| You say…                        | Workspace launched |
|---------------------------------|--------------------|
| "Open coding workspace"        | coding             |
| "Launch embedded"              | embedded           |
| "Start vlsi workspace"         | vlsi               |
| "Open college"                 | college            |
| "Run hackathon workspace"      | hackathon          |

### Tips

- Speak clearly and at a normal pace.
- Wait for the "Speak now!" prompt before talking.
- If it doesn't match, it will show what it heard — check for typos.
- Quiet environments work best.

---

## 🛠️ Error Handling

| Scenario                      | What Happens                                      |
|-------------------------------|---------------------------------------------------|
| `workspaces.json` missing     | Clear error message with instructions              |
| Invalid JSON syntax           | Python's JSON parser error is shown                |
| Workspace not found           | Lists available workspaces                         |
| App not found on PATH         | Logs the error; other items still launch           |
| No microphone                 | Graceful message asking to connect one             |
| Speech not understood         | Asks to try again                                  |
| No internet (voice)           | Google API error is shown                          |
| Microphone permission denied  | Clear message pointing to OS privacy settings      |
| Voice deps not installed      | App works fine without them (CLI + menu still work)|

---

## 🔮 Future Expansion Roadmap

The architecture is designed so you can add these features without restructuring:

| Feature                      | Where to Add                            |
|------------------------------|-----------------------------------------|
| GUI (CustomTkinter)          | New `gui/` package; import launcher     |
| AI workspace recommendations | New `ai/` package; analyze usage logs   |
| Startup automation           | Register with Windows Task Scheduler    |
| Save current workspace       | Snapshot open apps → write to JSON      |
| Close workspace              | Track PIDs in launcher; add kill method |
| Schedule workspace launch    | `--schedule` flag; use `sched` module   |
| Focus mode                   | Close non-workspace apps before launch  |

---

## 📄 License

This project is open source. Use it however you like.
=======
# Workspace-Mangager
Create the workspace when needed.
>>>>>>> b8a17b4127f702b316ca267cb0f02ad0f80e83b6
