# CAD authoring toolbar: icons, tooltips, and discoverability

Researched 2026-09-27. Scope: the mechanical-part and assembly authoring prototype, `plan/cad-design-workspace.html`. This supplements the earlier CAD product research; it is separate from the existing live-viewer toolbar sizing notes.

## Verified product behavior

| Product | Officially documented behavior | Lesson for LemonCAD |
| --- | --- | --- |
| SOLIDWORKS | CommandManager supports large buttons with text as a configurable option. Tooltips can show the tool name only, a brief description, or a description with an image/animation. Context toolbars can appear when selecting a feature in the viewport or FeatureManager tree; quick mates are also configurable. Larger icons and touch mode are available. [Customize Toolbars](https://help.solidworks.com/2025/english/Solidworks/sldworks/HIDD_CUSTOMIZE_TOOLBARS.htm) | Use compact commands with explanatory hover cards, while retaining a labeled mode. Selection can narrow relevant commands. |
| SOLIDWORKS shortcuts | Separate customizable shortcut bars exist for Part, Assembly, Drawing, and Sketch. `S` opens the bar by default; arrows navigate, Enter runs a tool, and Escape dismisses it. Command search is included. [Shortcut Bars](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_shortcut_bars.htm?id=4.4.1.3) | Group tools by modeling context; provide a searchable route as the command set grows. |
| Onshape | Toolbars can be customized by moving tool sets or individual icons; the shortcut toolbar uses `S`. [Part Studios](https://cad.onshape.com/help/Content/PartStudio/part_studios.htm) Search can run tools, show descriptions on hover, and highlight their toolbar locations. Mobile search is available through the tools menu. [Search Tools](https://cad.onshape.com/help/Content/Home/search_tools.htm) | Icons need a discoverable, named alternative; search can also teach where tools live. |
| Shapr3D | The main menu defaults to icons; names appear on hover depending on settings. Menus and modes adapt to the selection. [Modeling space](https://support.shapr3d.com/hc/en-us/articles/7873880676508-Shapr3D-modeling-space) Shortcuts appear beside tool names; command search can use the current selection. [Accessing tools](https://support.shapr3d.com/hc/en-us/articles/7378907587484-Accessing-tools) | A quiet canvas can coexist with discoverable tool names and context-sensitive actions. |

SOLIDWORKS is not exclusively icon-only: the icon/text presentation is configurable. The user's proposed icon-first presentation is nevertheless well supported by these products. No exact SOLIDWORKS hover delay was established from the official documentation reviewed.

## Recommended LemonCAD design

These are design proposals, not claims about the products above or features already implemented.

- **Compact by default:** one row of recognizable CAD icons; retain text for Part / Sketch / Assembly tabs and primary workflow actions such as Apply change. Keep the history tree readable.
- **Stable groups:** separate creation, modification, inspection, and commenting with small dividers. Avoid moving common tools when the selection changes; show contextual help or an adjacent context area instead.
- **Clear symbols:** extrude shows a profile becoming a solid, cut shows removed material, fillet shows a rounded edge, and mate shows two constrained components. Do not reuse one generic cube for every operation.
- **Useful hover cards:** command name, an implemented shortcut if available, one sentence explaining the result, and any selection prerequisite. Example: **Fillet** — Round selected edges with a specified radius. **Select one or more edges.**
- **Timing:** start with approximately 450 ms on pointer hover and immediate help on keyboard focus; tune after testing. These timings are our proposed behavior, not a SOLIDWORKS specification.
- **Learnable fallback:** a visible Show labels switch. Automatically show labels for devices without hover; let taps activate commands normally. A labeled tool list or command search can support smaller touch layouts later.
- **Honest availability:** unavailable commands should explain the missing prerequisite or prototype limitation. Do not advertise keyboard shortcuts that do nothing.

## Tooltip interaction requirements

Custom hover content must be dismissible, hoverable, and persistent: users must be able to move the pointer onto the card, keep reading without a timeout, and dismiss an obscuring card without moving focus. Keyboard users need the same information on focus. [W3C: Content on Hover or Focus](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html)

Use a named button and associate supplementary help using `aria-describedby` with a `role="tooltip"` element. Keep keyboard focus on the command; Escape closes the tooltip. Do not put interactive controls inside a tooltip. These semantics follow the APG tooltip pattern, which W3C explicitly labels a work in progress. [W3C: Tooltip Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/)

Review the prototype with mouse hover, pointer movement onto the tooltip, Tab focus, Escape dismissal, label switching, narrow layouts, and a device with no hover. Tool names must remain available when hover is unavailable.

## Prototype revision and verification

Implemented only in [the authoring prototype](../plan/cad-design-workspace.html): icon-only part, assembly, orientation and fit controls; 32 px desktop targets, 44 px compact/touch targets; a shared tooltip with command name and purpose; a tool-names toggle; automatic labels on no-hover/coarse-pointer devices. Keyboard arrows navigate each toolbar, focused commands show help immediately, Escape dismisses it, and disabled Undo explains its prerequisite. No unimplemented shortcut is advertised. The 450 ms pointer delay is a LemonCAD choice.

Browser checked the icon layout, tool-name toggle, arrow-key focus, disabled-command explanation and Escape dismissal. Pointer-enter/leave and tooltip persistence are implemented; a physical touch-device check was not performed. JavaScript syntax and duplicate-ID checks passed. Existing application tests remain blocked by the previously reported missing `three` dependency; no app source, dependencies or tests were changed for this prototype revision.
