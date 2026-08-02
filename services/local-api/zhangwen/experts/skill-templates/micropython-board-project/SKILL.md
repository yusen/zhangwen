---
name: micropython-board-project
description: Build, revise, and validate versioned MicroPython projects for a named development board. Use for board-specific code generation, code review, user code edits, local static and syntax checks, or preparation for a separately confirmed USB serial upload when the effective board facts are supplied through a Markdown BoardProfile.
---

# MicroPython Board Project

## Workflow

1. Identify the exact development board. Do not substitute a generic ESP32 profile for an ambiguous board name.
2. Load the effective Markdown BoardProfile through the local context or Tool Runner. Treat its revision as the only board-fact source. Read [BoardProfile usage](references/BOARD_PROFILE.md).
3. Produce one recommended implementation containing both the software logic and hardware plan. Use MicroPython and the APIs declared by the effective BoardProfile.
4. Keep generated files reviewable and deterministic. Prefer a complete single `src/main.py`. Add only necessary flat `src/*.py` modules, and treat every generated source file as one validation and upload set; do not add non-uploaded placeholder files.
5. Save a user edit as a new immutable version with its base version and change summary. Never overwrite a prior version.
6. Run local static and syntax checks without executing project code. Read [Validation and device boundaries](references/VALIDATION.md). Treat real process exit codes as the only pass/fail source.
7. Report unrun, failed, and hardware-tested states explicitly. Do not describe saved but unvalidated code as accepted or upload-ready.

## Boundaries

- Keep the cloud model text-only. Local APIs and the Tool Runner own files, subprocesses, serial ports, and permissions.
- Keep ordinary MicroPython file upload separate from firmware erase or flashing. Require explicit confirmation for firmware operations.
- Never run real serial discovery, upload, `mpremote`, `esptool`, network access, or paid model calls during automated validation.
- Do not copy board pins, memory sizes, sensors, or APIs into this skill or its references. Load those facts from the effective BoardProfile so overlays take effect.
- Do not include API keys, Wi-Fi passwords, tokens, real serial identifiers, or personal data in code, logs, fixtures, or prompts.

## Result

Return the effective BoardProfile id and revision, created code version, base version, change summary, validation checks with exit codes, remaining risks, and the next confirmation-gated action.
