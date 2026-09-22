from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from jsonschema import Draft202012Validator

from .paths import resource

TYPES = {
    "scelta_singola": "Scelta singola",
    "scelta_multipla": "Scelta multipla",
    "aperta_breve": "Risposta breve",
    "aperta_libera": "Testo libero",
}
OUTCOMES = {
    "corretta": "Corretta",
    "parziale": "Parzialmente corretta",
    "sbagliata": "Sbagliata",
    "omessa": "Omessa",
    "da_valutare": "Da valutare",
}
CREDITS = {"corretta": 1.0, "parziale": 0.5, "sbagliata": 0.0, "omessa": 0.0, "da_valutare": None}
UNTAGGED = "Da classificare"


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(resource("schemas/quiz-v2.schema.json").read_text(encoding="utf-8"))


def question_errors(q: dict) -> list[str]:
    errors = []
    validator = question_validator()
    for error in validator.iter_errors(q):
        path = ".".join(str(p) for p in error.absolute_path) or "domanda"
        if error.validator == "required":
            errors.append(f"{path}: manca un campo obbligatorio ({error.message}).")
        else:
            errors.append(f"{path}: valore non valido ({error.message}).")
    if errors:
        return errors
    for field in ("id", "testo", "risposta_modello"):
        if field in q and not q[field].strip():
            errors.append(f"{field}: il testo non può essere vuoto.")
    for field in ("criteri", "risposte_ammesse"):
        if any(not x.strip() for x in q.get(field, [])):
            errors.append(f"{field}: non sono ammessi elementi vuoti.")
    options = q.get("risposte", [])
    ids = [x["id"] for x in options]
    if len(set(ids)) != len(ids):
        errors.append("risposte: gli identificatori devono essere distinti.")
    if any(not x["id"].strip() or not x["testo"].strip() for x in options):
        errors.append("risposte: identificatori e testi non possono essere vuoti.")
    if q["tipo"].startswith("scelta") and not set(q["corrette"]).issubset(ids):
        errors.append("corrette: una soluzione fa riferimento a un'alternativa inesistente.")
    allowed = {"id", "tipo", "testo", "argomento", "spiegazione"}
    allowed |= (
        {"risposte", "corrette"}
        if q["tipo"].startswith("scelta")
        else {"risposte_ammesse"}
        if q["tipo"] == "aperta_breve"
        else {"risposta_modello", "criteri"}
    )
    if set(q) - allowed:
        errors.append("Sono presenti campi appartenenti a un altro tipo di domanda.")
    return errors


@lru_cache(maxsize=1)
def question_validator():
    return Draft202012Validator(schema()["$defs"]["domanda"])


def normalize_bank(raw: dict) -> dict:
    bank = copy.deepcopy(raw)
    if not isinstance(bank, dict):
        raise ValueError("Il file deve contenere un oggetto JSON con titolo e domande.")
    version = bank.get("versione_schema")
    if version not in (1, 2):
        raise ValueError("Versione del formato non supportata. Sono accettate le versioni 1 e 2.")
    if not isinstance(bank.get("domande"), list):
        raise ValueError("Il campo 'domande' deve essere un elenco.")
    if version == 1:
        for q in bank["domande"]:
            if not isinstance(q, dict):
                raise ValueError("Ogni domanda deve essere un oggetto JSON.")
            q["tipo"] = "scelta_singola"
            old = q.pop("corretta", None)
            q["corrette"] = [old] if isinstance(old, str) else []
        bank["versione_schema"] = 2
    for q in bank["domande"]:
        if not isinstance(q, dict):
            raise ValueError("Ogni domanda deve essere un oggetto JSON.")
        if not isinstance(q.get("argomento", ""), str):
            raise ValueError("L'argomento deve essere un testo.")
        q["argomento"] = q.get("argomento", "").strip() or UNTAGGED
    return bank


def bank_errors(bank: dict) -> list[str]:
    errors = []
    top = {k: v for k, v in schema().items() if k not in ("$defs",)}
    top["properties"] = {**top["properties"], "domande": {"type": "array", "minItems": 1}}
    for e in Draft202012Validator(top).iter_errors(bank):
        errors.append(f"Raccolta: {e.message}")
    if errors:
        return errors
    if not bank["id"].strip() or not bank["titolo"].strip():
        errors.append("Identificatore e titolo della raccolta non possono essere vuoti.")
    seen = set()
    for i, q in enumerate(bank["domande"], 1):
        errors.extend(f"Domanda {i}: {e}" for e in question_errors(q))
        key = q.get("id") if isinstance(q, dict) else None
        if not isinstance(key, str):
            continue
        if key in seen:
            errors.append(f"Domanda {i}: identificatore duplicato '{key}'.")
        seen.add(key)
    return errors


def validate_bank(raw: dict) -> dict:
    bank = normalize_bank(raw)
    errors = bank_errors(bank)
    if errors:
        raise ValueError("\n".join(errors[:25]))
    return bank


def normalize_short(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


@dataclass(frozen=True)
class Evaluation:
    outcome: str
    origin: str = "automatico"

    @property
    def credit(self):
        return CREDITS[self.outcome]


def evaluate(q: dict, answer) -> Evaluation:
    if answer is None or (isinstance(answer, str) and not answer.strip()) or answer == []:
        return Evaluation("omessa")
    kind = q["tipo"]
    if kind in ("scelta_singola", "scelta_multipla"):
        if not isinstance(answer, list) or any(not isinstance(x, str) for x in answer):
            raise ValueError("Seleziona una risposta valida.")
        if not set(answer).issubset({x["id"] for x in q["risposte"]}):
            raise ValueError("Alternativa inesistente.")
        return Evaluation("corretta" if set(answer) == set(q["corrette"]) else "sbagliata")
    if not isinstance(answer, str):
        raise ValueError("La risposta deve essere un testo.")
    if kind == "aperta_breve":
        return Evaluation(
            "corretta"
            if normalize_short(answer) in {normalize_short(x) for x in q["risposte_ammesse"]}
            else "sbagliata"
        )
    return Evaluation("da_valutare", "manuale")


def score(outcome: str | None, config: dict):
    if outcome is None or outcome == "da_valutare":
        return None
    if outcome == "parziale":
        return config.get("correct_points", 1.0) / 2
    return {
        "corretta": config.get("correct_points", 1.0),
        "sbagliata": config.get("wrong_points", 0.0),
        "omessa": config.get("omitted_points", 0.0),
    }[outcome]


def fingerprint(q: dict) -> str:
    # Spiegazioni, argomenti e identificatori non cambiano le regole di valutazione.
    content = copy.deepcopy(
        {k: v for k, v in q.items() if k not in ("spiegazione", "argomento", "id")}
    )
    if "risposte" in content:
        content["risposte"] = sorted(content["risposte"], key=lambda option: option["id"])
        content["corrette"] = sorted(set(content["corrette"]))
    if "risposte_ammesse" in content:
        content["risposte_ammesse"] = sorted(
            {normalize_short(answer) for answer in content["risposte_ammesse"]}
        )
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def solution_text(q: dict) -> str:
    if q["tipo"].startswith("scelta"):
        return "\n".join(
            f"{r['id']}) {r['testo']}" for r in q["risposte"] if r["id"] in q["corrette"]
        )
    if q["tipo"] == "aperta_breve":
        return " / ".join(q["risposte_ammesse"])
    return q["risposta_modello"] + "\n\nCriteri:\n" + "\n".join("• " + c for c in q["criteri"])


def answer_text(q: dict, answer) -> str:
    if not answer:
        return "Nessuna risposta"
    if isinstance(answer, list):
        return "\n".join(
            f"{r['id']}) {r['testo']}" for r in q.get("risposte", []) if r["id"] in answer
        )
    return answer


def explanation_prompt(q: dict, answer) -> str:
    alternatives = "\n".join(f"{r['id']}) {r['testo']}" for r in q.get("risposte", []))
    return (
        "Aiutami a capire questa domanda. Spiega il ragionamento e l'eventuale errore nella mia risposta. "
        "Se la soluzione fornita è incoerente, segnalalo e motiva il dubbio; non inventare fonti. "
        "Per una risposta aperta confronta il mio testo con i criteri, distinguendo ciò che manca da ciò che è errato.\n\n"
        f"DOMANDA\n{q['testo']}\n\nALTERNATIVE\n{alternatives or 'Risposta aperta'}\n\n"
        f"LA MIA RISPOSTA\n{answer_text(q, answer)}\n\nSOLUZIONE DELLA FONTE\n{solution_text(q)}\n\n"
        f"SPIEGAZIONE DELLA FONTE\n{q.get('spiegazione') or 'Non disponibile'}"
    )
