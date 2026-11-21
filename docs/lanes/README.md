# Feature Lanes

One branch-local record per concurrent feature lane. It preserves the context needed for another
person or agent to review, integrate, cut, or resume the lane without a meeting.

After J authorizes the bootstrap and the captain creates the integration base, use
`python3 tools/hack_join.py --list` to see available work. With a selected lane,
`python3 tools/hack_join.py` creates the branch/worktree and prefills its record. Captains can use
`sh tools/hack_start.sh <feature>` for unplanned work. A record owns only its lane; shared
priorities live in `TEAM_BOARD.md` and shared interfaces live in `docs/hackathon/contracts.md`.

The four records dated 21 November with the original branch names document the first delivered wave. Consult the [current board](../../TEAM_BOARD.md) and [acceptance matrix](../ODBIOR-UKNF.md) for the active scope.

## Rules

- One owner and one record per feature branch.
- Claim concrete paths/modules and avoid overlap. Coordinate shared generated files explicitly.
- State is one of `PLANNED`, `ACTIVE`, `BLOCKED`, `READY`, `INTEGRATED`, or `CUT`.
- Keep `Current State`, `Next Step`, `Verification`, and `Fallback / Cut` factual and current.
- Local lane records are visible to `python3 tools/hack_status.py` on the same machine. Commit
  and push to share the record on another host only after J explicitly authorizes both.
- Keep integrated records as a short event history. After the hackathon, archive or delete them.

Run `python3 tools/hack_status.py` after fetching to aggregate local worktrees plus committed
`hack/*` branches. It is read-only and does not replace the PR or issue tracker.
