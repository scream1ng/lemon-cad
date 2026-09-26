# LemonCAD avatar menu research

26 September 2026. Scope: signed-in workspace avatar menu. Recommendations below are design inferences from official product and design-system documentation, checked against the current LemonCAD frontend.

## What the references establish

- Claude routes account-wide settings through its profile menu. Appearance and billing are settings destinations; support is a separate “Get help” item. [Claude appearance](https://support.claude.com/en/articles/8887527-customizing-your-appearance-settings), [billing](https://support.claude.com/en/articles/8325618-paid-plan-billing-faqs), [support](https://support.claude.com/en/articles/9015913-how-to-get-support).
- ChatGPT starts project creation in the sidebar and puts project settings under the individual project's options. Its tools are available from the project/chat context. This supports keeping project navigation and CAD workflows near the work rather than in the identity menu. [Projects in ChatGPT](https://help.openai.com/en/articles/10169521-projects-in-chatgpt).
- Carbon recommends short, precise menu labels, meaningful grouping, and few items. It treats menus as a way to hide secondary actions, not as a place for complex form inputs. [Carbon menu guidance](https://carbondesignsystem.com/components/menu/usage/).
- The W3C menu-button pattern calls for keyboard opening, arrow-key movement, Escape to close and restore focus, and appropriate `aria-haspopup` / `aria-expanded` semantics. [WAI-ARIA menu button](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/).

## Recommendation for the current build

Keep the avatar menu narrow and account-specific:

1. **Identity header:** avatar and full email; truncate visually with the full email still available to assistive technology or a tooltip.
2. **Plans & credits:** open the existing Pricing view. Label it “Plans & credits” only if that view clearly explains credits; it currently does, while checkout is unavailable. Do not show a balance or “Manage subscription” without real account data/actions.
3. **Connect Google:** retain only when the account has not connected Google, as the current code does. If more connections arrive later, move them into a real account settings screen rather than growing the menu.
4. **Sign out:** last item, separated from the account actions.

The current **My projects** menu item duplicates the left Projects tab and can be removed. Keep folder creation/sharing, project navigation, CAD export, drawing, costing, and fixture launchers in their respective work surfaces. This is an inference from the product examples above and the current LemonCAD layout, not a claim that every AI product uses the same menu.

Add **Help** only when there is a real LemonCAD documentation or support destination. Add **Settings**, **Theme**, and **Usage** only when those controls/pages exist. Claude demonstrates where such features can live once built; it does not justify placeholder items. A future usage item should show real usage, not a guessed credit count.

## Current implementation check

`frontend/src/main.tsx` currently has identity, My projects, conditional Connect Google, and Sign out; the main navigation has Pricing. `frontend/src/WorkspaceSidebar.tsx` already has Projects. No account settings, theme switch, usage dashboard, or help destination was found in the frontend. The recommended immediate change is therefore **replace My projects with a link to the existing Plans & credits view**, or leave the menu at two actions if Pricing should stay solely in primary navigation.
