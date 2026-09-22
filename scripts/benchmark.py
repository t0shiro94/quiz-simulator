"""Verifica ripetibile delle prestazioni su un archivio di grandi dimensioni."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quiz_simulator.storage import Store, dumps


def question(number: int) -> dict:
    return {
        "id": f"q-{number:05d}",
        "tipo": "scelta_singola",
        "testo": f"Qual è la risposta al concetto {number}?",
        "argomento": f"Argomento {number % 100:02d}",
        "risposte": [
            {"id": "A", "testo": "Risposta corretta"},
            {"id": "B", "testo": "Distrattore"},
        ],
        "corrette": ["A"],
    }


def timed(operation):
    started = time.perf_counter()
    value = operation()
    return value, round(time.perf_counter() - started, 3)


def add_attempts(store: Store, question_count: int, attempt_count: int) -> None:
    """Popola lo storico a blocchi, come farebbe un archivio cresciuto nel tempo."""
    session_size = 100
    session_count = (attempt_count + session_size - 1) // session_size
    now = time.time() - attempt_count
    payload = dumps(question(0))
    config = dumps(
        {
            "correct_points": 1.0,
            "wrong_points": 0.0,
            "omitted_points": 0.0,
            "shuffle_options": False,
            "minutes": 0,
        }
    )

    with store.transaction():
        store.db.executemany(
            """INSERT INTO sessions(id,mode,status,created_at,finished_at,config)
               VALUES(?, 'allenamento', 'submitted', ?, ?, ?)""",
            (
                (f"bench-{index:07d}", now + index, now + index, config)
                for index in range(session_count)
            ),
        )

        batch = []
        for index in range(attempt_count):
            question_pk = index % question_count + 1
            remainder = index % 20
            outcome = (
                "corretta" if remainder < 12 else "sbagliata" if remainder < 17 else "parziale"
            )
            batch.append(
                (
                    f"bench-{index // session_size:07d}",
                    index % session_size,
                    question_pk,
                    f"Argomento {(question_pk - 1) % 100:02d}",
                    payload,
                    dumps(["A"]),
                    outcome,
                    now + index,
                )
            )
            if len(batch) == 10_000:
                store.db.executemany(
                    """INSERT INTO items(
                         session_id,position,question_pk,revision,topic,payload,answer,
                         confirmed,outcome,origin,original_outcome,graded_at)
                       VALUES(?,?,?,1,?,?,?,1,?,'automatico',?,?)""",
                    [(*row[:7], row[6], row[7]) for row in batch],
                )
                batch.clear()
        if batch:
            store.db.executemany(
                """INSERT INTO items(
                     session_id,position,question_pk,revision,topic,payload,answer,
                     confirmed,outcome,origin,original_outcome,graded_at)
                   VALUES(?,?,?,1,?,?,?,1,?,'automatico',?,?)""",
                [(*row[:7], row[6], row[7]) for row in batch],
            )

        attempts_per_question, extra_attempts = divmod(attempt_count, question_count)
        store.db.executemany(
            """INSERT INTO progress(
                 question_pk,attempts,wrong,partial,correct,unresolved,streak,due,last_at,last_outcome)
               VALUES(?,?,?,?,?,1,0,?,?,?)""",
            (
                (
                    pk,
                    attempts_per_question + int(pk <= extra_attempts),
                    (attempts_per_question + int(pk <= extra_attempts)) * 5 // 20,
                    (attempts_per_question + int(pk <= extra_attempts)) * 3 // 20,
                    (attempts_per_question + int(pk <= extra_attempts)) * 12 // 20,
                    now,
                    now + attempt_count,
                    "sbagliata",
                )
                for pk in range(1, question_count + 1)
            ),
        )


def run(question_count: int, attempt_count: int) -> dict:
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="benchmark-") as directory:
        store = Store(Path(directory))
        bank = {
            "versione_schema": 2,
            "id": "benchmark",
            "titolo": "Benchmark",
            "domande": [question(index) for index in range(question_count)],
        }

        _, import_seconds = timed(lambda: store.import_bank(bank))
        _, attempts_seconds = timed(lambda: add_attempts(store, question_count, attempt_count))
        found, search_seconds = timed(
            lambda: store.list_questions(search=f"concetto {question_count // 2}", limit=20)
        )
        stats, analytics_seconds = timed(store.analytics)
        _, adaptive_seconds = timed(lambda: store.create_session("intelligente", 100))
        dashboard, dashboard_seconds = timed(store.dashboard)
        database_megabytes = round(store.path.stat().st_size / 1024 / 1024, 1)
        store.close()

    result = {
        "questions": question_count,
        "attempts": attempt_count,
        "database_megabytes": database_megabytes,
        "seconds": {
            "import": import_seconds,
            "attempt_population": attempts_seconds,
            "full_text_search": search_seconds,
            "analytics": analytics_seconds,
            "adaptive_quiz": adaptive_seconds,
            "dashboard": dashboard_seconds,
        },
        "checks": {
            "search_found": found[1] >= 1,
            "analytics_groups": len(stats),
            "dashboard_questions": dashboard["summary"]["questions"],
            "dashboard_attempts": dashboard["summary"]["attempts"],
        },
    }
    result["passed"] = (
        result["checks"]["search_found"]
        and result["checks"]["dashboard_questions"] == question_count
        and search_seconds < 2
        and analytics_seconds < 8
        and adaptive_seconds < 8
        and dashboard_seconds < 3
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=int, default=50_000)
    parser.add_argument("--attempts", type=int, default=500_000)
    args = parser.parse_args()
    if args.questions < 1 or args.attempts < 0:
        parser.error("I valori devono essere positivi.")

    result = run(args.questions, args.attempts)
    output = ROOT / "tmp" / "benchmark-last.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
