# BoardProfile Usage

## Source Of Truth

Use the effective Markdown BoardProfile supplied by the local host. The effective document is the data-directory overlay when present, otherwise the bundled profile. Record its `id` and `revision` with the result.

The cloud model must not open BoardProfile files directly. Ask the local context assembler or Tool Runner to resolve the profile and provide bounded Markdown text.

## Required Metadata

Expect frontmatter with `id`, `name`, `aliases`, `platform`, and `language`. Require `language: micropython`. Reject an identity change when saving an overlay.

Use only facts present in the effective Markdown for board capabilities, pin mappings, memory, sensors, power, interfaces, and module names. When a needed fact is absent, label it unknown and request confirmation instead of borrowing it from a similar board.

## Overlay Behavior

Save edits through the local BoardProfile API with the loaded revision. A revision conflict must preserve the local draft and require an explicit refresh or merge. Reset removes only the overlay and restores the bundled profile.

Do not embed board-specific facts in `SKILL.md` or another reference. This keeps future boards and user overlays reusable without changing the skill.
