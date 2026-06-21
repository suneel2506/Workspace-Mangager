# Workspace Automation System v3.0

A modular, production-style **personal productivity and automation assistant** built with Python.

Combines **Workspace Management**, **Task Management**, **Voice Commands**, **Automation Tools**, and **AI Assistant Features** into a single desktop application.

---

## Features

| Feature | Description |
|---------|-------------|
| **Workspace Management** | Create, delete, rename, open, and list workspaces with associated apps/URLs |
| **Task Management** | Add, delete, complete, update tasks with priorities and due dates |
| **Voice Commands** | Speak commands using Google Speech-to-Text recognition |
| **App Launcher** | Launch Chrome, VS Code, Notepad, Calculator, and more |
| **File Automation** | Create/delete folders, move files, organize Downloads by file type |
| **Browser Automation** | Open URLs, search Google from text or voice |
| **System Control** | Shutdown, restart, lock screen, sleep monitor |
| **GUI Dashboard** | Tkinter dashboard with sidebar navigation and stat cards |
| **AI Assistant** | Future-ready AI integration (local fallback for now) |
| **Command Logging** | All commands logged to SQLite + `logs/app.log` |

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the GUI dashboard (default)
python main.py

# Interactive CLI mode
python main.py --cli

# Voice recognition mode
python main.py --voice

# Execute a single command
python main.py --cmd "create workspace IronForge"
python main.py --cmd "show pending tasks"
python main.py --cmd "launch chrome"
```

---

## Project Structure

```text
WorkspaceManager/
│
├── main.py                     # Entry point: GUI (default), --cli, --voice
│
├── core/
│   ├── __init__.py             # Package exports
│   ├── assistant.py            # Central orchestrator (ties everything together)
│   ├── listener.py             # Microphone capture + Google Speech-to-Text
│   ├── speaker.py              # Text-to-speech output via pyttsx3
│   ├── command_parser.py       # Expandable rule-based command router
│   └── ai_manager.py           # Future AI integration stub
│
├── automations/
│   ├── __init__.py             # Package exports
│   ├── app_launcher.py         # Desktop application launcher
│   ├── browser_tasks.py        # URL opening + Google search
│   ├── file_manager.py         # Filesystem operations + organize downloads
│   └── system_control.py       # Shutdown, restart, lock, sleep
│
├── workspace/
│   ├── __init__.py             # Package exports
│   ├── workspace_manager.py    # Workspace CRUD + open/launch
│   └── task_manager.py         # Task CRUD + filtering + priority
│
├── database/
│   ├── __init__.py             # Package exports
│   ├── db.py                   # SQLite connection, schema, migration, logging
│   └── tasks.db                # Auto-created SQLite database
│
├── gui/
│   ├── __init__.py             # Package exports
│   ├── dashboard.py            # Main window + sidebar + stat cards
│   ├── workspace_page.py       # Workspace CRUD UI
│   └── task_page.py            # Task CRUD UI with filtering
│
├── config/
│   ├── __init__.py
│   └── settings.py             # All configuration constants
│
├── utils/
│   ├── __init__.py
│   └── helpers.py              # CLI display helpers + ANSI colors
│
├── logs/
│   └── app.log                 # Auto-created log file
│
├── assets/                     # Static assets (icons, sounds)
│
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Database Schema

```sql
-- Workspaces
CREATE TABLE workspaces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    path        TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
);

-- Workspace items (apps + URLs attached to workspaces)
CREATE TABLE workspace_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER NOT NULL,
    type          TEXT    NOT NULL CHECK(type IN ('app', 'url')),
    value         TEXT    NOT NULL,
    name          TEXT    DEFAULT '',
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Tasks
CREATE TABLE tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER,
    title         TEXT    NOT NULL,
    description   TEXT    DEFAULT '',
    status        TEXT    DEFAULT 'pending'
                         CHECK(status IN ('pending', 'in_progress', 'completed')),
    priority      TEXT    DEFAULT 'medium'
                         CHECK(priority IN ('low', 'medium', 'high', 'critical')),
    due_date      TEXT    DEFAULT NULL,
    created_at    TEXT    DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
);

-- Command log (recent activity)
CREATE TABLE command_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT    NOT NULL,
    result      TEXT    DEFAULT '',
    timestamp   TEXT    DEFAULT (datetime('now', 'localtime'))
);
```

---

## Class Diagram

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Assistant   │────▶│ CommandParser│────▶│  ParsedCommand   │
│              │     │              │     │  (dataclass)     │
│ process_text │     │ parse()      │     │  intent, args,   │
│ process_voice│     │ register()   │     │  raw_text, conf. │
│ start/stop   │     └──────────────┘     └──────────────────┘
│ voice_loop   │
└──┬───┬───┬───┘
   │   │   │
   ▼   ▼   ▼
┌──────┐ ┌──────┐ ┌──────┐
│Listen│ │Speak │ │AI Mgr│
│er    │ │er    │ │      │
└──────┘ └──────┘ └──────┘
   │
   ▼
┌──────────────────────────────────────────┐
│            Action Layer                   │
├──────────┬────────────┬──────┬───────────┤
│Workspace │   Task     │ App  │  Browser  │
│Manager   │  Manager   │Launch│  Tasks    │
│          │            │er    ├───────────┤
│          │            │      │ File Mgr  │
│          │            │      ├───────────┤
│          │            │      │ Sys Ctrl  │
└────┬─────┴─────┬──────┴──────┴───────────┘
     │           │
     ▼           ▼
┌─────────┐  ┌────────┐
│ SQLite  │  │ OS/Net │
│ (db.py) │  │ APIs   │
└─────────┘  └────────┘
```

---

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point — routes to GUI, CLI, or voice mode |
| `core/assistant.py` | Central orchestrator — ties all subsystems together |
| `core/listener.py` | Records audio via sounddevice, transcribes via Google STT |
| `core/speaker.py` | Text-to-speech output using pyttsx3 |
| `core/command_parser.py` | Rule-based intent matching + argument extraction |
| `core/ai_manager.py` | Future AI integration (OpenAI, Gemini, local models) |
| `workspace/workspace_manager.py` | Workspace CRUD + item management + launch |
| `workspace/task_manager.py` | Task CRUD + status/priority management + filtering |
| `automations/app_launcher.py` | Launch desktop apps by name or path |
| `automations/browser_tasks.py` | Open URLs + Google search |
| `automations/file_manager.py` | Folder CRUD + organize downloads |
| `automations/system_control.py` | Shutdown, restart, lock, sleep (Windows) |
| `database/db.py` | SQLite connection, schema DDL, JSON migration, command log |
| `gui/dashboard.py` | Tkinter main window with sidebar + pages |
| `gui/workspace_page.py` | Tkinter workspace Treeview + item management |
| `gui/task_page.py` | Tkinter task Treeview + filtering + CRUD |
| `config/settings.py` | All configuration: paths, registry, TTS, GUI, commands |
| `utils/helpers.py` | CLI display helpers (banners, colors, formatting) |

---

## Available Commands

| Command | Example |
|---------|---------|
| Create workspace | `"create workspace IronForge"` |
| Open workspace | `"open workspace IronForge"` |
| Delete workspace | `"delete workspace IronForge"` |
| Rename workspace | `"rename workspace OldName to NewName"` |
| List workspaces | `"list workspaces"` |
| Add task | `"add task finish authentication"` |
| Complete task | `"complete task finish authentication"` |
| Delete task | `"delete task old item"` |
| Show tasks | `"show pending tasks"` |
| Launch app | `"launch chrome"`, `"open vscode"` |
| Google search | `"search Python tutorials"` |
| Open URL | `"go to github.com"` |
| Organize downloads | `"organize downloads"` |
| Create folder | `"create folder C:/Projects/new"` |
| Lock screen | `"lock screen"` |
| Shutdown | `"shutdown computer"` |
| Restart | `"restart computer"` |
| Help | `"help"` |

---

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| Python 3.12+ | Core language |
| SQLite | Database (via stdlib `sqlite3`) |
| Tkinter | GUI framework (stdlib) |
| SpeechRecognition | Voice-to-text |
| sounddevice | Microphone audio capture |
| scipy | WAV file I/O |
| pyttsx3 | Text-to-speech |

---

## Future-Ready Architecture

The codebase is designed so you can later replace:

| Current | Future | Files to Change |
|---------|--------|----------------|
| Tkinter | React / Electron | Only `gui/` directory |
| SQLite | PostgreSQL / MySQL | Only `database/db.py` |
| Local AI | OpenAI / Gemini | Only `core/ai_manager.py` |
| Google STT | Whisper / Vosk | Only `core/listener.py` |
| pyttsx3 | Cloud TTS | Only `core/speaker.py` |
| Keyword parser | NLP (spaCy/Rasa) | Only `core/command_parser.py` |

---

## Requirements

```
SpeechRecognition>=3.11.0
sounddevice>=0.5.0
scipy>=1.13.0
pyttsx3>=2.98
```

Install with: `pip install -r requirements.txt`

---

## License

Personal project by Suneel Kumar.
