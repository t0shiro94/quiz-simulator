import copy
import json
import random
import sqlite3
import threading
import time
import zipfile

import pytest

from quiz_simulator.storage import Store


def answer_session(store, kind, answer, manual=None, mode="allenamento"):
    sid = store.create_session(mode, 1, {"kinds": [kind]})
    store.save_answer(sid, 0, answer, True)
    if manual:
        store.manual_grade(sid, 0, manual)
    store.submit(sid)
    return sid


def test_import_update_replace_and_revisions(store, bank):
    rows, count = store.list_questions()
    assert count == 4
    first = next(r for r in rows if r["external_id"] == "one")
    sid = answer_session(store, "scelta_singola", ["A"])
    changed = copy.deepcopy(bank)
    changed["domande"][0]["corrette"] = ["A"]
    store.import_bank(changed, "update", "test")
    assert store.question(first["pk"])["revision"] == 2
    assert store.session(sid)["items"][0]["question"]["corrette"] == ["B"]
    assert store.session_summary(sid)["counts"]["sbagliata"] == 1
    changed["domande"] = changed["domande"][:1]
    store.import_bank(changed, "replace", "test")
    assert store.list_questions()[1] == 1
    assert store.list_questions(trash=True)[1] == 3
    assert list((store.root / "backups").glob("*.zip"))


def test_transaction_cancellation_preserves_collection(store, bank):
    original = store.export_bank("test")
    bank["domande"][0]["testo"] = "Changed"
    with pytest.raises(ValueError, match="annullata"):
        store.import_bank(bank, "replace", "test", cancelled=lambda: True)
    assert store.export_bank("test") == original


def test_invalid_replace_does_not_delete(store, bank):
    bank["domande"][0]["corrette"] = ["unknown"]
    with pytest.raises(ValueError):
        store.import_bank(bank, "replace", "test")
    assert store.list_questions()[1] == 4


def test_idempotence_and_persistence(store):
    sid = store.create_session("allenamento", 1, {"kinds": ["scelta_singola"]})
    store.save_answer(sid, 0, ["A"], True)
    with pytest.raises(ValueError):
        store.save_answer(sid, 0, ["B"], True)
    store.submit(sid)
    store.submit(sid)
    other = Store(store.root)
    try:
        assert other.session_summary(sid)["counts"] == {"sbagliata": 1}
        assert other.db.execute("SELECT attempts FROM progress").fetchone()[0] == 1
    finally:
        other.close()


def test_training_drafts_are_omitted(store):
    sid = store.create_session("allenamento", 1, {"kinds": ["scelta_singola"]})
    store.save_answer(sid, 0, ["B"])
    store.submit(sid)
    assert store.session_summary(sid)["counts"] == {"omessa": 1}


def test_exam_drafts_hidden_and_timer(store):
    sid = store.create_session("esame", 1, {"kinds": ["aperta_libera"]}, {"minutes": 1})
    store.save_answer(sid, 0, "Una parte di un intero", True)
    assert store.session(sid)["items"][0]["outcome"] is None
    with pytest.raises(ValueError):
        store.manual_grade(sid, 0, "corretta")
    with store.db:
        store.db.execute("UPDATE sessions SET deadline=? WHERE id=?", (time.time() - 1, sid))
    assert store.check_deadline(sid)
    assert store.session(sid)["status"] == "submitted"
    assert store.session_summary(sid)["pending"] == 1
    store.manual_grade(sid, 0, "parziale")
    assert store.session_summary(sid)["points"] == 0.5
    assert store.session_summary(sid)["pending"] == 0
    with pytest.raises(ValueError):
        store.save_answer(sid, 0, "new")


def test_whitespace_answer_cannot_be_manually_graded(store):
    sid = store.create_session("esame", 1, {"kinds": ["aperta_libera"]})
    store.save_answer(sid, 0, "   ")
    store.submit(sid)
    assert store.session_summary(sid)["counts"] == {"omessa": 1}
    with pytest.raises(ValueError, match="omessa"):
        store.manual_grade(sid, 0, "corretta")


def test_recovery_reset_and_rebuild(store):
    answer_session(store, "scelta_singola", ["A"])
    assert store.db.execute("SELECT unresolved FROM progress").fetchone()[0] == 1
    answer_session(store, "scelta_singola", ["B"])
    assert store.db.execute("SELECT unresolved,streak FROM progress").fetchone()[:] == (1, 1)
    answer_session(store, "scelta_singola", ["B"])
    row = store.db.execute("SELECT * FROM progress").fetchone()
    assert row["unresolved"] == 0 and row["streak"] == 2 and row["wrong"] == 1
    store.reset_learning("test")
    store.rebuild_learning()
    assert store.db.execute("SELECT attempts FROM progress").fetchone()[0] == 0
    assert len(store.sessions()) == 3
    answer_session(store, "scelta_singola", ["A"])
    assert store.db.execute("SELECT wrong FROM progress").fetchone()[0] == 1


def test_manual_rectification_is_not_new_attempt(store):
    sid = answer_session(store, "aperta_breve", "Parigi.")
    item = store.session(sid)["items"][0]
    at = item["graded_at"]
    store.manual_grade(sid, 0, "corretta")
    assert store.session(sid)["items"][0]["graded_at"] == at
    row = store.db.execute("SELECT * FROM progress").fetchone()
    assert row["attempts"] == 1 and row["wrong"] == 0
    assert store.session(sid)["items"][0]["origin"] == "manuale"


def test_trash_restore_purge_results_recalculates(store):
    sid = answer_session(store, "scelta_singola", ["A"])
    store.session_action(sid, "trash")
    assert store.db.execute("SELECT attempts FROM progress").fetchone()[0] == 0
    store.session_action(sid, "restore")
    assert store.db.execute("SELECT attempts FROM progress").fetchone()[0] == 1
    store.collection_action("test", "trash")
    with pytest.raises(ValueError, match="Nessuna domanda"):
        store.choose_questions(5, "intelligente", {})
    store.collection_action("test", "restore")
    store.collection_action("test", "trash")
    store.collection_action("test", "purge", remove_history=False)
    assert store.session_summary(sid)["counts"]["sbagliata"] == 1
    assert store.session(sid)["items"][0]["question_pk"] is None


def test_backup_restore_and_path_traversal(store, tmp_path):
    sid = answer_session(store, "aperta_libera", "Spiegazione", "parziale")
    item = store.session(sid)["items"][0]
    store.add_note(item["question_pk"], 1, "Nota salvata")
    archive = store.backup()
    store.reset_learning()
    store.rename_collection("test", "Cambiata")
    store.restore_backup(archive)
    assert store.collections()[0]["title"] == "Raccolta test"
    assert store.notes(item["question_pk"], 1)[0]["text"] == "Nota salvata"
    assert store.session_summary(sid)["points"] == 0.5
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": "QuizSimulatorBackup", "version": 1}))
        z.writestr("quiz.sqlite3", "fake")
        z.writestr("sources/../../outside.txt", "bad")
    with pytest.raises(ValueError, match="percorsi"):
        store.restore_backup(bad)
    assert store.collections()[0]["title"] == "Raccolta test"


def altered_backup(store, path, statement, extra_files=None):
    database = path.with_suffix(".sqlite3")
    target = sqlite3.connect(database)
    try:
        store.db.backup(target)
        target.execute(statement)
        target.commit()
    finally:
        target.close()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "manifest.json", json.dumps({"format": "QuizSimulatorBackup", "version": 1})
        )
        archive.write(database, "quiz.sqlite3")
        for name, content in extra_files or []:
            archive.writestr(name, content)
    return path


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE items SET payload='not-json'",
        "UPDATE items SET answer='not-json'",
        "UPDATE sessions SET config='[]'",
        "INSERT OR REPLACE INTO settings(key,value) VALUES('bad','not-json')",
    ],
)
def test_restore_rejects_semantically_corrupt_history(store, tmp_path, statement):
    answer_session(store, "scelta_singola", ["B"])
    archive = altered_backup(store, tmp_path / "altered.zip", statement)
    with pytest.raises(ValueError, match="backup|contenuto|configurazione"):
        store.restore_backup(archive)
    assert store.collections()[0]["title"] == "Raccolta test"


def test_restore_rebuilds_search_index_and_checks_source_hash(store, tmp_path):
    archive = altered_backup(store, tmp_path / "without-fts.zip", "DROP TABLE questions_fts")
    store.restore_backup(archive)
    assert store.list_questions(search="capitale")[1] == 2

    bad_source = "sources/" + "0" * 64 + ".json"
    archive = altered_backup(
        store, tmp_path / "bad-source.zip", "SELECT 1", [(bad_source, b"altered")]
    )
    with pytest.raises(ValueError, match="fonte"):
        store.restore_backup(archive)


def test_fts_and_smart_no_duplicates(store):
    assert store.list_questions(search="capitale")[1] == 2
    assert store.list_questions(search='" OR *')[1] == 0
    selection = store.choose_questions(100, "intelligente", {}, random.Random(1))
    assert len(selection) == 4
    assert len(set(pk for pk, _ in selection)) == 4
    store.collection_action("test", "archive")
    with pytest.raises(ValueError):
        store.choose_questions(4, "intelligente", {"collection": "test"})


def test_only_one_concurrent_session_can_start(store):
    barrier = threading.Barrier(2)
    created = []
    failures = []

    def start_session():
        local = Store(store.root)
        original = local.active_session
        first_check = True

        def synchronized_check():
            nonlocal first_check
            result = original()
            if first_check:
                first_check = False
                barrier.wait(timeout=5)
            return result

        local.active_session = synchronized_check
        try:
            created.append(local.create_session("allenamento", 1))
        except ValueError as exc:
            failures.append(str(exc))
        finally:
            local.close()

    threads = [threading.Thread(target=start_session) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(created) == 1
    assert len(failures) == 1
    assert (
        store.db.execute(
            "SELECT count(*) FROM sessions WHERE status='active' AND deleted_at IS NULL"
        ).fetchone()[0]
        == 1
    )


def test_results_are_paginated_without_hiding_history(store):
    with store.transaction():
        store.db.executemany(
            """INSERT INTO sessions(id,mode,status,created_at,finished_at,config)
               VALUES(?,'allenamento','submitted',?,?, '{}')""",
            ((f"history-{index}", index, index) for index in range(205)),
        )
    assert store.session_count() == 205
    assert len(store.sessions(limit=100, offset=0)) == 100
    assert len(store.sessions(limit=100, offset=200)) == 5


def test_small_samples_and_origin_are_separate(store, bank):
    answer_session(store, "scelta_singola", ["A"])
    answer_session(store, "scelta_singola", ["A"])
    stats = store.analytics()
    assert stats[0]["count"] == 2 and not stats[0]["weak"] and not stats[0]["enough"]
    answer_session(store, "aperta_breve", "Something", "sbagliata")
    assert {s["origin"] for s in store.analytics()} == {"automatico", "manuale"}


def test_manual_short_answer_errors_feed_smart_selection(store, bank):
    template = copy.deepcopy(bank["domande"][2])
    bank["domande"] = [{**copy.deepcopy(template), "id": f"short-{index}"} for index in range(3)]
    store.import_bank(bank, "replace", "test")
    for _ in range(2):
        sid = store.create_session("allenamento", 3)
        for position in range(3):
            store.save_answer(sid, position, "sbagliata", True)
            store.manual_grade(sid, position, "sbagliata")
        store.submit(sid)
    assert any(stat["origin"] == "manuale" and stat["weak"] for stat in store.analytics())
    reasons = {reason for _, reason in store.choose_questions(3, "intelligente", {})}
    assert "Argomento da rinforzare" in reasons or "Errore ricorrente" in reasons
    assert store.choose_questions(1, "intelligente", {})[0][1] in {
        "Argomento da rinforzare",
        "Errore ricorrente",
    }


def test_unclassified_excluded_from_topic_diagnosis(store):
    rows, _ = store.list_questions()
    store.set_topic([r["pk"] for r in rows], "")
    answer_session(store, "scelta_singola", ["A"])
    assert not store.analytics()


def test_strong_topic_signal_and_recent_trend(store, bank):
    bank["domande"] = [{**copy.deepcopy(bank["domande"][0]), "id": str(i)} for i in range(3)]
    store.import_bank(bank, "replace", "test")
    for _ in range(4):
        sid = store.create_session("allenamento", 3)
        for i in range(3):
            store.save_answer(sid, i, ["A"], True)
        store.submit(sid)
    assert store.analytics()[0]["weak"]
    for _ in range(4):
        sid = store.create_session("allenamento", 3)
        for i in range(3):
            store.save_answer(sid, i, ["B"], True)
        store.submit(sid)
    assert store.analytics()[0]["trend"] == "In miglioramento"
