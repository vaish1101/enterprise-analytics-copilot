# Final release and deployment boundaries

Review: 17 October 2026. No production configuration, GitHub branch or deployment was changed during this review.

Compatibility continuation: 18 October 2026. The complete additive publication
tree restores all existing presentation/schema types, structured analytics and
fact sources, metadata labels and unreleased-answer verification handling. The
optional experimental product summary coexists with the existing API fields;
unknown provider counts remain explicit only when experimental telemetry cannot
measure them. Default provider counts remain integers. Existing secret-scanner
rules, public test selections and both public/private Docker target names are
retained. All 72 previously excluded public-base files are unchanged. The
corrected public suite passed 194 checks, and the unchanged frontend passed 101
tests plus production/demo builds. These are offline software checks, not new
live-agent results or promotion approval.

## Existing hosted frontend

URL: https://enterprise-analytics-copilot.vercel.app/

Associated public commit: `79cd2a51776bbfbda2c5b98c596598211f6117a8`, frontend package version 1.0.0. GitHub records a successful Vercel deployment for that commit. The currently served main JavaScript, stylesheet and 3D chunk match a fresh pinned-source recorded-demo build byte-for-byte. This is stronger evidence than the package version alone; the version number is not a unique build identifier.

Recorded Mercedes analysis, source inspection, Henkel sales (10,348 EUR million), unsupported separate-price attribution and an unknown question were exercised in the deployed UI. They replay selected records/refusals, not current live model decisions. The historical Mercedes illustration does not establish that the new diagnostic sufficiency gate approved its documentary explanation.

`/api/v1/metadata` and `/ready` on the Vercel host return the SPA HTML rather than backend JSON. They are not healthy FastAPI endpoints. `build:demo` compiles the no-network recorded adapter. No active backend connection or backend CORS deployment is claimed. Vite's development proxy is local-only. Do not point the static deployment at a paid backend without authorization.

The checked public bundles contain no credential patterns, and all three font notices are served. Private Vercel environment settings were not accessible in this review; an owner must confirm that no secrets are stored in exposed `VITE_*` variables. Source/bundle scans do not certify hidden dashboard configuration.

## Security patch in this unpublished draft

Fresh npm review found GHSA-68fv-2mgg-jv7q in transitive `source-map-js` 1.2.1, a development dependency. This draft pins 1.2.2, the patched version, without changing frontend implementation. Only that locked package record changed. The final fresh npm audit reports no known advisories. Fresh Python requirements review reports no known advisories across 64 resolved packages; this does not certify all future resolutions or deployment images.

The production Vercel build was not redeployed. The vulnerable development-package finding is not evidence that the static browser UI was compromised or remotely exploitable. Review any deployment/tooling exposure to untrusted source maps before deciding urgency. [Reviewed advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

The Docker frontend stage now uses the existing font-license copy script rather than stale references to removed fonts. The public Docker target remains numerical-only, nonroot and credential-free; it is not the live four-agent backend.

## Architecture and release scope

The validated default remains unchanged. The opt-in four-role backend, shared sufficiency gate, bounded repair and deterministic release verifier remain in the package. The published frontend has no dedicated v2 `product.release_mode`/agent-role interface; end-to-end experimental mode presentation is not certified by its recorded replay. Do not silently promote or connect the candidate just because frontend and API tests pass.

Live evaluation still requires the frozen human-review requirement, verified all-in billing, explicit protocol/ceiling approval and separate semantic adjudication. Automated evidence review does not replace independent human sign-off. No provider request is authorized by a successful unit test or this documentation.

## GitHub and rights

Use the existing sanitized public repository history. Do not merge private commits, force-push private branches, export raw corpora/embeddings/provider transcripts, or rewrite protected evaluation history. Historical local database defaults should be rotated if reused outside disposable local development; no real provider key was identified by the scoped scans.

Existing project ownership and third-party notices are retained. Font license text is copied into build assets; raw publisher reports are not distributed. Screenshots show this project's existing UI and the recorded-demo disclosure. Package license inventories are not blanket redistribution permission for arbitrary third-party material.

Owner approval is required before any push. Vercel is connected to the public repository: pushing or merging may trigger a preview/production deployment. Coordinate those side effects before publishing even a review branch; no automatic redeployment is authorized here.
