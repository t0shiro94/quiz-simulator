from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from .domain import (
    CREDITS,
    UNTAGGED,
    evaluate,
    fingerprint,
    question_errors,
    score,
    validate_bank,
)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def file_digest(path: Path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Store:
    """Archivio SQLite; ogni thread di lavoro usa un'istanza separata."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.data = self.root / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / "sources").mkdir(exist_ok=True)
        (self.root / "backups").mkdir(exist_ok=True)
        (self.root / "tmp").mkdir(exist_ok=True)
        self.path = self.data / "quiz.sqlite3"
        self._connect()
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.close()
            raise ValueError("Archivio creato da una versione dell'app non compatibile.")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS collections(
          id TEXT PRIMARY KEY, title TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
          deleted_at REAL, reset_at REAL NOT NULL DEFAULT 0, source TEXT);
        CREATE TABLE IF NOT EXISTS questions(
          pk INTEGER PRIMARY KEY, collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
          external_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
          payload TEXT NOT NULL, fingerprint TEXT NOT NULL, topic TEXT NOT NULL, kind TEXT NOT NULL,
          favorite INTEGER NOT NULL DEFAULT 0, deleted_at REAL, reset_at REAL NOT NULL DEFAULT 0,
          UNIQUE(collection_id, external_id));
        CREATE INDEX IF NOT EXISTS idx_questions_filter ON questions(collection_id, deleted_at, topic, kind);
        CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(text, topic, tokenize='unicode61');
        CREATE TABLE IF NOT EXISTS sessions(
          id TEXT PRIMARY KEY, mode TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
          created_at REAL NOT NULL, finished_at REAL, deadline REAL, config TEXT NOT NULL,
          current_index INTEGER NOT NULL DEFAULT 0, deleted_at REAL);
        CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON sessions(deleted_at,id);
        CREATE TRIGGER IF NOT EXISTS one_active_session_insert
          BEFORE INSERT ON sessions
          WHEN NEW.status='active' AND NEW.deleted_at IS NULL
               AND EXISTS(SELECT 1 FROM sessions WHERE status='active' AND deleted_at IS NULL)
          BEGIN SELECT RAISE(ABORT, 'Esiste gia una sessione attiva'); END;
        CREATE TRIGGER IF NOT EXISTS one_active_session_update
          BEFORE UPDATE OF status,deleted_at ON sessions
          WHEN NEW.status='active' AND NEW.deleted_at IS NULL
               AND EXISTS(SELECT 1 FROM sessions WHERE status='active' AND deleted_at IS NULL AND id!=NEW.id)
          BEGIN SELECT RAISE(ABORT, 'Esiste gia una sessione attiva'); END;
        CREATE TABLE IF NOT EXISTS items(
          pk INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          position INTEGER NOT NULL, question_pk INTEGER REFERENCES questions(pk) ON DELETE SET NULL,
          revision INTEGER NOT NULL, topic TEXT NOT NULL, payload TEXT NOT NULL, answer TEXT,
          confirmed INTEGER NOT NULL DEFAULT 0, outcome TEXT, origin TEXT, original_outcome TEXT,
          graded_at REAL, reason TEXT NOT NULL DEFAULT '', UNIQUE(session_id, position));
        CREATE INDEX IF NOT EXISTS idx_items_question ON items(question_pk, revision, graded_at);
        CREATE INDEX IF NOT EXISTS idx_items_topic ON items(topic, origin, graded_at DESC);
        CREATE INDEX IF NOT EXISTS idx_items_session ON items(session_id, position);
        CREATE INDEX IF NOT EXISTS idx_items_dashboard_session
          ON items(session_id,question_pk,revision,graded_at,origin,outcome);
        CREATE TABLE IF NOT EXISTS progress(
          question_pk INTEGER PRIMARY KEY REFERENCES questions(pk) ON DELETE CASCADE,
          attempts INTEGER NOT NULL DEFAULT 0, wrong INTEGER NOT NULL DEFAULT 0,
          partial INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0,
          unresolved INTEGER NOT NULL DEFAULT 0, streak INTEGER NOT NULL DEFAULT 0,
          due REAL, last_at REAL, last_outcome TEXT);
        CREATE TABLE IF NOT EXISTS notes(
          pk INTEGER PRIMARY KEY, question_pk INTEGER REFERENCES questions(pk) ON DELETE CASCADE,
          revision INTEGER NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        PRAGMA user_version=1;
        """)
        self._ensure_runtime_objects()
        self.db.commit()

    def _ensure_runtime_objects(self):
        """Ricrea gli oggetti aggiuntivi dopo l'apertura o il ripristino di un backup."""
        self.db.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(text, topic, tokenize='unicode61');
        CREATE INDEX IF NOT EXISTS idx_questions_filter ON questions(collection_id, deleted_at, topic, kind);
        CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON sessions(deleted_at,id);
        CREATE INDEX IF NOT EXISTS idx_items_question ON items(question_pk, revision, graded_at);
        CREATE INDEX IF NOT EXISTS idx_items_topic ON items(topic, origin, graded_at DESC);
        CREATE INDEX IF NOT EXISTS idx_items_session ON items(session_id, position);
        CREATE INDEX IF NOT EXISTS idx_items_dashboard_session
          ON items(session_id,question_pk,revision,graded_at,origin,outcome);
        CREATE TRIGGER IF NOT EXISTS one_active_session_insert
          BEFORE INSERT ON sessions
          WHEN NEW.status='active' AND NEW.deleted_at IS NULL
               AND EXISTS(SELECT 1 FROM sessions WHERE status='active' AND deleted_at IS NULL)
          BEGIN SELECT RAISE(ABORT, 'Esiste gia una sessione attiva'); END;
        CREATE TRIGGER IF NOT EXISTS one_active_session_update
          BEFORE UPDATE OF status,deleted_at ON sessions
          WHEN NEW.status='active' AND NEW.deleted_at IS NULL
               AND EXISTS(SELECT 1 FROM sessions WHERE status='active' AND deleted_at IS NULL AND id!=NEW.id)
          BEGIN SELECT RAISE(ABORT, 'Esiste gia una sessione attiva'); END;
        """)

    def _rebuild_search_index(self):
        with self.transaction():
            self.db.execute("DELETE FROM questions_fts")
            for row in self.db.execute("SELECT pk,payload FROM questions"):
                question = json.loads(row["payload"])
                self._index_question(row["pk"], question)

    @staticmethod
    def _validate_database(connection, cancelled=None, progress=None):
        """Controlla i dati che la verifica strutturale di SQLite non può interpretare."""
        try:
            if (
                connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or connection.execute("PRAGMA user_version").fetchone()[0] != 1
            ):
                raise ValueError("Il database del backup è danneggiato o incompatibile.")
            for table in (
                "collections",
                "questions",
                "sessions",
                "items",
                "progress",
                "notes",
                "settings",
            ):
                connection.execute(f"SELECT * FROM {table} LIMIT 0")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Relazioni del backup non valide.")
            if (
                connection.execute(
                    "SELECT count(*) FROM sessions WHERE status='active' AND deleted_at IS NULL"
                ).fetchone()[0]
                > 1
            ):
                raise ValueError("Il backup contiene più prove attive contemporaneamente.")

            for row in connection.execute("SELECT payload,kind,topic,revision FROM questions"):
                question = json.loads(row["payload"])
                if (
                    question_errors(question)
                    or question["tipo"] != row["kind"]
                    or question.get("argomento", UNTAGGED) != row["topic"]
                    or row["revision"] < 1
                ):
                    raise ValueError("Il backup contiene domande non valide.")

            session_count = connection.execute("SELECT count(*) FROM sessions").fetchone()[0]
            for row in connection.execute("SELECT mode,status,config,current_index FROM sessions"):
                config = json.loads(row["config"])
                required = {
                    "correct_points",
                    "wrong_points",
                    "omitted_points",
                    "shuffle_options",
                    "minutes",
                }
                if (
                    row["mode"] not in ("allenamento", "esame", "intelligente")
                    or row["status"] not in ("active", "submitted")
                    or not isinstance(config, dict)
                    or not required.issubset(config)
                    or not isinstance(config["shuffle_options"], bool)
                    or row["current_index"] < 0
                ):
                    raise ValueError("Il backup contiene una configurazione di prova non valida.")
                for key in ("correct_points", "wrong_points", "omitted_points", "minutes"):
                    value = config[key]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        raise ValueError("Il backup contiene punteggi o timer non validi.")

            total_items = connection.execute("SELECT count(*) FROM items").fetchone()[0]
            valid_outcomes = {None, "corretta", "parziale", "sbagliata", "omessa", "da_valutare"}
            valid_origins = {None, "automatico", "manuale"}
            for index, row in enumerate(
                connection.execute(
                    """SELECT payload,answer,confirmed,outcome,origin,original_outcome,
                              graded_at,revision,topic FROM items"""
                )
            ):
                if cancelled and cancelled():
                    raise ValueError("Ripristino annullato prima di modificare i dati.")
                question = json.loads(row["payload"])
                if question_errors(question) or row["revision"] < 1 or not row["topic"]:
                    raise ValueError("Il backup contiene una copia storica non valida.")
                answer = json.loads(row["answer"]) if row["answer"] is not None else None
                evaluate(question, answer)
                if (
                    row["confirmed"] not in (0, 1)
                    or row["outcome"] not in valid_outcomes
                    or row["origin"] not in valid_origins
                    or row["original_outcome"] not in valid_outcomes
                    or (row["confirmed"] and row["outcome"] is None)
                    or (row["outcome"] is not None and row["graded_at"] is None)
                ):
                    raise ValueError("Il backup contiene un risultato storico non valido.")
                if progress and index % 1000 == 0:
                    progress(80 + int(20 * (index + 1) / max(1, total_items)))

            for row in connection.execute("SELECT value FROM settings"):
                json.loads(row["value"])
            if progress and not total_items:
                progress(100)
            return session_count
        except (json.JSONDecodeError, KeyError, TypeError, sqlite3.Error) as exc:
            raise ValueError("Il contenuto del backup non è valido o compatibile.") from exc
        except ValueError:
            raise

    def _connect(self):
        self.db = sqlite3.connect(self.path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=15000")

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def collections(self, trash=False):
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT c.*, COUNT(q.pk) AS count
          FROM collections c LEFT JOIN questions q ON q.collection_id=c.id AND q.deleted_at IS NULL
          WHERE (c.deleted_at IS NOT NULL)=? GROUP BY c.id ORDER BY c.title COLLATE NOCASE""",
                (int(trash),),
            )
        ]

    def topics(self):
        return [
            r[0]
            for r in self.db.execute("""SELECT DISTINCT q.topic FROM questions q JOIN collections c ON c.id=q.collection_id
          WHERE q.deleted_at IS NULL AND c.deleted_at IS NULL AND c.archived=0 ORDER BY q.topic""")
        ]

    def preview_import(self, raw, target=None):
        bank = validate_bank(raw)
        collection = target or bank["id"]
        old = {
            r["external_id"]: r
            for r in self.db.execute(
                "SELECT * FROM questions WHERE collection_id=? AND deleted_at IS NULL",
                (collection,),
            )
        }
        result = Counter(new=0, changed=0, identical=0, removed=0)
        for q in bank["domande"]:
            previous = old.pop(q["id"], None)
            result[
                "new"
                if previous is None
                else "identical"
                if json.loads(previous["payload"]) == q
                else "changed"
            ] += 1
        result["removed"] = len(old)
        return dict(result)

    def import_bank(
        self,
        raw,
        mode="create",
        target=None,
        keep_progress=True,
        source: Path | None = None,
        cancelled=None,
        progress=None,
    ):
        bank = validate_bank(raw)
        cid = target or bank["id"]
        if mode not in ("create", "update", "replace"):
            raise ValueError("Operazione di importazione non valida.")
        exists = self.db.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
        if mode == "create" and exists:
            raise ValueError(
                "Esiste già una raccolta con questo ID. Scegli Aggiorna/Sostituisci oppure un ID nuovo."
            )
        if mode != "create" and not exists:
            raise ValueError("Seleziona la raccolta da aggiornare o sostituire.")
        if exists and exists["deleted_at"] is not None:
            raise ValueError("La raccolta è nel cestino: ripristinala prima di aggiornarla.")
        if mode == "replace":
            self.backup(label="prima-sostituzione")
        source_name = None
        if source:
            source_name = file_digest(source) + Path(source).suffix.lower()
            dest = self.data / "sources" / source_name
            if not dest.exists():
                shutil.copyfile(source, dest)
        now = time.time()
        with self.transaction():
            if mode == "create":
                self.db.execute(
                    "INSERT INTO collections(id,title,source) VALUES(?,?,?)",
                    (cid, bank["titolo"], source_name),
                )
            else:
                self.db.execute(
                    "UPDATE collections SET title=?, source=COALESCE(?,source) WHERE id=?",
                    (bank["titolo"], source_name, cid),
                )
            old = {
                r["external_id"]: r
                for r in self.db.execute("SELECT * FROM questions WHERE collection_id=?", (cid,))
            }
            incoming = set()
            for i, q in enumerate(bank["domande"]):
                if cancelled and cancelled():
                    raise ValueError("Importazione annullata: nessuna modifica applicata.")
                incoming.add(q["id"])
                existing = old.get(q["id"])
                fp = fingerprint(q)
                if existing:
                    changed = fp != existing["fingerprint"]
                    reset = (
                        now
                        if not keep_progress or existing["deleted_at"] is not None
                        else existing["reset_at"]
                    )
                    self.db.execute(
                        """UPDATE questions SET payload=?, fingerprint=?, topic=?,kind=?,revision=?,deleted_at=NULL,reset_at=? WHERE pk=?""",
                        (
                            dumps(q),
                            fp,
                            q["argomento"],
                            q["tipo"],
                            existing["revision"] + int(changed),
                            reset,
                            existing["pk"],
                        ),
                    )
                    pk = existing["pk"]
                    # L'argomento può cambiare, mentre le copie storiche restano inalterate.
                    self.db.execute(
                        "UPDATE items SET topic=? WHERE question_pk=?", (q["argomento"], pk)
                    )
                    self._refresh_progress(pk)
                else:
                    pk = self.db.execute(
                        "INSERT INTO questions(collection_id,external_id,payload,fingerprint,topic,kind) VALUES(?,?,?,?,?,?)",
                        (cid, q["id"], dumps(q), fp, q["argomento"], q["tipo"]),
                    ).lastrowid
                self._index_question(pk, q)
                if progress and i % 100 == 0:
                    progress(int(100 * (i + 1) / len(bank["domande"])))
            if mode == "replace":
                for key, row in old.items():
                    if key not in incoming:
                        self.db.execute(
                            "UPDATE questions SET deleted_at=? WHERE pk=?", (now, row["pk"])
                        )
        return cid

    def _index_question(self, pk, q):
        self.db.execute("DELETE FROM questions_fts WHERE rowid=?", (pk,))
        self.db.execute(
            "INSERT INTO questions_fts(rowid,text,topic) VALUES(?,?,?)",
            (pk, q["testo"], q.get("argomento", UNTAGGED)),
        )

    def question(self, pk):
        row = self.db.execute("SELECT * FROM questions WHERE pk=?", (pk,)).fetchone()
        if not row:
            raise ValueError("Domanda non disponibile.")
        result = dict(row)
        result["question"] = json.loads(result["payload"])
        return result

    def save_question(self, cid, q, pk=None):
        q = copy.deepcopy(q)
        q["argomento"] = q.get("argomento", "").strip() or UNTAGGED
        errors = question_errors(q)
        if errors:
            raise ValueError("\n".join(errors))
        if pk:
            previous = self.question(pk)
            if q["id"] != previous["external_id"]:
                raise ValueError("L'identificatore di una domanda esistente non è modificabile.")
        collection = self.db.execute("SELECT title FROM collections WHERE id=?", (cid,)).fetchone()
        if not collection:
            raise ValueError("Raccolta non disponibile.")
        self.import_bank(
            {"versione_schema": 2, "id": cid, "titolo": collection[0], "domande": [q]},
            "update",
            cid,
        )

    def create_collection(self, title):
        title = title.strip()
        if not title:
            raise ValueError("Inserisci un titolo.")
        cid = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO collections(id,title) VALUES(?,?)", (cid, title))
        return cid

    def set_topic(self, pks, topic):
        topic = topic.strip() or UNTAGGED
        with self.transaction():
            for pk in pks:
                q = self.question(pk)["question"]
                q["argomento"] = topic
                self.db.execute(
                    "UPDATE questions SET topic=?,payload=? WHERE pk=?", (topic, dumps(q), pk)
                )
                self.db.execute("UPDATE items SET topic=? WHERE question_pk=?", (topic, pk))
                self._index_question(pk, q)

    def _filter(
        self, collection=None, topic=None, kinds=None, search="", favorite=False, trash=False
    ):
        conditions = [
            "c.deleted_at IS NULL",
            "c.archived=0",
            "q.deleted_at IS NOT NULL" if trash else "q.deleted_at IS NULL",
        ]
        values = []
        if collection:
            conditions[1] = "1=1"  # Le raccolte archiviate restano modificabili.
            conditions.append("q.collection_id=?")
            values.append(collection)
        if topic:
            conditions.append("q.topic=?")
            values.append(topic)
        if kinds:
            conditions.append("q.kind IN (" + ",".join("?" for _ in kinds) + ")")
            values.extend(kinds)
        if favorite:
            conditions.append("q.favorite=1")
        if search.strip():
            tokens = ['"' + token.replace('"', '""') + '"*' for token in search.strip().split()]
            conditions.append(
                "q.pk IN (SELECT rowid FROM questions_fts WHERE questions_fts MATCH ?)"
            )
            values.append(" AND ".join(tokens))
        return " AND ".join(conditions), values

    def list_questions(self, limit=50, offset=0, **filters):
        where, params = self._filter(**filters)
        count = self.db.execute(
            f"SELECT count(*) FROM questions q JOIN collections c ON c.id=q.collection_id WHERE {where}",
            params,
        ).fetchone()[0]
        rows = self.db.execute(
            f"""SELECT q.*,c.title AS collection_title FROM questions q JOIN collections c ON c.id=q.collection_id
          WHERE {where} ORDER BY q.pk LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        )
        return [dict(r) for r in rows], count

    def export_bank(self, cid):
        row = self.db.execute("SELECT title FROM collections WHERE id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("Raccolta non disponibile.")
        questions = [
            json.loads(r[0])
            for r in self.db.execute(
                "SELECT payload FROM questions WHERE collection_id=? AND deleted_at IS NULL ORDER BY pk",
                (cid,),
            )
        ]
        if not questions:
            raise ValueError("Non ci sono domande da esportare.")
        return {"versione_schema": 2, "id": cid, "titolo": row[0], "domande": questions}

    def source_path(self, cid):
        row = self.db.execute("SELECT source FROM collections WHERE id=?", (cid,)).fetchone()
        return self.data / "sources" / Path(row[0]).name if row and row[0] else None

    def set_favorite(self, pk, value):
        with self.db:
            self.db.execute("UPDATE questions SET favorite=? WHERE pk=?", (int(value), pk))

    def collection_action(self, cid, action, remove_history=False):
        with self.transaction():
            if action == "trash":
                self.db.execute(
                    "UPDATE collections SET deleted_at=? WHERE id=?", (time.time(), cid)
                )
            elif action == "restore":
                self.db.execute("UPDATE collections SET deleted_at=NULL WHERE id=?", (cid,))
            elif action in ("archive", "unarchive"):
                self.db.execute(
                    "UPDATE collections SET archived=? WHERE id=?", (int(action == "archive"), cid)
                )
            elif action == "purge":
                row = self.db.execute(
                    "SELECT deleted_at FROM collections WHERE id=?", (cid,)
                ).fetchone()
                if not row or row[0] is None:
                    raise ValueError("Prima sposta la raccolta nel cestino.")
                if remove_history:
                    # Una sessione mista va rimossa per intero per mantenere coerenti i totali.
                    self.db.execute(
                        "DELETE FROM sessions WHERE id IN (SELECT i.session_id FROM items i JOIN questions q ON q.pk=i.question_pk WHERE q.collection_id=?)",
                        (cid,),
                    )
                ids = [
                    r[0]
                    for r in self.db.execute(
                        "SELECT pk FROM questions WHERE collection_id=?", (cid,)
                    )
                ]
                for pk in ids:
                    self.db.execute("DELETE FROM questions_fts WHERE rowid=?", (pk,))
                self.db.execute("DELETE FROM collections WHERE id=?", (cid,))
                if remove_history:
                    self._refresh_all_progress()
            else:
                raise ValueError("Operazione non valida.")

    def rename_collection(self, cid, title):
        if not title.strip():
            raise ValueError("Inserisci un titolo.")
        with self.db:
            self.db.execute("UPDATE collections SET title=? WHERE id=?", (title.strip(), cid))

    def question_action(self, pks, action):
        if action not in ("trash", "restore", "purge"):
            raise ValueError("Operazione non valida.")
        with self.transaction():
            for pk in pks:
                if action == "trash":
                    self.db.execute(
                        "UPDATE questions SET deleted_at=? WHERE pk=?", (time.time(), pk)
                    )
                elif action == "restore":
                    self.db.execute("UPDATE questions SET deleted_at=NULL WHERE pk=?", (pk,))
                elif action == "purge":
                    self.db.execute(
                        "DELETE FROM questions_fts WHERE rowid=? AND EXISTS(SELECT 1 FROM questions WHERE pk=? AND deleted_at IS NOT NULL)",
                        (pk, pk),
                    )
                    self.db.execute(
                        "DELETE FROM questions WHERE pk=? AND deleted_at IS NOT NULL", (pk,)
                    )

    def reset_learning(self, cid=None):
        self.backup(label="prima-azzeramento")
        with self.transaction():
            if cid:
                self.db.execute("UPDATE collections SET reset_at=? WHERE id=?", (time.time(), cid))
                self.db.execute(
                    "DELETE FROM progress WHERE question_pk IN (SELECT pk FROM questions WHERE collection_id=?)",
                    (cid,),
                )
            else:
                self.db.execute("UPDATE collections SET reset_at=?", (time.time(),))
                self.db.execute("DELETE FROM progress")

    def _refresh_progress(self, pk):
        q = self.db.execute(
            "SELECT q.*,c.reset_at AS collection_reset FROM questions q JOIN collections c ON c.id=q.collection_id WHERE q.pk=?",
            (pk,),
        ).fetchone()
        if not q:
            return
        rows = self.db.execute(
            """SELECT i.* FROM items i JOIN sessions s ON s.id=i.session_id
          WHERE i.question_pk=? AND i.revision=? AND i.graded_at>? AND s.deleted_at IS NULL
          AND i.outcome IS NOT NULL AND i.outcome!='da_valutare' ORDER BY i.graded_at,i.pk""",
            (pk, q["revision"], max(q["reset_at"], q["collection_reset"])),
        ).fetchall()
        counts = Counter(r["outcome"] for r in rows)
        had_error = False
        streak = 0
        unresolved = False
        due = None
        last_session = None
        intervals = [1, 3, 7, 14, 30]
        for r in rows:
            if r["outcome"] in ("sbagliata", "parziale", "omessa"):
                had_error, unresolved, streak = True, True, 0
                due = r["graded_at"] + 86400
                last_session = None
            elif had_error and r["session_id"] != last_session:
                streak += 1
                last_session = r["session_id"]
                unresolved = streak < 2
                due = r["graded_at"] + 86400 * intervals[min(streak - 1, 4)]
        self.db.execute(
            """INSERT OR REPLACE INTO progress(question_pk,attempts,wrong,partial,correct,unresolved,streak,due,last_at,last_outcome)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                pk,
                len(rows),
                counts["sbagliata"],
                counts["parziale"],
                counts["corretta"],
                int(unresolved),
                streak,
                due,
                rows[-1]["graded_at"] if rows else None,
                rows[-1]["outcome"] if rows else None,
            ),
        )

    def _refresh_all_progress(self):
        self.db.execute("DELETE FROM progress")
        for row in self.db.execute(
            "SELECT DISTINCT question_pk FROM items WHERE question_pk IS NOT NULL"
        ).fetchall():
            self._refresh_progress(row[0])

    def analytics(self):
        active = "q.deleted_at IS NULL AND c.deleted_at IS NULL AND c.archived=0"
        groups = self.db.execute(
            f"""SELECT DISTINCT q.topic FROM questions q JOIN collections c ON c.id=q.collection_id WHERE {active} AND q.topic!=?""",
            (UNTAGGED,),
        ).fetchall()
        stats = []
        for group in groups:
            for origin in ("automatico", "manuale"):
                rows = self.db.execute(
                    f"""SELECT i.outcome,i.question_pk,i.graded_at FROM items i
                  JOIN questions q ON q.pk=i.question_pk JOIN collections c ON c.id=q.collection_id JOIN sessions s ON s.id=i.session_id
                  WHERE i.topic=? AND i.origin=? AND {active} AND s.deleted_at IS NULL
                  AND i.revision=q.revision AND i.graded_at>MAX(q.reset_at,c.reset_at)
                  AND i.outcome IN ('corretta','parziale','sbagliata') ORDER BY i.graded_at DESC,i.pk DESC LIMIT 20""",
                    (group[0], origin),
                ).fetchall()
                if not rows:
                    continue

                def difficulty(sample):
                    return sum(1 - CREDITS[row["outcome"]] for row in sample) / len(sample)

                enough = len(rows) >= 5 and len({r["question_pk"] for r in rows}) >= 3
                value = difficulty(rows)
                trend = "Dati insufficienti"
                if len(rows) == 20:
                    delta = difficulty(rows[:10]) - difficulty(rows[10:])
                    trend = (
                        "In miglioramento"
                        if delta <= -0.1 + 1e-9
                        else "Da rivedere"
                        if delta >= 0.1 - 1e-9
                        else "Stabile"
                    )
                stats.append(
                    {
                        "topic": group[0],
                        "origin": origin,
                        "count": len(rows),
                        "distinct": len({r["question_pk"] for r in rows}),
                        "difficulty": value,
                        "weak": enough and value >= 0.4,
                        "enough": enough,
                        "trend": trend,
                        "counts": dict(Counter(r["outcome"] for r in rows)),
                    }
                )
        return sorted(stats, key=lambda x: (-x["weak"], -x["difficulty"], x["topic"]))

    def choose_questions(self, count, mode, filters, rng=None):
        rng = rng or random.Random()
        where, params = self._filter(**filters)
        rows = [
            dict(r)
            for r in self.db.execute(
                f"""SELECT q.pk,q.topic,q.kind,p.attempts,p.wrong,p.partial,p.unresolved,p.due,p.last_at
          FROM questions q JOIN collections c ON c.id=q.collection_id LEFT JOIN progress p ON p.question_pk=q.pk
          WHERE {where} AND c.archived=0""",
                params,
            )
        ]
        count = min(count, len(rows))
        if not count:
            raise ValueError("Nessuna domanda disponibile con questi filtri.")
        if mode != "intelligente":
            return [(r["pk"], "Selezione casuale") for r in rng.sample(rows, count)]
        # Il rapporto separa le valutazioni automatiche da quelle manuali. La selezione
        # lavora per argomento perché una risposta breve può essere rettificata in seguito.
        weak_topics = {s["topic"] for s in self.analytics() if s["weak"]}
        weak = [r for r in rows if r["topic"] in weak_topics]
        due = [r for r in rows if r["due"] is not None and r["due"] <= time.time()]
        rng.shuffle(weak)
        weak.sort(key=lambda r: (-(r["unresolved"] or 0), -(r["wrong"] or 0), r["last_at"] or 0))
        due.sort(key=lambda r: r["due"])
        selected = []
        used = set()

        def take(pool, n, reason):
            taken = 0
            for r in pool:
                if taken >= n:
                    break
                if r["pk"] not in used:
                    selected.append(
                        (
                            r["pk"],
                            "Errore ricorrente"
                            if reason == "Argomento da rinforzare" and (r["wrong"] or 0) >= 2
                            else reason,
                        )
                    )
                    used.add(r["pk"])
                    taken += 1

        weak_slots = min(count, math.ceil(count * 0.6))
        take(weak, weak_slots, "Argomento da rinforzare")
        due_slots = min(count - len(selected), math.ceil(count * 0.2))
        take(due, due_slots, "Ripasso previsto")
        # La rotazione degli argomenti bilancia la prima sessione di chi non ha uno storico.
        topics = {}
        rng.shuffle(rows)
        rows.sort(key=lambda r: ((r["attempts"] or 0) > 0, r["attempts"] or 0))
        for r in rows:
            topics.setdefault(r["topic"], []).append(r)
        balanced = []
        while topics:
            for topic in list(topics):
                balanced.append(topics[topic].pop(0))
                if not topics[topic]:
                    del topics[topic]
        take(balanced, count - len(selected), "Esplorazione e consolidamento")
        rng.shuffle(selected)
        return selected

    def create_session(self, mode, count=20, filters=None, config=None):
        if mode not in ("allenamento", "esame", "intelligente"):
            raise ValueError("Modalità non valida.")
        if not isinstance(count, int) or count < 1 or count > 1000:
            raise ValueError("Scegli da 1 a 1000 domande per sessione.")
        if self.active_session():
            raise ValueError("Riprendi o termina prima la sessione in corso.")
        config = {
            "correct_points": 1.0,
            "wrong_points": 0.0,
            "omitted_points": 0.0,
            "shuffle_options": False,
            "minutes": 0,
            **(config or {}),
        }
        for key in ("correct_points", "wrong_points", "omitted_points", "minutes"):
            if not isinstance(config[key], (float, int)) or not math.isfinite(config[key]):
                raise ValueError("Punteggi e durata devono essere numeri validi.")
        if config["correct_points"] <= 0 or config["minutes"] < 0:
            raise ValueError("Il punteggio corretto deve essere positivo e la durata non negativa.")
        chosen = self.choose_questions(count, mode, filters or {})
        now, sid = time.time(), uuid.uuid4().hex
        deadline = now + config["minutes"] * 60 if mode == "esame" and config["minutes"] else None
        with self.transaction():
            # BEGIN IMMEDIATE rende seriale questo controllo tra più istanze dell'app.
            if self.active_session():
                raise ValueError("Riprendi o termina prima la sessione in corso.")
            self.db.execute(
                "INSERT INTO sessions(id,mode,created_at,deadline,config) VALUES(?,?,?,?,?)",
                (sid, mode, now, deadline, dumps(config)),
            )
            for position, (pk, reason) in enumerate(chosen):
                row = self.question(pk)
                q = row["question"]
                if config["shuffle_options"] and "risposte" in q:
                    random.shuffle(q["risposte"])
                self.db.execute(
                    "INSERT INTO items(session_id,position,question_pk,revision,topic,payload,reason) VALUES(?,?,?,?,?,?,?)",
                    (sid, position, pk, row["revision"], q["argomento"], dumps(q), reason),
                )
        return sid

    def active_session(self):
        row = self.db.execute(
            "SELECT id FROM sessions WHERE status='active' AND deleted_at IS NULL ORDER BY created_at LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def session(self, sid):
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            raise ValueError("Sessione non disponibile.")
        result = dict(row)
        result["config"] = json.loads(result["config"])
        result["items"] = []
        for r in self.db.execute(
            "SELECT * FROM items WHERE session_id=? ORDER BY position", (sid,)
        ):
            item = dict(r)
            item["question"] = json.loads(item["payload"])
            item["answer"] = json.loads(item["answer"]) if item["answer"] is not None else None
            result["items"].append(item)
        return result

    def check_deadline(self, sid):
        s = self.db.execute("SELECT status,deadline FROM sessions WHERE id=?", (sid,)).fetchone()
        if s and s["status"] == "active" and s["deadline"] and s["deadline"] <= time.time():
            self.submit(sid)
            return True
        return False

    def save_answer(self, sid, position, answer, confirm=False):
        if self.check_deadline(sid):
            raise ValueError("Il tempo è scaduto: la prova è stata consegnata.")
        session = self.session(sid)
        if session["status"] != "active":
            raise ValueError("La prova è già stata consegnata.")
        item = session["items"][position]
        if item["confirmed"]:
            raise ValueError("La risposta è già stata confermata.")
        result = evaluate(item["question"], answer)
        confirmed = bool(confirm and session["mode"] != "esame")
        if confirmed and result.outcome == "omessa":
            raise ValueError("Inserisci una risposta oppure usa Avanti per saltare la domanda.")
        with self.transaction():
            self.db.execute(
                """UPDATE items SET answer=?,confirmed=?,outcome=?,origin=?,original_outcome=?,graded_at=? WHERE pk=?""",
                (
                    dumps(answer),
                    int(confirmed),
                    result.outcome if confirmed else None,
                    result.origin if confirmed else None,
                    result.outcome if confirmed else None,
                    time.time() if confirmed else None,
                    item["pk"],
                ),
            )
            self.db.execute("UPDATE sessions SET current_index=? WHERE id=?", (position, sid))
            if confirmed and item["question_pk"]:
                self._refresh_progress(item["question_pk"])

    def submit(self, sid):
        session = self.session(sid)
        if session["status"] != "active":
            return
        with self.transaction():
            now = time.time()
            for item in session["items"]:
                if not item["confirmed"]:
                    # In allenamento una bozza non conta come tentativo finché non viene confermata.
                    answer = item["answer"] if session["mode"] == "esame" else None
                    result = evaluate(item["question"], answer)
                    self.db.execute(
                        "UPDATE items SET confirmed=1,outcome=?,origin=?,original_outcome=?,graded_at=? WHERE pk=?",
                        (result.outcome, result.origin, result.outcome, now, item["pk"]),
                    )
                if item["question_pk"]:
                    self._refresh_progress(item["question_pk"])
            self.db.execute(
                "UPDATE sessions SET status='submitted',finished_at=? WHERE id=?", (now, sid)
            )

    def manual_grade(self, sid, position, outcome):
        if outcome not in ("corretta", "parziale", "sbagliata"):
            raise ValueError("Valutazione non valida.")
        s = self.session(sid)
        item = s["items"][position]
        if not item["confirmed"] or (s["mode"] == "esame" and s["status"] == "active"):
            raise ValueError("Conferma la risposta o consegna la prova prima della valutazione.")
        if evaluate(item["question"], item["answer"]).outcome == "omessa":
            raise ValueError("Una risposta omessa non può essere valutata manualmente.")
        if item["question"]["tipo"] not in ("aperta_breve", "aperta_libera"):
            raise ValueError("La valutazione manuale è disponibile per le risposte aperte.")
        with self.transaction():
            self.db.execute(
                "UPDATE items SET outcome=?,origin='manuale' WHERE pk=?", (outcome, item["pk"])
            )
            if item["question_pk"]:
                self._refresh_progress(item["question_pk"])

    def session_summary(self, sid):
        session = self.session(sid)
        counts = Counter(i["outcome"] or "non_confermata" for i in session["items"])
        points = sum(score(i["outcome"], session["config"]) or 0 for i in session["items"])
        return {
            "counts": dict(counts),
            "points": points,
            "total": len(session["items"]),
            "pending": counts["da_valutare"] + counts["non_confermata"],
            "correct_percent": 100 * counts["corretta"] / max(1, len(session["items"])),
        }

    def sessions(self, trash=False, limit=200, offset=0):
        if limit < 1 or offset < 0:
            raise ValueError("Paginazione non valida.")
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT s.*,count(i.pk) AS total,
          sum(CASE WHEN i.outcome='corretta' THEN 1 ELSE 0 END) AS correct,
          sum(CASE WHEN i.outcome='da_valutare' THEN 1 ELSE 0 END) AS pending
          FROM sessions s LEFT JOIN items i ON i.session_id=s.id WHERE (s.deleted_at IS NOT NULL)=?
          GROUP BY s.id ORDER BY s.created_at DESC LIMIT ? OFFSET ?""",
                (int(trash), limit, offset),
            )
        ]

    def session_count(self, trash=False):
        return self.db.execute(
            "SELECT count(*) FROM sessions WHERE (deleted_at IS NOT NULL)=?", (int(trash),)
        ).fetchone()[0]

    def session_action(self, sid, action):
        with self.transaction():
            session = self.db.execute(
                "SELECT status,deleted_at FROM sessions WHERE id=?", (sid,)
            ).fetchone()
            if not session:
                raise ValueError("Prova non disponibile.")
            pks = [
                r[0]
                for r in self.db.execute(
                    "SELECT question_pk FROM items WHERE session_id=? AND question_pk IS NOT NULL",
                    (sid,),
                )
            ]
            if action == "trash":
                self.db.execute("UPDATE sessions SET deleted_at=? WHERE id=?", (time.time(), sid))
            elif action == "restore":
                if self.active_session() and session["status"] == "active":
                    raise ValueError(
                        "Termina la sessione attiva prima di ripristinare questa prova."
                    )
                self.db.execute("UPDATE sessions SET deleted_at=NULL WHERE id=?", (sid,))
            elif action == "purge":
                if session["deleted_at"] is None:
                    raise ValueError("Prima sposta la prova nel cestino.")
                self.db.execute("DELETE FROM sessions WHERE id=?", (sid,))
            else:
                raise ValueError("Operazione non valida.")
            for pk in pks:
                self._refresh_progress(pk)

    def question_history(self, pk):
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT i.*,s.mode FROM items i JOIN sessions s ON s.id=i.session_id
          WHERE i.question_pk=? AND s.deleted_at IS NULL AND i.confirmed=1 ORDER BY i.graded_at DESC LIMIT 100""",
                (pk,),
            )
        ]

    def notes(self, pk, revision):
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM notes WHERE question_pk=? AND revision=? ORDER BY created_at DESC",
                (pk, revision),
            )
        ]

    def add_note(self, pk, revision, text, source="ChatGPT · riportata dall'utente"):
        if not text.strip():
            raise ValueError("La spiegazione non può essere vuota.")
        with self.db:
            self.db.execute(
                "INSERT INTO notes(question_pk,revision,text,source,created_at) VALUES(?,?,?,?,?)",
                (pk, revision, text.strip(), source, time.time()),
            )

    def delete_note(self, pk):
        with self.db:
            self.db.execute("DELETE FROM notes WHERE pk=?", (pk,))

    def get_setting(self, key, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def dashboard(self):
        active = "q.deleted_at IS NULL AND c.deleted_at IS NULL AND c.archived=0"
        summary = dict(
            self.db.execute(
                f"""SELECT count(*) AS questions,coalesce(sum(p.attempts),0) AS attempts,
          coalesce(sum(p.unresolved),0) AS unresolved,
          coalesce(sum(CASE WHEN p.due<=? THEN 1 ELSE 0 END),0) AS due
          FROM questions q JOIN collections c ON c.id=q.collection_id LEFT JOIN progress p ON p.question_pk=q.pk
          WHERE {active}""",
                (time.time(),),
            ).fetchone()
        )
        totals = [
            dict(r)
            for r in self.db.execute(f"""SELECT q.kind,i.origin,i.outcome,count(*) AS count
          FROM sessions s
          CROSS JOIN items i INDEXED BY idx_items_dashboard_session
          CROSS JOIN questions q
          CROSS JOIN collections c
          WHERE i.session_id=s.id AND q.pk=i.question_pk AND c.id=q.collection_id
          AND {active} AND s.deleted_at IS NULL AND i.revision=q.revision
          AND i.graded_at>MAX(q.reset_at,c.reset_at)
          GROUP BY q.kind,i.origin,i.outcome""")
        ]
        recurring = [
            dict(r)
            for r in self.db.execute(f"""SELECT q.pk,q.payload,q.topic,p.* FROM questions q
          JOIN collections c ON c.id=q.collection_id JOIN progress p ON p.question_pk=q.pk
          WHERE {active} AND p.wrong>=2 ORDER BY p.unresolved DESC,p.wrong DESC LIMIT 30""")
        ]
        return {
            "summary": summary,
            "topics": self.analytics(),
            "totals": totals,
            "recurring": recurring,
        }

    def rebuild_learning(self):
        with self.transaction():
            self._refresh_all_progress()

    def set_setting(self, key, value):
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, dumps(value))
            )

    def backup(self, destination=None, label="backup", progress=None, cancelled=None):
        path = (
            Path(destination)
            if destination
            else self.root
            / "backups"
            / (time.strftime("%Y%m%d-%H%M%S") + "-" + label + "-" + uuid.uuid4().hex[:6] + ".zip")
        )
        if path.resolve() == self.path.resolve():
            raise ValueError("Il backup non può sovrascrivere il database.")
        with tempfile.TemporaryDirectory(dir=self.root / "tmp", prefix="backup-") as temp:
            snapshot = Path(temp) / "quiz.sqlite3"
            target = sqlite3.connect(snapshot)
            try:
                self.db.backup(target)
            finally:
                target.close()
            staging = Path(temp) / "backup.zip"
            with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("manifest.json", dumps({"format": "QuizSimulatorBackup", "version": 1}))
                z.write(snapshot, "quiz.sqlite3")
                sources = list((self.data / "sources").glob("*"))
                for i, source in enumerate(sources):
                    if cancelled and cancelled():
                        raise ValueError("Backup annullato.")
                    if source.is_file():
                        z.write(source, "sources/" + source.name)
                    if progress:
                        progress(int(100 * (i + 1) / max(1, len(sources))))
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging, path)
        return path

    def restore_backup(self, path, progress=None, cancelled=None):
        # Ogni voce viene verificata prima di toccare l'archivio; extractall() non viene usato.
        with tempfile.TemporaryDirectory(dir=self.root / "tmp", prefix="restore-") as temp:
            temp = Path(temp)
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if (
                    len(set(names)) != len(names)
                    or "manifest.json" not in names
                    or "quiz.sqlite3" not in names
                ):
                    raise ValueError("Backup incompleto o con voci duplicate.")
                if sum(info.file_size for info in z.infolist()) > 4 * 1024**3:
                    raise ValueError("Backup superiore al limite di ripristino di 4 GB.")
                for name in names:
                    valid_source = (
                        name.startswith("sources/")
                        and len(Path(name).parts) == 2
                        and re.fullmatch(r"[0-9a-f]{64}\.(json|pdf)", Path(name).name) is not None
                    )
                    if name not in ("manifest.json", "quiz.sqlite3") and not valid_source:
                        raise ValueError("Il backup contiene percorsi non ammessi.")
                    if "\\" in name or ":" in name or ".." in Path(name).parts:
                        raise ValueError("Il backup contiene percorsi non ammessi.")
                manifest = json.loads(z.read("manifest.json"))
                if manifest != {"format": "QuizSimulatorBackup", "version": 1}:
                    raise ValueError("Formato backup non supportato.")
                for i, name in enumerate(names):
                    if cancelled and cancelled():
                        raise ValueError("Ripristino annullato prima di modificare i dati.")
                    out = temp / name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(name) as src, out.open("wb") as dest:
                        shutil.copyfileobj(src, dest)
                    if progress:
                        progress(int(80 * (i + 1) / len(names)))
            source_dir = temp / "sources"
            source_names = set()
            if source_dir.exists():
                for source in source_dir.iterdir():
                    digest = file_digest(source)
                    if digest != source.stem:
                        raise ValueError("Una fonte inclusa nel backup è stata alterata.")
                    source_names.add(source.name)
            check = sqlite3.connect(temp / "quiz.sqlite3")
            check.row_factory = sqlite3.Row
            try:
                self._validate_database(check, cancelled, progress)
                referenced_sources = {
                    row[0]
                    for row in check.execute(
                        "SELECT DISTINCT source FROM collections WHERE source IS NOT NULL"
                    )
                }
                if not referenced_sources.issubset(source_names):
                    raise ValueError("Il backup non contiene tutte le fonti dichiarate.")
            finally:
                check.close()
            safety = self.backup(label="prima-ripristino")
            # Le fonti identificate dall'hash sono immutabili: anticiparne la copia può
            # lasciare soltanto un file inutilizzato.
            if source_dir.exists():
                for f in source_dir.iterdir():
                    shutil.copyfile(f, self.data / "sources" / f.name)
            source_db = sqlite3.connect(temp / "quiz.sqlite3")
            try:
                source_db.backup(self.db)
            finally:
                source_db.close()
            self.db.execute("PRAGMA foreign_keys=ON")
            self._ensure_runtime_objects()
            self._rebuild_search_index()
            return safety
