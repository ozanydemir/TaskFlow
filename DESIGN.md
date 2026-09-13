---
name: TaskFlow
description: A reference-faithful navy workspace for local project tasks.
colors:
  primary: "#2563eb"
  primary-hover: "#3b82f6"
  action-blue: "#239bff"
  action-violet: "#5726f5"
  frame-start: "#0f192a"
  frame-middle: "#090f1a"
  frame-end: "#0b121e"
  card-start: "#141f30"
  card-end: "#0e1623"
  card-border: "#304461"
  card-hover-border: "#49658b"
  input-surface: "#121d2e"
  input-border: "#354c70"
  text: "#f2f5fc"
  metadata: "#96add4"
  completed-text: "#91a5c7"
  control-text: "#b3c6e9"
  project-cyan: "#00f2fe"
  project-emerald: "#10b981"
  project-purple: "#c084fc"
  project-amber: "#fbbf24"
  project-cyan-bg: "#082029"
  project-emerald-bg: "#092618"
  project-purple-bg: "#220f38"
  project-amber-bg: "#291e0a"
typography:
  display:
    fontFamily: "Segoe UI"
    fontSize: "34px"
    fontWeight: 800
  title:
    fontFamily: "Segoe UI"
    fontSize: "19px"
    fontWeight: 400
  body:
    fontFamily: "Segoe UI"
    fontSize: "18px"
    fontWeight: 400
  label:
    fontFamily: "Segoe UI"
    fontSize: "14px"
    fontWeight: 400
  badge:
    fontFamily: "Segoe UI"
    fontSize: "15px"
    fontWeight: 600
rounded:
  compact: "6px"
  dialog-control: "8px"
  tab: "9px"
  control: "10px"
  entry: "15px"
  card: "16px"
spacing:
  metadata: "12px"
  controls: "14px"
  compact: "18px"
  sections: "24px"
  card-columns: "28px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.dialog-control}"
    padding: "6px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-project:
    textColor: "#f4f6ff"
    rounded: "{rounded.control}"
    height: "50px"
    padding: "0 18px"
  input-task:
    backgroundColor: "{colors.input-surface}"
    textColor: "#f3f6ff"
    rounded: "{rounded.entry}"
    height: "68px"
  card-task:
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "26px 22px 24px 28px"
  chip-project:
    typography: "{typography.badge}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
---

# Design System: TaskFlow

## Overview

**Creative North Star: "The Reference TaskFlow Workspace"**

TaskFlow faithfully transfers the user-supplied reference into a functional native Windows PyQt5 desktop interface. Its world is dark navy, gently diagonal surface gradients, fine cool-blue borders, royal-blue and violet actions, and spacious task rows. The approved reference remains the visual authority; this document refreshes the existing design record from app_gui.py and taskflow_visuals.py.

Segoe UI carries practical interface text, while Segoe Print preserves the reference's handwritten motivational accents. The desktop uses native window, tray, focus and resizing behavior. HTML/CSS in the sidecar is a portable visual preview of native components, not a change of application platform.

**Key Characteristics:**
- Navy tonal layers with thin blue outlines.
- Blue-to-violet actions and gradient check branding.
- Readable wrapped task titles with quiet date and note metadata.
- Project-color identity without purpose-specific badge pictograms.

## Colors

### Primary
Royal blue is the dialog action color; action blue and action violet form the large add-task gradient. Related blue and violet stops in the check logo, completed checkbox and project-add control belong to the approved reference world.

**The Action Gradient Rule.** Reserve vivid blue-to-violet gradients for actions, completion and reference branding; structural surfaces remain navy.

### Secondary
Project identity uses paired dark backgrounds and bright text/borders. The first four assignments are cyan, emerald, purple and amber; DISTINCT_PALETTES supplies the remaining twelve assignments. Preserve that source palette and its project-index assignment rather than inventing a second categorization system. Colors are identity cues, not completion states.

### Neutral
The frame and task cards use diagonal navy gradients. Card and input borders separate neighboring surfaces. Bright text carries active titles; metadata blue carries dates and notes; completed text is muted alongside a strike-through.

## Typography

Segoe UI is the application face. Display type is bold (800), with a large wordmark (34px) reducing to compact display size (28px). Task titles are regular (19px), task entry and project tabs use body-size text (18px), metadata uses label-size text (14px), and project badges use semibold text (15px). The subtitle and active count use supporting text (16px). Native font metrics determine wrapping and line height; no web line-height is normative.

Segoe Print italic is confined to the reference mottos: header (20px) and footer (14px).

**The Complete Title Rule.** Wrap task titles as plain text and recalculate card heights using native font metrics after resizing; never clip a long title to preserve a fixed card height.

## Layout

The first viewport follows the approved reference: completion ring and branding, project navigation, task entry, task cards, then the footer. The header is draggable, and the task list owns vertical overflow. Project tabs scroll horizontally through wheel or drag gestures, with a functional overflow menu.

Default window dimensions are (1120 × 820 logical pixels), constrained by available screen space; the minimum is (640 × 520). The outer resize gutter is (8px). Main section spacing is (24px). Main horizontal padding reduces from (28px) to (20px) below window width (850px); the header motto hides at the same threshold. The footer motto is visible only from window width (1000px).

Card reflow is based on card width, separately from window width. Below (790px), badges move beneath metadata, horizontal padding and column gaps reduce to (18px), and vertical padding becomes (22px). Notes hide below card width (570px) but remain available through the task menu. Badge text elides with its full project name retained in a tooltip. Title width is capped at (510px), and height grows with wrapped content. Height includes implementation headroom for list-item margins and font rounding; this is a clipping safeguard, not a reusable spacing token.

**The Reflow Before Decoration Rule.** Keep task content and actions usable when space narrows; move project badges and hide the reference mottos at the implemented thresholds.

## Elevation & Depth

The shipped interface uses tonal layering, thin outlines and diagonal gradients, with no drop-shadow vocabulary or animated transitions. Cards brighten their outlines on hover; focused controls use brighter blue outlines. Preserve these immediate state changes instead of adding unsupported floating elevation.

**The Navy Layer Rule.** Separate frame, entry and cards through their existing navy surfaces and borders.

## Shapes

The frame has soft corners (18px); cards use the card radius, task entry and its square add button use the entry radius, and compact controls and badges use the control radius. Project tabs are softly rectangular rather than pills. Checkbox indicators are square (30px) with softened corners (7px) and a (2px) outline.

Icons are authored with QPainter, rendered at double resolution, and use rounded caps and joins with a consistent stroke (1.8 units). Keep existing native application and tray icon assets.

## Components

### Buttons
Project Add is a (50px) tall blue-navy-to-violet control. Add Task is a square (68px) gradient button with a white plus. Hover and focus brighten outlines; pressed states darken or flatten the surface. Task Add disables when trimmed input is empty.

Window controls are (48 × 44px): pin, hide and close. Pin has a checked blue state. Hide and close retain tray-hiding behavior; explicit application exit remains in the tray menu. No notification or maximize button is part of the approved interface.

Dialog actions preserve existing compact solid-blue primary and red destructive treatment. Their denser sizing is incumbent dialog behavior, not the main surface's scale.

### Chips
Project badges show the bracketed project name with its assigned dark fill, bright border and matching text. They contain no YouTube or purpose-specific icon. The minimum badge width is (228px), constrained by available width during reflow; truncation retains the full name in a tooltip.

### Cards / Containers
Task cards use the navy card gradient, card radius and thin border. Checkbox and task menu sit at the top of the row. Title, real date and editable note form the content column; completed titles mute and strike through. Double-click opens title editing. Footer count and clear-completed action sit below a thin top divider.

### Inputs / Fields
Task entry uses a navy bordered container (68px tall) with a document icon, transparent text field and reference placeholder. Enter and the plus button create a task. The large entry does not currently introduce a container focus ring; dialog fields have their existing blue focus border. Do not describe a preview focus style as shipped native behavior.

### Navigation
Project tabs are (50px) tall with project-color dots, dark resting surfaces, and bright project-color active outlines. Tümü uses a grid icon and blue selection. Fixed Project Add and overflow controls remain reachable while tabs scroll.

### Completion Ring
The ring is (80px) with a navy track, royal-blue clockwise progress from the top, rounded arc caps and centered percentage. Its value reflects completion in the selected project scope.

## Do's and Don'ts

### Do:
- **Do** preserve the approved reference's navy gradients, blue/violet actions and handwritten mottos.
- **Do** measure native wrapped title height after resizing and retain clipping headroom.
- **Do** preserve project colors, plain badge names, tooltips and reachable overflow controls.
- **Do** keep pin, hide and close behavior compatible with the existing tray workflow.

### Don't:
- **Don't** add notification or maximize controls to the reference header.
- **Don't** add YouTube or purpose-specific pictograms to project badges.
- **Don't** turn compact layout into truncated task titles or horizontal task-list scrolling.
- **Don't** substitute a generic web, iOS or Android visual system for this native reference.
