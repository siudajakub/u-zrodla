# Integration And Branch Protocol

One merge train turns parallel lanes into a reliable demo.

## Branch Model

```text
main (demo-safe) <- hack/integration <- hack/<owner>/<feature>
```

- `main` changes only when a verified integration commit is promoted.
- `hack/integration` is owned by the integration captain and must stay runnable.
- Feature branches are short-lived and based on the latest integration branch.
- J explicitly authorizes commits and pushes. During bootstrap, the captain prepares the first
  integration base after authorization. Work in the primary checkout until the base exists.
- Never force-push a branch after review begins unless the reviewer agrees.

## Starting A Lane

The recommended path reads available work from the project documentation:

```bash
git fetch --all --prune
python3 tools/hack_join.py
```

For a lane that is not listed on the board, the captain may use the lower-level command:

```bash
sh tools/hack_start.sh <feature> --owner <name> --base hack/integration
```

Both commands create a sibling worktree, a `hack/<owner>/<feature>` branch, and a lane record.
`hack_join.py` also copies acceptance, claim, and dependency context from `TEAM_BOARD.md`.
Use `python3 tools/hack_join.py --list` to inspect available lanes and leave the checkout untouched.

## Ready Gate

In the feature worktree, run the checks in [AGENTS.md](../../AGENTS.md) and the tests for the
lane. Once the authorized candidate is committed and includes the current integration base, run
`sh tools/hack_ready.sh`. Record the result and request fresh-context review.

The owner resolves integration conflicts in the feature branch. The reviewer checks the lane's
acceptance, contract compatibility, tests, error/loading behavior, and removal/fallback path.

## Captain Merge Train

For one READY lane at a time:

1. Confirm the feature head and review approval have not changed.
2. Merge into `hack/integration` without rewriting feature history.
3. Run focused checks, then one golden-path smoke.
4. If broken, revert that merge or have the owner fix forward immediately. Do not stack more lanes
   on an unknown-bad integration commit.
5. Mark the lane INTEGRATED and announce any changed contract.

After a stable wave, run full checks and promote the exact integration commit to `main`. Tag demo
milestones so the team always has a known rollback point.

## Conflict Policy

- The feature owner resolves conflicts caused by their lane.
- Contract owners decide semantic conflicts; the captain decides merge order.
- Generated lockfiles, schemas, and migrations get one designated owner per integration wave.
- Never solve a conflict by discarding code you do not understand. Ask the owning lane.

## Emergency Cut

A lane must be removable without destabilizing the golden path. Revert its merge commit, disable
its default-off flag, or remove its route from the demo. Record the cut on `TEAM_BOARD.md`; leave
post-event repair outside the hackathon merge train.
