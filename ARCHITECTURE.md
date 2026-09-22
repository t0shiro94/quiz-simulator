# Architecture

Quiz Simulator is a local-first Windows desktop application built with **Python 3.14**, **PySide6** and **SQLite**.

The codebase separates the UI, quiz-domain rules, importing, persistence and reporting into distinct modules so the application can grow without concentrating all behavior in a single file.

## High-level flow

```text
JSON / PDF files
      |
      v
 importing.py
      |
      v
  domain.py  <---- validation / normalization / evaluation
      |
      v
  storage.py <---- SQLite + FTS5 + backups + learning progress
      |
      +------------------------+
      |                        |
      v                        v
 quiz_pages.py            report_pages.py
      |                        |
      +-----------+------------+
                  |
                  v
                app.py
                  |
                  v
             PySide6 UI
```

## Main modules

### `app.py`

Application shell and main PySide6 window.

Responsibilities include:

- application startup;
- main navigation;
- settings;
- backup and restore entry points;
- global styling;
- coordination between the main pages and the shared `Store`.

### `domain.py`

Contains the core quiz rules that do not depend on the graphical interface.

It handles:

- supported question types;
- answer outcomes and credits;
- JSON Schema validation;
- compatibility normalization between schema versions;
- question-bank validation;
- answer evaluation;
- text normalization.

Keeping these rules outside the UI makes them easier to test independently.

### `importing.py`

Handles external quiz sources.

It supports:

- JSON loading;
- normalization of imported banks;
- textual PDF parsing;
- extraction of questions, alternatives and answer keys;
- warnings for ambiguous or unsupported input.

PDF parsing is intentionally text-based. Pages without extractable text are reported as possible OCR cases instead of silently producing unreliable questions.

### `storage.py`

Persistence layer backed by SQLite.

The database stores:

- collections;
- question revisions;
- quiz sessions;
- answers and grading outcomes;
- learning progress;
- notes;
- settings.

The storage layer also manages:

- SQLite integrity checks;
- foreign-key validation;
- FTS5 full-text search;
- indexes for frequent queries;
- the constraint that only one active quiz session may exist at a time;
- backups and restore validation;
- question-learning indicators.

The database is stored locally under the application's data directory.

### `library.py`

Implements the question-library workflow, including collection and question management.

### `quiz_pages.py`

Contains the pages used to configure and run quiz sessions.

### `report_pages.py`

Contains dashboard, learning-progress and result views.

### `dialogs.py`

Reusable dialogs for editing, importing and other focused user interactions.

### `widgets.py`

Shared UI helpers and small reusable PySide6 components.

### `paths.py`

Centralizes application and resource paths so source execution and packaged execution can use the same code paths.

## Data model

The SQLite database uses separate tables for long-lived content and quiz history.

```text
collections
    |
    +---- questions ---- progress
    |         |
    |         +--------- notes
    |
sessions
    |
    +---- items
```

Questions keep revision information, while quiz-session items preserve the question payload used during that attempt. This allows previous results to remain meaningful even after a question is later edited.

## Search

The application uses an SQLite **FTS5** virtual table for indexed question search.

The search index is rebuilt when needed from the current stored question payloads.

## Validation

Imported data passes through two levels of validation:

1. JSON Schema validation for the supported file format.
2. Additional domain checks for constraints such as unique identifiers, non-empty content and valid answer references.

This prevents malformed imports from being written directly into the archive.

## Local-first design

Quiz Simulator does not require a remote account or application backend.

```text
Application
├── data/
│   ├── quiz.sqlite3
│   └── sources/
├── backups/
└── tmp/
```

User archives, learning history and imported sources remain on the local machine.

## Quality checks

The repository includes:

- `pytest` test coverage for domain and application workflows;
- `pytest-qt` for Qt-related tests;
- `ruff` for linting and formatting checks;
- a smoke-test launch mode;
- a benchmark script that exercises large synthetic archives;
- a PyInstaller build workflow for the Windows distribution.

For contributor setup and commands, see [CONTRIBUTING.md](CONTRIBUTING.md).
