# LemonCAD design system

New identity for a separate product. User selected **light, clean workshop** with lemon branding. No existing application styles in this workspace; Bixl Studio supplies future CAD functionality, not its visual identity.

## Identity

| Item | Rule |
|---|---|
| Name | LemonCAD, provisional pending name clearance |
| Mark | Simple lemon silhouette with pointed ends, a leaf, and one highlight; vector SVG |
| Wordmark | Lemon bold, CAD regular; deep olive; no space in the displayed name |
| Clear space | At least one quarter of mark width around logo |
| Minimum size | Mark 24 px; full wordmark 130 px wide |
| Tagline | Open a part. Make your next move. |
| Family | LemonCAD View / Draw / Fixture / Cost |

## Tokens

| Token | Value | Usage |
|---|---|---|
| Lemon | `#F3DF38` | Primary action, selected measurement, logo |
| Lemon soft | `#F8F4CD` | Selected navigation background |
| Deep olive | `#29352B` | Text, wordmark, strong structure |
| Leaf olive | `#59634C` | Secondary detail, focus ring, active controls |
| Muted text | `#687167` | Supporting copy on pale surfaces |
| Warm white | `#FFFEFA` | Panels, dialogs, buttons |
| Workshop grey | `#F5F6F0` | Page background |
| Canvas | `#F3F5EE` | Model canvas with faint optional dot grid |
| Soft olive | `#EDF1E7` | Model rows, thumbnails |
| Border | `#DFE3D7` | Panel and row separators; decorative, not sole control affordance |
| Success | `#496B51` on `#EDF3E8` | Saved status with text/check, never color alone |
| Caution | `#29352B` on `#FBF7E9` | Explicit drawing omissions |
| Error | `#963B31` on `#FFF1EC` | Proposed import/export failure state |
| UI type | System sans-serif, 14 px base, 1.5 line height | No remote font dependency |
| Numeric type | System monospace with tabular numerals | Values, dimensions, units |
| Type scale | 10 / 11 / 12 / 14 / 15 / 22 / 29 / 34 px | 10–11 px only supporting desktop metadata; core content 12–14+ |
| Spacing | 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 px | Consistent baseline scale |
| Radius | 5–6 px controls, 8–9 px panels, 14 px dialogs | No pill-shaped primary buttons |
| Shadows | None for regular panels; light shadow for paper; strong shadow for modal | Borders establish hierarchy |

## Product patterns

| Pattern | Appearance / behavior | States |
|---|---|---|
| Primary button | Lemon fill, deep olive label, 40 px minimum desktop height | Hover darkens subtly; 2 px focus ring; pending keeps width with verb; disabled needs text context |
| Secondary button | Warm white with border, leading line icon | Same focus; never yellow text on white |
| Navigation | Plain labels, yellow underline; sidebar selected row uses pale lemon | Distinguish current screen using text/shape as well as color |
| Viewer | One model canvas, floating left measurement tools, top-centre view tools and upper-right view selection; Smart Dimension enabled by default, whole-hole picking, mouse-following click-to-place dimensions and free trackball rotation | Loading progress/cancel, recoverable error, selection, no-selection |
| Dimensions | On-model labels, latest result in bottom status strip, explicit unit and basis | Selected card uses pale lemon with olive border; unsupported measurement explains why |
| Folders | Simple folder icon, name, project count, sharing summary | Private/shared status visible; inherited access explained in share dialog |
| Projects | Thumbnail + name + metadata rows | Draft vs published visible; keyboard activation required for production rows |
| Sharing | Owner/Viewer roles, audience selector, published revisions | Restricted by default; explicit invitation/link publication; revoke action in production |
| Drawing | White A3 sheet on grey desk; sheet rail left, settings right | Draft, pending generation, omissions, reviewed export; no invented title block |
| Dialog | Centered warm-white panel, visible close, one primary action | Escape closes; focus trapped and restored |
| Default landing | Large central file-drop area, Choose file button, supported formats and sample-part action; no login gate | Disclose server STEP processing before upload |
| Paid tools | Same interface, clear paid label, service-specific entry | Show scope and price before purchase; no fabricated pricing |

## Responsive and access

- Desktop authoring after sign-in: fluid width, 16 px page gutters, viewport-height layout, and two working cards. Chat/History share the left card (270–340 px); the model fills the remaining width. Panels scroll independently. Public landing and pricing retain their bounded 1280 px container.
- Landing: centred drop area, maximum 790 px; primary action visible on arrival.
- Mobile: 12 px outer gutters; preserve the bounded page treatment without horizontal scrolling.
- Below 760 px: scroll the command bar horizontally and wrap top actions. Target 44 px touch controls in implementation.
- Yellow always carries deep olive text. Do not use yellow as small text or as the only meaningful stroke on white.
- Production must provide visible keyboard focus, named icon controls, accessible model alternatives and sufficient contrast at final sizes.
- Viewer geometry is illustrative in the prototype; SVG is not a CAD calculation engine.
- Prototype screen switcher includes Brand for review only; production navigation follows user access.

## Do / don't

- Use lemon yellow sparingly so the model remains the focus.
- Use real units, source revision and clear approximation status.
- Keep free PNG/PDF exports ungated; save/share/draft drawing require a free account.
- Preserve folder ownership and private draft vs published revision boundaries.
- No gradients, glossy lemons, decorative AI sparkles, or shadows on every panel.
- No claim of browser-only STEP processing when using Bixl's server geometry path.
- Keep infrastructure terminology out of product navigation. Hosting is Railway, including Postgres and storage.

## Artifacts

- `plan/lemoncad-product.html`: self-contained clickable design prototype.
- `plan/assets/lemoncad-mark.svg`: standalone vector mark.
- `plan/assets/lemoncad-logo.svg`: vector mark and wordmark (system font text).
- `plan/assets/lemoncad-part-study.svg`: illustrative model study.

## Engineering feature page

Pricing opens a public page with three cards: weld fixture, checking fixture, and costing. Indicative credit prices are clearly marked; the shared-credit proposal and evidence live in `research/lemoncad-credit-pricing.md`. The cards describe proposed prices; checkout is not enabled. Configured Claude access is entitlement-gated.

## Floating CAD controls

- Shared desktop controls: 32 px height, 18 px icons, 12 px single-line labels. Icon-only controls are 32 × 32 px with accessible names and hover/focus tooltips.
- All three palettes: 4 px padding/gaps, 1 px border, 8 px radius, identical subtle shadow (`0 4px 16px #29352b12`), 16 px canvas inset. This shadow is reserved for floating controls.
- One separator per group boundary. Units is a compact named select. The left toolbar uses icons; view controls retain short text.
- Strong pale-lemon active tool/orientation; quieter bordered visibility toggles. Standard-view state clears on free orbit.
- One tab stop per toolbar, arrow-key navigation along its orientation. Native select retains its arrow keys. Coarse pointers use 44 px controls; narrow layouts move view selection below the top toolbar.

## Engineering workspace surfaces

The Viewer workspace uses one continuous workshop-grey background beneath the header,
model, assistant and compact footer. Assistant and model are separate warm-white containers
with 16 px corners, 16 px gaps and a subtle `0 2px 12px #29352b09` elevation shadow.
No full-width header/footer rule or shared sidebar divider joins the containers.
The model canvas is inset with 12 px corners. Preserve the bounded page width and
lemon accents; on small screens stack the containers with 12 px gaps.

## Unified workspace and access

- Top navigation contains Viewer and Pricing only; drawings and Engineering retain
  the Viewer navigation state.
- Guests can upload, measure and export PNG/PDF without signing in.
- Signed-in users gain My files, draft drawing, save and share actions in the workspace.
- My files is a dismissible, focus-trapped drawer over the current workspace. Folder
  links retain their existing public read-only access.
- Paid users gain Engineering beside the same model, with Chat and Estimate/Fixture
  brief tabs. Backend entitlement checks remain authoritative.
- Drawing sheets and settings open beside the model. On narrow screens, panels stack.
- The model viewer stays mounted across panels and Pricing so camera, dimensions
  and the selected part remain intact. Pricing does not grant paid access.
