For each claim where data and code are available, run the analysis and compare the output to the published numerics, and record the result in the claim's `reproductions:` block.

Verification is the re-enactment of a paper's analysis against its deposited code and data, with the reproduced numerics compared against those reported in the paper. The unit of verification is the claim, not the figure; a single figure may host several claims, and a single verification script typically targets several claims at once.

## The `verify.py` pattern

Verification scripts are authored at `verification/<paper-slug>/verify.py`. Each script follows a common pattern:

1. **Acquire data.** Clone the deposited GitHub repository (`git clone --depth=1`) or download the public deposit (NeuroVault collection, OpenNeuro CSV/NIfTI bundle, RCSB PDB file, G-Node Excel, OSF posterior CSV, Dryad archive). Record the deposit URL in the script header. Cache to `/tmp/<paper-slug>/`.

2. **Construct environment.** Conda or pip; apply patches where deposited code has been broken by upstream API drift. Deposited analysis code is often a few years old and pinned to nothing, so a renamed attribute in a plotting library is enough to make it error at the rendering step. Patch automatically, before execution, and record the patch: a reproduction that silently edits the deposit is not a reproduction of it.

3. **Execute targeted analyses.** Either re-run the deposited notebook end-to-end, or load pre-computed intermediates (CSV, NPY, NIfTI) and run the figure-generation step only. Most scripts implement both modes and switch on a `--full` flag (see FAST vs FULL mode below).

4. **Compare to paper-reported numerics.** Reproduce point estimates, statistics, p-values, panel coordinates, or in the imaging case, voxel counts and peak coordinates. Tolerance for "match" is per-claim and recorded inline.

5. **Write a per-claim row to `verify.log`.** Each row carries the claim slug, the paper-reported value, the reproduced value, and a status of `PASS` / `WARN` / `FAIL`. The log is committed to the repository and is the audit trail for the corpus.

The script is invokable from the command line in three modes:

- `python verify.py` — fast mode (default), runs all claims on cached/pre-computed data
- `python verify.py --full` — full pipeline (long simulation, raw preprocessing)
- `python verify.py --claim <slug>` — single-claim verification

## FAST vs FULL mode

The deposit-first principle (run the figure-generation step from pre-computed intermediates rather than rerun the simulation or preprocessing pipeline) governs the FAST mode. FULL mode is the end-to-end re-execution.

For computationally expensive analyses, FAST is often the only path that completes in reasonable time, and the gap is not marginal: reading a published mean from a cached hundred-row CSV takes minutes, where the end-to-end path may mean a multi-gigabyte archive, a simulator to install, and hours of compute for the same number. A claim settled in either mode is settled; what differs is what else the run would have checked along the way.

The FAST/FULL split makes the deposit-first path explicit in the script. Where deposited intermediates are available, they are the primary verification target; the underlying simulation or preprocessing is verified by inspection of the deposited code rather than by full re-execution.

## The from-notes fallback

When a download fails, when the script times out, or when a long simulation that completed in a prior session does not complete in the current session, the verify function falls through to hard-coded values carried forward from the prior verification session and still emits `PASS`. This pattern is documented because it appears in actual scripts.

This is honest in one sense — the values were reproduced live in a prior session, and the script is recording that prior outcome rather than inventing one. But the `PASS` in the current log is not backed by current execution, and nothing in the log says so. A reader who consults only `verify.log` sees `PASS` and cannot distinguish a value read from data this run from a value carried forward from a run they cannot see, unless they read the script. The evidentiary trail exists in the claim files; it just is not where the reader looks.

That is the argument for provenance the script emits itself rather than prose written afterwards — every file opened, with size and hash, and every value compared beside the one the paper reports. A status is only as good as the record of how it was obtained, and a fallback that emits the same status as a live run erases exactly that distinction.

A mismatch is a third case, and the one the vocabulary has to keep separable. A re-run that reproduces a paper's *discrepancy* — the analysis runs, and lands somewhere the paper does not — is a successful reproduction of a failure, not a failed reproduction. The run passed; the claim did not. `failed:mismatch` on the claim and `PASS` on the run are both correct and must not be collapsed, which is why the status vocabulary below separates the claim's verdict from the script's exit.

## Status vocabulary — verification criteria

| Status | Criterion |
|:-------|:----------|
| `verified` | Live execution against deposited code and data reproduced the published numerics within tolerance, in this prototype's session or a logged prior session whose script and notes are committed. |
| `verified:partial` | A defined subset of the claim's quantitative content was reproduced; the rest is either inaccessible or outside the script's targeted scope. The matched portion is documented in `notes`. |
| `verified:with-nuance` / `verified:direction-and-trend` | Direction or trend reproduced; magnitude or statistical significance does not match. The discrepancy is recorded; the claim is not promoted to plain `verified`. |
| `unverified` | Not yet attempted, reason genuinely unknown (default for claim files in papers without a verify script). |
| `unverified:no-data` | Data deposit is documented but not accessible to this prototype. |
| `unverified:no-code` | Code is documented but not accessible. |
| `unverified:code-error` | Code is accessible and runs, but errors before producing output. The exact error is recorded; if a workaround exists (e.g., the matplotlib patch), it is recorded too. |
| `unverified:compute-infeasible` | Code is accessible and would run end-to-end, but the runtime exceeds available compute. The estimated runtime is recorded. The deposit-first path (pre-computed intermediates) is checked before assigning this status. |
| `failed:mismatch` | Live execution produced output that does not match the published numerics. The discrepancy is recorded in `notes` with enough precision to diagnose the cause. |

Assessment claims (structural properties of code or parameterisation) are verified by code inspection; mark `verified` and record in `notes` that verification was by code reading rather than execution — naming the file and the line, so the reading can be checked. Where the inspection turns on a calculation the deposited code does not perform (a parameter checked against the paper's own constants, say), carry the calculation out inline and record it, or the status rests on an assertion no reader can re-derive.

## Coverage is a property of a corpus, not of this layer

How many papers carry a verification script, how many claims a re-run could settle, and how many of those were settled live rather than from notes are all facts about a particular corpus at a particular moment. They are computed, not written down: `check_reproductions.py --corpus --strict` reports the spread across every reproduction record, and `audit_verifications.py` reports records asserting more than their run supports. A corpus that wants those numbers in its own documentation should generate them there, where they can go stale visibly, rather than transcribe them here, where they cannot.

What belongs here is the standard the numbers are measured against, which is the status vocabulary above.

[↑ Contents](#contents)

---
