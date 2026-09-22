import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Anche i dati temporanei di pytest devono restare nel progetto.
tempfile.tempdir = str(Path(__file__).resolve().parent.parent / "tmp")

import pytest

from quiz_simulator.storage import Store


@pytest.fixture
def bank():
    return {
        "versione_schema": 2,
        "id": "test",
        "titolo": "Raccolta test",
        "domande": [
            {
                "id": "one",
                "tipo": "scelta_singola",
                "testo": "Qual è la capitale della Francia?",
                "argomento": "Geografia",
                "risposte": [{"id": "A", "testo": "Roma"}, {"id": "B", "testo": "Parigi"}],
                "corrette": ["B"],
            },
            {
                "id": "multi",
                "tipo": "scelta_multipla",
                "testo": "Quali numeri sono pari?",
                "argomento": "Matematica",
                "risposte": [
                    {"id": "A", "testo": "2"},
                    {"id": "B", "testo": "3"},
                    {"id": "C", "testo": "4"},
                ],
                "corrette": ["A", "C"],
            },
            {
                "id": "short",
                "tipo": "aperta_breve",
                "testo": "Capitale della Francia?",
                "argomento": "Geografia",
                "risposte_ammesse": ["Parigi", "Paris"],
            },
            {
                "id": "free",
                "tipo": "aperta_libera",
                "testo": "Spiega una frazione.",
                "argomento": "Matematica",
                "risposta_modello": "Una frazione rappresenta parti di un intero.",
                "criteri": ["Spiega numeratore e denominatore", "Fornisce un esempio"],
            },
        ],
    }


@pytest.fixture
def store(tmp_path, bank):
    s = Store(tmp_path)
    s.import_bank(bank)
    yield s
    s.close()
