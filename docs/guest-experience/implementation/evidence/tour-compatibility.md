# Optional spotlight gate — GE-13.1

Decision: **DEFERRED / NOT ACCEPTED**. No Driver.js dependency or production adapter was added.
`PRODUCT_TOUR_ENABLED` stays false by default. GE-13.2 supplies a route-aware inline guide; there
is no custom spotlight replacement. This is an optional feature decision, not a claim that the
library can never work with an additional guarded adapter.

Observed package metadata (`npm.cmd view driver.js@1.10.2 version license dist.integrity dist.tarball --json`):

- Exact version 1.10.2, MIT; tarball `https://registry.npmjs.org/driver.js/-/driver.js-1.10.2.tgz`.
- Integrity `sha512-L/EMTriJPAmg+5kIFmrjzt3TI+1NblhHOV/UZkfpgU/uxhSflGheynMBxk5oImDSy6seAEkIl6MzNOc0zdoKtg==`.
- `npm.cmd pack driver.js@1.10.2 --ignore-scripts --pack-destination <owned-temp>` downloaded
  26 files. SHA512 was independently verified; every tar path was relative under `package`,
  with no traversal, links or special entries. License and exact distribution declarations were
  read before extraction/use. Package scripts are build/test/lint/release development scripts;
  no install script was executed. Manifest/lockfile remain unchanged.

The opt-in `onboarding-compatibility.spec.ts` loads the inspected IIFE/CSS through same-origin
fixture URLs on the actual StrictMode application, not a CDN or inline-script/CSP exception.
Enable `MOODPRINT_TOUR_COMPATIBILITY=1` and point `MOODPRINT_TOUR_SPIKE_DIR` to the inspected
`package` directory before running:

```powershell
npm.cmd exec -- playwright test --config playwright.owned.config.ts onboarding-compatibility.spec.ts --reporter=list
```

Without the fixture, the named availability gate failed explicitly (**1 failed**); absence was
not counted as success. With the fixture, the final run was **3 passed / 2 failed** (15.5s):

| Criterion | Observation |
| --- | --- |
| Repeated setup/destroy in the real StrictMode app | PASS: one popover at a time; no leftover popover/overlay; zero mutation requests. This is imperative adapter lifecycle evidence, not proof of an unimplemented React wrapper. |
| Escape / focus return | PASS: closes and returns to the prior visible launcher. |
| Reduced motion / 320px | PASS for this fixture: animate/smoothScroll disabled; popover fits viewport and Escape cleans it. |
| Native app dialog collision | FAIL: opening the real end-trial dialog leaves one Driver popover. A future adapter must coordinate destruction/focus before taking the native top layer. Initial locator ambiguity was corrected and the real count failure reproduced. |
| Actual serving-mode CSP | NOT ESTABLISHED: Vite response has no production CSP; the gate rejects it. Neither the Vite fixture nor package loading certifies the required FastAPI AND Caddy behavior. Their application/proxy checks remain GE-14 work. |
| Router/back/GSAP/full viewport/200%/soft keyboard/SR matrix | NOT PROVEN for a production spotlight. No manual NVDA/VoiceOver or device keyboard evidence. |

The failing optional spike stays reproducible behind an explicit test opt-in; it is not in the
default product regression suite because that suite ships the inline guide and contains no
spotlight. No product authorization, CSP or accessibility assertion was disabled to accept a
library. Raw browser evidence is in OS temp (`moodprint-guest/tour-spike-results`). Owned extracted
package files are disposable and are removed after recording the decision; re-pack/re-verify
the same integrity before any future spike. Public spotlight enablement requires a new complete
compatibility review; no alternate library or additional package is selected here.
