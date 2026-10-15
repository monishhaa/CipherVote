# Feature audit (A1–B4)

Checked against the current source and the isolated test database. The prompt stopped at B4, so later items are not scored here.

Dev database backup, taken before this audit: `data/backup/securevote_20261015T141829Z.db`.

## Phase 0 baseline

| Check | Result |
| --- | --- |
| Backend pytest | 59 passed, 1 failed, then the failing test was fixed. `test_lfw_sample_voters_endpoint` now passes. Full suite before that fix: 60 tests, 1 failure. |
| Frontend unit tests | None. `frontend/package.json` has `dev`, `build`, and `preview` only. |
| Frontend lint | No lint script. |
| TypeScript | `npx tsc --noEmit` in `frontend` exited 0. |
| Test database guard | `backend/tests/conftest.py` forces `test_securevote.db` and aborts otherwise. Covered by `test_suite_refuses_dev_database`. |

Documented start commands and what this machine actually needs:

- Backend from the repo root, after `source venv/bin/activate`: `uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload`. The handbook still shows an older machine path and `uvicorn backend.app.main:app`.
- Frontend: `cd frontend && npm run dev`. Vite’s default port is 5173. The handbook says 3000.

API routers are mounted under `/api`. Frontend sections are `/` (landing), `/admin/e/:electionId/:section`, `/user/e/:electionId/:section`, `/user/login`, `/user/register`, and `/ceremony/:token`. `/audit` is rewritten into the voter portal.

Tables with an `election_id` column in the dev database: `elections`, `trustees`, `voters`, `ballots`, `tally_results`, `notifications`, `email_outbox`, `archived_elections`. `login_audit_logs` has no `election_id`. The ORM defines it, and this audit found no writer.

## Matrix

| ID | Feature | Expected behaviour | How verified | Status | Fix summary |
| --- | --- | --- | --- | --- | --- |
| A1 | Two landing entries | Landing offers only Voter and Administrator. `/audit` enters the voter portal. | Read `frontend/src/pages/Landing.tsx` and the `/audit` rewrite in `frontend/src/App.tsx`. | PASS | Removed the header “Public Audit Ledger” link and the footer “Trustee access” link. `/audit` now replaces itself with `/user/e/:id/audit` when an election is stored, otherwise `/user/audit`. |
| A2 | Role guards and admin credentials | A voter session gets 401/403 on `/api/admin/*`. An admin session gets 401/403 on `/api/voter/*`. Admin routes require sign-in. The password is checked as a hash of the `.env` value and is not in the frontend. Logout clears the session. | `test_role_guards_and_hashed_admin_login`. Logout: `handleAdminLogout` and `handleVoterLogout` in `App.tsx` remove the session keys. | PASS | Admin login and trustee reissue compare SHA-256 digests. The process no longer prints the default password. |
| A3 | Election id in the URL | Election pages use `/admin/e/:id/...` and `/user/e/:id/...`. Refresh keeps the id. Switching elections clears banners, drafts, and cached page state. | Route parser in `frontend/src/utils/routeUtils.ts`. Switch handler clears banners and remounts voter pages with `key={electionId}`. Notifications request includes `election_id`. | PASS | Admin switch navigates to the same section under the new id and clears banners. Vote, overview, and notifications remount per election. |
| A4 | One product name, no raw ids, no `[object Object]` | Titles and UI use `APP_NAME`. Users do not see slugs. API errors go through `formatApiError`. | `APP_NAME` is `SecureVote` in `frontend/src/constants.ts`. `npx tsc --noEmit` passed. Election cards no longer print `ID:`. | PARTIAL | Replaced visible CipherVote strings and the election-card slug. Access-denied text no longer includes the election id. Some older pages still pass `data.detail` into `Error` before `formatApiError`. |
| A5 | Forms in both themes | Typed text and autofill stay visible. Custom dropdowns are readable. Admin login can show or hide the password. | `PasswordInput` already toggles visibility. Input variants set ink/paper text colors. Autofill rules added in `frontend/src/index.css`. | PARTIAL | Autofill text color is forced for paper and ink fields. Not re-checked in a browser this pass. |
| B1 | Create, edit, archive, delete | Admin can create a title, optional description, 2–10 unique candidates, and a timezone; edit until voting opens; archive; delete only with zero voters. | `test_election_edit_archive_delete_and_isolation`. | PASS | Update and delete used an undefined id and crashed. Delete counted every voter in the database. Both are scoped to the path id. Description is stored. `POST /api/admin/elections/:id/archive` sets `ARCHIVED`. The elections screen can edit, archive, and delete. |
| B2 | Checklist and empty states | Overview has a setup checklist. No-election states are empty states. Landing and registration say the election is not open yet. | Checklist and “No election selected” are in `AdminDashboard.tsx`. Landing shows “No election configured yet”. Register shows “Registration is not open yet.” | PASS | Already present. No code change. |
| B3 | Election isolation | Rows are scoped by `election_id`, with composite uniqueness for voter id, email, and ballot sequence. Rolls, counts, notifications, and keys do not leak. | `test_election_edit_archive_delete_and_isolation` checks voter counts, rolls, blind-signature keys, and genesis hashes. | PARTIAL | List counts and notification broadcasts were global; they now filter by `election_id`. Voter inbox requests pass `election_id`. `login_audit_logs` still has no `election_id`. Several routes still default a missing id to `council-2026`. Token nonces are not stored as their own unique `(election_id, nonce)` row; `token_signature` is unique globally. |
| B4 | Sidebar badges and leftover elections | Elections badge is the non-archived count. Voter Roll and Trustee Portal status are for the open election. Archive leftover test or demo elections and list them. | Badge expression in `AdminDashboard.tsx`. Live rows read from `securevote.db`. | NEEDS-ME | The Elections badge now counts rows whose status is not `ARCHIVED`. Nothing was archived or deleted. The dev database has seven elections, and several have voters or ballots. |

## Elections left in the dev database

Nothing was archived. These rows are still active:

| election_id | title | status | voters |
| --- | --- | --- | --- |
| fashion-1791639459 | fashion | CLOSED | 5 |
| abcd-1791701153 | abcd | OPEN | 1 |
| xyz-1791915045 | xyz | OPEN | 0 |
| mnop-1791919950 | mnop | CLOSED | 1 |
| monisha-1791924501 | monisha | CLOSED | 0 |
| wxyz-1792066798 | wxyz | COMPLETED | 1 |
| manya-1792072148 | manya | COMPLETED | 1 |

Say which of these should be archived. `xyz` and `monisha` are the only ones with zero voters, so they are the only ones that can be deleted.

## [NEEDS ME]

- Confirm which live elections to archive or delete. This audit did not change them.
- Look at admin login, the election form, and both themes in the browser. Autofill and dropdown contrast were not clicked through here.
- Real webcam and Gmail were not used.
