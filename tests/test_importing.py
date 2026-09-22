import pytest

from quiz_simulator.domain import question_errors, validate_bank
from quiz_simulator.importing import parse_pdf_text, read_json


def test_inline_multiline_and_page_continuation():
    bank, warnings, pages = parse_pdf_text(
        [
            (1, "1. Qual è la capitale\ndella Francia?\nA) Roma\nB) Parigi"),
            (
                2,
                "Risposta corretta: B\nArgomento: Geografia\n2) Quali sono pari?\nA. 2\nB. 3\nC. 4\nRisposte corrette: A, C",
            ),
        ],
        "Test",
        "test",
    )
    assert not warnings
    validate_bank(bank)
    assert bank["domande"][0]["testo"] == "Qual è la capitale della Francia?"
    assert bank["domande"][1]["tipo"] == "scelta_multipla"
    assert pages == {"1": 1, "2": 2}


def test_final_solutions_and_conflicts():
    source = "1. Quesito\nA) Uno\nB) Due\nRisposta corretta: A\nSOLUZIONI\n1: B"
    bank, warnings, _ = parse_pdf_text([(1, source)], "Test", "test")
    assert any("contraddittorie" in w for w in warnings)
    assert question_errors(bank["domande"][0])
    bank, _, _ = parse_pdf_text([(1, source.replace("Risposta corretta: A\n", ""))], "Test", "test")
    assert validate_bank(bank)["domande"][0]["corrette"] == ["B"]


def test_pdf_open_questions():
    text = "1. Capitale francese?\nTipo: aperta_breve\nRisposte ammesse: Parigi | Paris\n2. Spiega una frazione.\nTipo: aperta_libera\nRisposta modello: Parti di un intero.\nCriteri:\n- Definizione\n- Esempio"
    bank, _, _ = parse_pdf_text([(1, text)], "Test", "test")
    validate_bank(bank)
    assert bank["domande"][1]["criteri"] == ["Definizione", "Esempio"]


def test_empty_pages_do_not_invent_questions():
    bank, warnings, _ = parse_pdf_text([(1, "")], "Vuoto", "empty")
    assert not bank["domande"]
    assert any("OCR" in w for w in warnings)


def test_broken_json_location(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"broken":', encoding="utf-8")
    with pytest.raises(ValueError, match="riga 1"):
        read_json(path)
