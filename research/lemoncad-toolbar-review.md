# LemonCAD toolbar UX review

25 September 2026. Findings and proposed specification; no application changes.

## Recommendation

Use the upper-right view selector as the visual reference for **all floating controls**. Match button height, padding, corner radius, type and active states; do not force horizontal and vertical toolbars to have the same overall width. Keep the left tools, top-centre view controls and upper-right orientation selector in their current locations.

The current screen mixes three button patterns: stacked icon/label cards on the left, inline icon/label controls with a stacked Units field at the top, and compact text buttons at the upper right. That inconsistency makes the interface feel assembled from unrelated components.

## Audit of the current implementation

Review based on the latest viewer screenshot and `frontend/src/style.css`, `frontend/src/main.tsx`, and `DESIGN.md`.

| Element | Finding | Concrete proposal |
|---|---|---|
| Left tools | An 84 px container, wrapped labels and inherited 64 px button minimum width produce a tall, heavy palette. Primary command labels inherit 10 px text, while DESIGN.md reserves that size for supporting metadata. | Compact 32 × 32 px icon buttons in a 42 px-wide palette. Explain commands with named controls and hover/focus tooltips. Keep a readable contextual instruction for Smart Dimension. |
| Top-centre toolbar | 40 px minimum buttons plus 5 px vertical container padding; stacked Units label/select adds a second visual row. It is visibly heavier than the view selector. | Use the same 32 px control height. Fit / Shaded / Dimensions can retain short inline labels; replace the stacked Units field with a compact, accessibly named `mm` menu. |
| Upper-right view selector | Short labels and restrained padding provide the preferred density. Current CSS implies roughly 31 px button height at the default line height; this is a CSS estimate, not a measured browser bounding box. | Preserve its appearance, normalize controls to 32 px, and make the other toolbars match. |
| Container treatment | Main palettes use 12 px corners; the view selector uses 9 px. DESIGN.md specifies 8–9 px panel corners. | Shared 8 px radius, 4 px padding, 1 px border, and one identical subtle floating shadow. Record the floating-shadow exception in DESIGN.md before implementation. |
| Grouping | Old `.command-group` right borders/padding remain under new vertical group styling, alongside bottom separators. | Reset inherited group styling. Use one horizontal separator in a vertical palette and one vertical separator in a horizontal toolbar. |
| State hierarchy | Smart Dimension and Dimensions visibility both use the same prominent yellow treatment; orientation buttons do not indicate the chosen standard view. | Strong selected-tool treatment for Smart Dimension; quieter checked visibility state; selected orientation state that clears when freely orbiting. Communicate state through more than colour alone. |
| Placement | The top toolbars share a top offset, but their different heights make them look misaligned. | Shared top edge and shared 42 px outer height. Keep 16 px clearance from canvas edges; prevent collision at narrower widths. |

## Evidence and interpretation

- Rhino provides controls for toolbar image sizing and uses command icons with hover explanations. This supports compact controls with discoverable names; it does not establish a universal 32 px CAD standard. [Rhino sizes and styles](https://docs.mcneel.com/rhino/8/help/en-us/options/toolbars_sizes_and_styles.htm), [Rhino interface](https://docs.mcneel.com/rhino/8/help/en-us/user_interface/rhino_window.htm).
- W3C's toolbar pattern recommends a labelled group, arrow-key navigation and an explicit vertical orientation where applicable. The existing `role="toolbar"` is only part of that behavior. [WAI-ARIA toolbar pattern](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/).
- WCAG 2.2's minimum target-size criterion uses 24 × 24 CSS pixels, with specified exceptions. Proposed 32 px desktop controls are above that floor; retain the project's 44 px touch target policy for coarse pointers. This is not a whole-interface compliance assessment. [W3C target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum).

## Proposed shared toolbar specification

| Property | Desktop proposal |
|---|---|
| Control height | 32 px |
| Icon-only control | 32 × 32 px |
| Icon | 18 px, consistent stroke weight |
| Text | 12 px, one line; 16 px line height |
| Container | 4 px padding, 1 px border, 8 px radius |
| Outer toolbar thickness | 42 px (32 + 8 padding + 2 border) |
| Group separation | 8 px, one separator where helpful |
| Canvas offset | 16 px |
| Touch controls | 44 px target; allow larger palette / overflow |

These are LemonCAD design decisions based on the user's preferred selector, not measurements copied from Rhino.

Keep the dark blue-grey part and black edges. The next improvement is toolbar consistency, not another colour change. Preserve the current measurement workflow.

## Verification for a future implementation

Check desktop and narrow layouts without overlapping toolbar groups. All visible command text must stay on one line. Test named icon buttons, focus tooltips, keyboard navigation and selected states. Confirm floating controls do not obstruct the default fitted part. Update DESIGN.md's viewer pattern: its top-command-bar/automatic-label description predates the user's floating-tool and click-to-place decisions.
