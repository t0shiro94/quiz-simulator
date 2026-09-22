import copy

import pytest

from quiz_simulator.domain import (
    evaluate,
    explanation_prompt,
    fingerprint,
    normalize_short,
    question_errors,
    score,
    validate_bank,
)


def test_single_and_multi(bank):
    one, multi, *_ = bank["domande"]
    assert evaluate(one, ["B"]).outcome == "corretta"
    assert evaluate(one, ["A"]).outcome == "sbagliata"
    assert evaluate(multi, ["C", "A"]).outcome == "corretta"
    assert evaluate(multi, ["A"]).outcome == "sbagliata"
    assert evaluate(multi, ["A", "B", "C"]).outcome == "sbagliata"
    multi["risposte"].reverse()
    assert evaluate(multi, ["A", "C"]).credit == 1
    with pytest.raises(ValueError):
        evaluate(one, ["X"])


def test_short_normalization_is_not_semantic_guessing(bank):
    q = bank["domande"][2]
    assert evaluate(q, "  PARIGI  ").outcome == "corretta"
    assert evaluate(q, "Parigì").outcome == "sbagliata"
    assert evaluate(q, "Parigi.").outcome == "sbagliata"
    assert normalize_short("  ABC   DEF ") == "abc def"
    assert normalize_short("e\u0301") == normalize_short("é")
    assert normalize_short("3,14") != normalize_short("3.14")


def test_free_pending_and_omitted(bank):
    q = bank["domande"][3]
    assert evaluate(q, "La mia spiegazione").outcome == "da_valutare"
    assert evaluate(q, "testo").credit is None
    assert evaluate(q, "   ").outcome == "omessa"
    assert score("da_valutare", {}) is None
    assert score("parziale", {"correct_points": 4}) == 2
    assert score("sbagliata", {"wrong_points": -0.25}) == -0.25


def test_schema_and_legacy(bank):
    assert not question_errors(bank["domande"][0])
    legacy = copy.deepcopy(bank)
    legacy["versione_schema"] = 1
    legacy["domande"] = [legacy["domande"][0]]
    legacy["domande"][0]["corretta"] = legacy["domande"][0].pop("corrette")[0]
    legacy["domande"][0].pop("tipo")
    assert validate_bank(legacy)["domande"][0]["corrette"] == ["B"]
    for mutate in [
        lambda b: b.update(versione_schema=99),
        lambda b: b["domande"].append(b["domande"][0]),
        lambda b: b["domande"][0].update(corrette=["X"]),
        lambda b: b["domande"][3].update(criteri=[]),
    ]:
        bad = copy.deepcopy(bank)
        mutate(bad)
        with pytest.raises(ValueError):
            validate_bank(bad)


def test_fingerprint_ignores_explanation_not_solution(bank):
    q = bank["domande"][0]
    changed = {**q, "spiegazione": "Un approfondimento", "argomento": "Capitali"}
    assert fingerprint(changed) == fingerprint(q)
    changed["corrette"] = ["A"]
    assert fingerprint(changed) != fingerprint(q)

    multi = copy.deepcopy(bank["domande"][1])
    reordered = copy.deepcopy(multi)
    reordered["risposte"].reverse()
    reordered["corrette"].reverse()
    assert fingerprint(reordered) == fingerprint(multi)

    short = copy.deepcopy(bank["domande"][2])
    short["risposte_ammesse"] = ["  PARIS ", "PARIGI"]
    assert fingerprint(short) == fingerprint(bank["domande"][2])


def test_prompt_includes_context_and_user_answer(bank):
    prompt = explanation_prompt(bank["domande"][0], ["A"])
    assert "LA MIA RISPOSTA\nA) Roma" in prompt
    assert "SOLUZIONE DELLA FONTE\nB) Parigi" in prompt
