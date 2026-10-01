"""Simpan & muat hasil engine di tabel `scores`."""
import json
import sqlite3


def save_scores(con: sqlite3.Connection, payload: dict) -> None:
    con.execute("DELETE FROM scores")
    con.executemany("INSERT INTO scores (employer_id, rank, payload) VALUES (?,?,?)",
                    [(c["id"], c["rank"], json.dumps(c, ensure_ascii=False)) for c in payload["companies"]])
    con.execute("INSERT OR REPLACE INTO score_meta (id, payload) VALUES (1, ?)", [json.dumps(payload["meta"], ensure_ascii=False)])


def load_scores(con: sqlite3.Connection) -> tuple[dict, list[dict]]:
    meta = con.execute("SELECT payload FROM score_meta WHERE id = 1").fetchone()
    rows = con.execute("SELECT payload FROM scores ORDER BY rank").fetchall()
    return (json.loads(meta[0]) if meta else {}), [json.loads(r[0]) for r in rows]
