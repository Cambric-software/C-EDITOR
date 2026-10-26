# C EDITOR migration plan

## Current state
- Python desktop app (Tkinter) with 6 departments: Documents, Design, Spreadsheet, Slides, Video, Animation.
- Renamed to C EDITOR.

## Target
- Flutter desktop app using cambric_design package.
- Same UI style, color palette, fonts as other Cambric products.

## Phases
1. Create Flutter app shell with sidebar navigation.
2. Port Documents department (rich-text editor, templates).
3. Port Design department (drag-and-drop canvas).
4. Port Spreadsheet (grid + formulas).
5. Port Slides (presentation builder).
6. Port Video (timeline editor).
7. Port Animation (frame-by-frame).
8. Add download page and CI.

## Notes
- Keep Python version as reference.
- Use shared cambric_design package.