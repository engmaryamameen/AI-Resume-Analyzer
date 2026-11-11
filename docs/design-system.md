# Interface design

Rolemaker presents résumé analysis as an editing workflow: input, evidence, and a clear next action.

## Foundations

The interface uses self-hosted Inter, a text wordmark, a near-black canvas (`#050505`), dark neutral surfaces, lime accents (`#ABF565`), and teal primary actions (`#10B981`). Status colors always accompany explicit labels. Icons come from the shared SVG component.

Desktop layouts use a maximum 1440-pixel container with 64-pixel gutters. Smaller screens reduce gutters and collapse grids. Typography and spacing establish hierarchy; borders identify controls, source passages, and related content.

## Navigation and interaction

Desktop public navigation places the brand left, links centrally, and the primary action right. Mobile navigation uses a native modal dialog. Workspace navigation is an in-flow disclosure with `aria-expanded`, Escape handling, and focus restoration.

Links use a color change and animated underline. Disclosure panels animate their height and opacity, with transitions disabled for reduced motion. Report tabs support keyboard navigation. Upload requirement icons remain aligned with the first line of wrapped text. The footer stays compact and reflows on narrow screens.

## Component boundaries

- `frontend/src/lib/brand.ts` owns the application name and description.
- `frontend/src/components/brand.module.css` owns wordmark typography.
- `frontend/src/app/globals.css`, `product.css`, and `theme.css` define shared primitives, tokens, and application styles.
- Landing-page sections and the interactive report preview use CSS modules. Marketing heading selectors do not target nested form or report headings.
- Feature components own remote state and domain interactions; shared primitives provide consistent status and form feedback.

The landing report preview uses explicitly synthetic examples and a role selector. The `/demo` route runs the actual rules pipeline. Account and guest reviews use the API and worker. The interface identifies the processing method used; presentation does not imply independently validated model accuracy.

## Validation

Run frontend typing, lint, format, unit, and production build checks. Browser tests cover navigation geometry, source expansion, narrow layouts, upload-list alignment, heading size, reduced motion, focus behavior, and automated accessibility checks. Review populated, empty, loading, error, and long-content states when changing shared components.
