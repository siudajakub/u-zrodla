"""Materialized queue rows. Source cases and their audit history stay authoritative."""
import json

from . import store


# Rebuild the projection on startup when its format or the accepted analysis rules change.
FORMAT = 3


def _track(db, table, column, kind, update_when=""):
    for action, rows in (("INSERT", ("NEW",)), ("UPDATE", ("OLD", "NEW")), ("DELETE", ("OLD",))):
        keys = [f"{row}.{column}" if column else "''" for row in rows]
        values = ",".join(f"(\'{kind}\',{key})" for key in keys)
        condition = f"WHEN {update_when}" if action == "UPDATE" and update_when else ""
        db.execute(f"CREATE TRIGGER queue_{table}_{action.lower()} AFTER {action} ON {table} {condition} "
                   f"BEGIN INSERT INTO queue_dirty(kind,key) VALUES {values} ON CONFLICT(kind,key) DO NOTHING; END")


def migrate(db):
    db.execute("CREATE TABLE queue_rows("
               " id TEXT PRIMARY KEY, creator_id TEXT, updated TEXT NOT NULL, origin TEXT, module TEXT NOT NULL,"
               " platform TEXT NOT NULL, pending INTEGER NOT NULL, gated INTEGER NOT NULL, disclosure TEXT,"
               " summary TEXT NOT NULL, search TEXT NOT NULL)")
    db.execute("CREATE INDEX queue_rows_creator ON queue_rows(creator_id)")
    db.execute("CREATE TABLE queue_members("
               " name TEXT NOT NULL, id TEXT NOT NULL, PRIMARY KEY(name,id)) WITHOUT ROWID")
    db.execute("CREATE INDEX queue_members_case ON queue_members(id)")
    db.execute("CREATE TABLE queue_dirty(kind TEXT NOT NULL, key TEXT NOT NULL, PRIMARY KEY(kind,key)) WITHOUT ROWID")
    db.execute("CREATE TABLE queue_generation(id INTEGER PRIMARY KEY CHECK(id=1), signature TEXT NOT NULL)")
    tracking(db)


def tracking(db):
    db.execute("CREATE INDEX IF NOT EXISTS case_history_lookup ON history(case_id,action,seq DESC)")
    _track(db, "cases", "id", "case")
    _track(db, "qualification_results", "case_id", "case")
    _track(db, "history", "case_id", "case")
    _track(db, "versions", "id", "case")
    _track(db, "version_meta", "id", "case")
    _track(db, "creators", "id", "creator",
           "OLD.id IS NOT NEW.id OR json_extract(OLD.body,'$.name') IS NOT json_extract(NEW.body,'$.name')")
    _track(db, "thresholds", None, "settings")
    _track(db, "qualification_settings", None, "settings")


def _write_rows(db, rows, current, settings):
    names = store.creator_names(db)
    variant = settings["variant"]
    threshold = settings["thresholds"].get(variant, 60)
    for row in rows:
        case = store.case_dict(db, row, current, 2, settings, full=False)
        creator = case.get("creatorId")
        if not case.get("creatorName") and names.get(creator):
            case["creatorName"] = names[creator]
        summary = store.summary_of_case(case, threshold, settings["thresholds"])
        module = case.get("module") or "M1"
        platform = store.canonical_platform(str(case.get("platform") or "").split(":")[0])
        gated = module == "M1" and bool(store.variant_view(case, variant, threshold).get("gated"))
        disclosure = None
        if "adRegister" in case["queues"]:
            where = (case.get("adRelationship") or {}).get("disclosure") or {}
            disclosure = where.get("where") or "none"
        search = [str(case.get(k) or "").casefold() for k in ("title", "creatorName", "author", "creatorId")]
        db.execute("INSERT INTO queue_rows VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (case["id"], creator, case["updatedAt"], case.get("origin"), module, platform,
                    summary["transcriptState"] == "pending", gated, disclosure, store.dump(summary), store.dump(search)))
        db.executemany("INSERT INTO queue_members VALUES(?,?)", ((name, case["id"]) for name in case["queues"]))


def refresh(db, startup=False):
    """Refresh dirty rows under the transaction lock that protects their source data."""
    dirty = db.execute("SELECT kind,key FROM queue_dirty").fetchall()
    if not dirty and not startup:
        return
    current = store.analysis_current()
    reset = any(kind == "settings" for kind, _ in dirty)
    if startup:
        signature = store.dump([FORMAT, current])
        saved = db.execute("SELECT signature FROM queue_generation WHERE id=1").fetchone()
        if saved is None or saved[0] != signature:
            reset = True
            db.execute("INSERT OR REPLACE INTO queue_generation VALUES(1,?)", (signature,))
    if not reset and not dirty:
        return
    settings = store.load_settings(db)
    if reset:
        db.execute("DELETE FROM queue_members")
        db.execute("DELETE FROM queue_rows")
        _write_rows(db, db.execute("SELECT * FROM cases"), current, settings)
    else:
        keys = {key for kind, key in dirty if kind == "case"}
        for kind, creator in dirty:
            if kind == "creator":
                keys.update(row[0] for row in db.execute("SELECT id FROM queue_rows WHERE creator_id=?", (creator,)))
        db.executemany("DELETE FROM queue_members WHERE id=?", ((key,) for key in keys))
        db.executemany("DELETE FROM queue_rows WHERE id=?", ((key,) for key in keys))
        rows = (row for key in keys if (row := db.execute("SELECT * FROM cases WHERE id=?", (key,)).fetchone()))
        if keys:
            _write_rows(db, rows, current, settings)
    db.execute("DELETE FROM queue_dirty")


def summaries(db, queues, module=None):
    names = ",".join("?" for _ in queues)
    where = " AND r.module=?" if module else ""
    args = (*queues, module) if module else queues
    rows = db.execute(f"SELECT r.summary,r.search FROM queue_rows r JOIN "
                      f"(SELECT DISTINCT id FROM queue_members WHERE name IN ({names})) m USING(id)"
                      f" WHERE 1{where} ORDER BY r.updated DESC,r.id", args)
    return [{**json.loads(row[0]), "_search": json.loads(row[1])} for row in rows]


def counts(db, history=False):
    result = dict.fromkeys(store.QUEUES, 0)
    result.update(db.execute("SELECT name,count(*) FROM queue_members GROUP BY name"))
    if not history:
        result["demo"] = 0
    result["transcriptPending"] = db.execute("SELECT count(*) FROM queue_rows "
                                            "WHERE pending=1 AND origin IN ('live','replay')").fetchone()[0]
    return result


def funnel(db, counts):
    where = " WHERE origin IN ('live','replay')"
    seen = dict(db.execute("SELECT module,count(*) FROM queue_rows" + where + " GROUP BY module"))
    platforms = dict(db.execute("SELECT platform,count(*) FROM queue_rows" + where + " GROUP BY platform"))
    disclosed = dict(db.execute("SELECT disclosure,count(*) FROM queue_rows" + where +
                               " AND disclosure IS NOT NULL GROUP BY disclosure"))
    held = db.execute("SELECT count(*) FROM queue_rows" + where + " AND gated=1").fetchone()[0]
    names = {"transcript": "bySpeech", "platform": "byPlatformFlag", "frame": "byFrame", "description": "byDescription"}
    return {"materials": sum(seen.values()), "adRegister": counts["adRegister"], "review": counts["review"],
            "explainedAutomatically": {label: disclosed.get(source, 0) for source, label in names.items()},
            "adRegisterUnexplained": sum(count for where, count in disclosed.items() if where not in names),
            "heldBySpeechGate": held, "byModule": {m: seen.get(m, 0) for m in ("M1", "M2", "M3")},
            "byPlatform": platforms}
