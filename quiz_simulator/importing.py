from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

from .domain import UNTAGGED, normalize_bank


class Cancelled(Exception):
    pass


def read_json(path: Path) -> dict:
    try:
        return normalize_bank(json.loads(Path(path).read_text(encoding="utf-8-sig")))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: riga {e.lineno}, colonna {e.colno}. {e.msg}") from e


def parse_pdf_text(
    pages: list[tuple[int, str]], title: str, bank_id: str
) -> tuple[dict, list[str], dict]:
    warnings = []
    sources = {}
    questions = []
    keys: dict[str, list[str]] = {}
    current = None
    field = "testo"
    in_keys = False
    current_option = None
    explicit_correct = {}

    def finish():
        nonlocal current
        if current is not None:
            current.setdefault("argomento", UNTAGGED)
            if "tipo" not in current:
                current["tipo"] = (
                    "scelta_multipla" if len(current.get("corrette", [])) > 1 else "scelta_singola"
                )
            if current["tipo"].startswith("scelta"):
                current.setdefault("risposte", [])
                current.setdefault("corrette", [])
            questions.append(current)
        current = None

    def parse_ids(value):
        return [s.strip().upper() for s in re.split(r"[,;\s]+", value.strip()) if s.strip()]

    for page_no, text in pages:
        if not text.strip():
            warnings.append(f"Pagina {page_no}: nessun testo estraibile. Potrebbe richiedere OCR.")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if re.fullmatch(r"SOLUZIONI\s*:?", line, re.I):
                finish()
                in_keys = True
                continue
            if in_keys:
                match = re.fullmatch(r"(\d+)\s*[:.)-]\s*([A-Za-z](?:\s*[,;]\s*[A-Za-z])*)", line)
                if match:
                    ident, ids = match.group(1), parse_ids(match.group(2))
                    if ident in keys and keys[ident] != ids:
                        warnings.append(f"Soluzioni finali contraddittorie per la domanda {ident}.")
                        keys[ident] = ["CONFLITTO"]
                    else:
                        keys[ident] = ids
                else:
                    warnings.append(
                        f"Pagina {page_no}: riga soluzioni non riconosciuta: {line[:100]}"
                    )
                continue
            match = re.match(r"^(\d+)[.)]\s+(.+)$", line)
            if match:
                finish()
                current = {"id": match.group(1), "testo": match.group(2)}
                sources[current["id"]] = page_no
                field, current_option = "testo", None
                continue
            if current is None:
                if line:
                    warnings.append(f"Pagina {page_no}: testo fuori dalle domande: {line[:90]}")
                continue
            marker = re.match(
                r"^(Tipo|Rispost[ae] corrett[ae]|Risposte ammesse|Risposta modello|Criteri|Argomento|Spiegazione)\s*:\s*(.*)$",
                line,
                re.I,
            )
            if marker:
                name, value = marker.group(1).casefold(), marker.group(2)
                current_option = None
                if name == "tipo":
                    current["tipo"] = value.strip().casefold()
                    field = None
                elif name in ("risposta corretta", "risposte corrette"):
                    ids = parse_ids(value)
                    if current["id"] in explicit_correct and explicit_correct[current["id"]] != ids:
                        ids = ["CONFLITTO"]
                    current["corrette"] = ids
                    explicit_correct[current["id"]] = ids
                    field = None
                elif name == "risposte ammesse":
                    current["risposte_ammesse"] = [x.strip() for x in value.split("|") if x.strip()]
                    field = "risposte_ammesse"
                elif name == "criteri":
                    current["criteri"] = [value] if value else []
                    field = "criteri"
                else:
                    field = {
                        "risposta modello": "risposta_modello",
                        "argomento": "argomento",
                        "spiegazione": "spiegazione",
                    }[name]
                    current[field] = value
                continue
            option = re.match(r"^([A-Za-z])[.)]\s+(.+)$", line)
            if (
                option
                and current.get("tipo", "").startswith("aperta") is False
                and field in ("testo", "risposte")
            ):
                current_option = {"id": option.group(1).upper(), "testo": option.group(2)}
                current.setdefault("risposte", []).append(current_option)
                field = "risposte"
            elif field == "risposte" and current_option is not None:
                current_option["testo"] += " " + line
            elif field == "criteri":
                if line.startswith(("- ", "• ")) or not current["criteri"]:
                    current["criteri"].append(line.lstrip("-• "))
                else:
                    current["criteri"][-1] += " " + line
            elif field == "risposte_ammesse":
                current[field].extend(x.strip() for x in line.split("|") if x.strip())
            elif field:
                current[field] = (current.get(field, "") + " " + line).strip()
            else:
                warnings.append(f"Pagina {page_no}: riga da verificare: {line[:90]}")
    finish()
    for q in questions:
        if q["id"] in keys:
            ids = keys[q["id"]]
            if q["id"] in explicit_correct and set(ids) != set(explicit_correct[q["id"]]):
                warnings.append(f"Domanda {q['id']}: soluzione inline e finale contraddittorie.")
                q["corrette"] = ["CONFLITTO"]
            elif q["tipo"].startswith("scelta"):
                q["corrette"] = ids
                if len(ids) > 1:
                    q["tipo"] = "scelta_multipla"
    missing = set(keys) - {q["id"] for q in questions}
    if missing:
        warnings.append("Soluzioni senza domanda: " + ", ".join(sorted(missing)))
    if not questions:
        warnings.append(
            "Nessuna domanda riconosciuta. Usa numeri come '1. Domanda' o inserisci i quesiti nell'editor."
        )
    return (
        {"versione_schema": 2, "id": bank_id, "titolo": title, "domande": questions},
        warnings,
        sources,
    )


def read_pdf(path: Path, start: int = 1, end: int | None = None, progress=None, cancelled=None):
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("Il PDF è protetto: usa una copia sbloccata con testo selezionabile.")
    end = end or len(reader.pages)
    if start < 1 or end < start or end > len(reader.pages):
        raise ValueError(
            f"Intervallo pagine non valido. Il PDF contiene {len(reader.pages)} pagine."
        )
    pages = []
    for number in range(start, end + 1):
        if cancelled and cancelled():
            raise Cancelled("Importazione annullata.")
        pages.append((number, reader.pages[number - 1].extract_text() or ""))
        if progress:
            progress(int(100 * (number - start + 1) / (end - start + 1)))
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    return parse_pdf_text(pages, Path(path).stem, "pdf-" + digest)
