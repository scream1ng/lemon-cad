# LemonCAD compact toolbar research

Researched 2026-09-25. Scope: consistent floating viewport controls. User preference: preserve the current upper-right view selector size and size other tools consistently. No application code changed.

## Verified primary-source facts

| Source | Documented behavior | Implication for this design (recommendation, not source mandate) |
| --- | --- | --- |
| [Rhino 8 Button Editor](https://docs.mcneel.com/rhino/8/help/en-us/toolbarsandmenus/button_editor.htm) | Buttons can inherit their tab's appearance; support icon-only, text-only, or both; have hover tooltips; linked tools can appear in a flyout. | Use one shared button appearance and compact icons with descriptive tooltips; reserve flyouts for related secondary commands. |
| [Onshape User Interface Basics](https://cad.onshape.com/help/Content/Home/user_interface_basics.htm) | Toolbars change with workflow. Vertical dividers mark groups; dropdown arrows expose additional tools. Lower resolution or higher browser zoom moves more tools into dropdown groups. | Group related actions with small separators. Preserve usable button size at narrow widths by grouping overflow rather than shrinking icons further. |
| [W3C Target Size (Minimum), WCAG 2.2 AA explanation](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum) | Pointer targets require at least 24 × 24 CSS pixels unless an exception applies. The spacing exception checks 24px-diameter circles around undersized targets. The explanation recommends meeting minimum size even when spacing could qualify. | Match the existing view selector's visual density while keeping each actual hit area at least 24 × 24 CSS pixels. Icon artwork may be smaller than its button. |
| [W3C ARIA Toolbar Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/) | The pattern groups controls with an accessible name and recommends one tab stop with arrow navigation; toolbar grouping is recommended for three or more controls. | Name each group by purpose. If adopting toolbar semantics, implement the corresponding keyboard behavior. |
| [W3C Toolbar Example](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/examples/toolbar/) | Example tooltips appear on hover and focus and dismiss with Escape. Focus has a border/background treatment. Independent toggles use `aria-pressed`; mutually exclusive choices use radio semantics. The example is illustrative, not production-ready code. | Distinguish persistent selection, temporary hover, and keyboard focus. Pair compact icons with accessible names and focus-visible tooltips; expose actual selected state semantically. |

## Proposed direction

- Treat the existing upper-right view selector as the size reference: common button height, icon scale, corner radius, padding, gap, and border weight across floating tool groups. Measure that existing control before choosing numeric tokens; these sources do not establish a universal CAD button size.
- Keep floating groups compact and aligned to common viewport-edge offsets. Use one restrained surface treatment and subtle group separators. This placement and styling are design recommendations, not claims about a required CAD convention.
- Keep the current tool order and commands for a sizing pass. Apply the same active-state treatment across comparable controls; preserve distinctions between toggles, one-shot actions, and mutually exclusive modes.
- Verify at normal and increased browser zoom: controls remain reachable, groups do not overlap, tooltip text identifies each icon, and pointer targets remain usable.

No direct quotations used.
