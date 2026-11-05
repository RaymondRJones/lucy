# UI overhaul, round 2: review assets

Before and after screenshots for the `ui-polish-round2` branch. "Before" is `main` at `e052907`. "After" is the final
state of the branch. All shots use the seeded sample cases (`seed_happy_path`, `seed_packet_scenarios`) plus two cases
created for this review ("Fresh case in progress" with a checklist but no answers, and "Brand new case" with nothing).
They come from a scratch database, so no real case data appears in them.

Desktop shots were 1440px wide (scaled to 1000px here); mobile shots are 390px wide. Full-page captures cannot show
sticky elements, so `state-packet-scrolled-desktop-after.jpg` shows the Print packet panel after scrolling.

| Screen | Before | After |
|---|---|---|
| Review, case with an out-of-scope answer | `review-alt-desktop-full-before.jpg` | `review-alt-desktop-full-after.jpg` |
| Review, case with a checklist but no answers | `fresh-review-desktop-full-before.jpg` | `fresh-review-desktop-full-after.jpg` |
| Review, case created a moment ago | `empty-review-desktop-full-before.jpg` | `empty-review-desktop-full-after.jpg` |
| Review, happy path | `review-desktop-full-before.jpg` | `review-desktop-full-after.jpg` |
| I-485 form | `i485-desktop-before.jpg` | `i485-desktop-after.jpg` |
| Prescreen, no answers yet | `fresh-prescreen-desktop-before.jpg` | `fresh-prescreen-desktop-after.jpg` |
| Print packet | `packet-desktop-before.jpg` | `packet-desktop-after.jpg` |
| Print packet, prescreen unfinished | `fresh-packet-desktop-before.jpg` | `fresh-packet-desktop-after.jpg` |
| I-485 form, mobile | `i485-mobile-full-before.jpg` | `i485-mobile-full-after.jpg` |
| Review, mobile | `review-alt-mobile-full-before.jpg` | `review-alt-mobile-full-after.jpg` |

After-only states: `state-packet-scrolled-desktop-after.jpg` (assemble panel with its confirmations, scrolled),
`state-packet-fee-unticked-desktop-after.jpg` (I-485 fee unticked), `state-packet-fees-not-final-desktop-after.jpg`
(prescreen unfinished), `state-packet-only-missing-desktop-after.jpg` (evidence filtered to items without a file).
