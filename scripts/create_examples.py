"""Genera nel progetto raccolte JSON e PDF di esempio riproducibili."""

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from quiz_simulator.domain import validate_bank

ROOT = Path(__file__).resolve().parents[1]


def make_bank():
    def single(ident, text, topic, options, correct, explanation):
        return {
            "id": ident,
            "tipo": "scelta_singola",
            "testo": text,
            "argomento": topic,
            "risposte": [{"id": chr(65 + i), "testo": value} for i, value in enumerate(options)],
            "corrette": [correct],
            "spiegazione": explanation,
        }

    questions = [
        single(
            "geo-001",
            "Qual è la capitale della Francia?",
            "Capitali europee",
            ["Roma", "Parigi", "Madrid", "Berlino"],
            "B",
            "Parigi è la capitale della Francia.",
        ),
        single(
            "geo-002",
            "Qual è la capitale della Spagna?",
            "Capitali europee",
            ["Madrid", "Barcellona", "Lisbona", "Siviglia"],
            "A",
            "La capitale della Spagna è Madrid.",
        ),
        single(
            "geo-003",
            "Qual è la capitale del Portogallo?",
            "Capitali europee",
            ["Porto", "Madrid", "Lisbona", "Braga"],
            "C",
            "Lisbona è la capitale del Portogallo.",
        ),
        single(
            "geo-004",
            "Berlino è la capitale della Germania.",
            "Capitali europee",
            ["Vero", "Falso"],
            "A",
            "Il vero/falso è una domanda a scelta singola con due alternative.",
        ),
        single(
            "mat-001",
            "Quanto vale 7 × 8?",
            "Aritmetica",
            ["54", "56", "64", "48"],
            "B",
            "Sette gruppi da otto elementi contengono 56 elementi.",
        ),
        single(
            "mat-002",
            "Quanto vale 3/4 espresso in percentuale?",
            "Aritmetica",
            ["25%", "50%", "75%", "80%"],
            "C",
            "3 diviso 4 è 0,75: moltiplicando per 100 si ottiene 75%.",
        ),
        single(
            "mat-003",
            "Quale numero è primo?",
            "Aritmetica",
            ["9", "15", "21", "17"],
            "D",
            "17 ha come divisori positivi soltanto 1 e 17.",
        ),
        {
            "id": "mat-004",
            "tipo": "scelta_multipla",
            "testo": "Seleziona tutti i numeri pari.",
            "argomento": "Aritmetica",
            "risposte": [
                {"id": "A", "testo": "2"},
                {"id": "B", "testo": "3"},
                {"id": "C", "testo": "4"},
                {"id": "D", "testo": "7"},
            ],
            "corrette": ["A", "C"],
            "spiegazione": "I numeri pari sono divisibili per 2 senza resto.",
        },
        {
            "id": "geo-005",
            "tipo": "scelta_multipla",
            "testo": "Quali tra queste città sono capitali nazionali?",
            "argomento": "Capitali europee",
            "risposte": [
                {"id": "A", "testo": "Roma"},
                {"id": "B", "testo": "Milano"},
                {"id": "C", "testo": "Lisbona"},
                {"id": "D", "testo": "Madrid"},
            ],
            "corrette": ["A", "C", "D"],
        },
        {
            "id": "geo-006",
            "tipo": "aperta_breve",
            "testo": "Scrivi la capitale della Francia.",
            "argomento": "Capitali europee",
            "risposte_ammesse": ["Parigi", "Paris"],
        },
        {
            "id": "mat-005",
            "tipo": "aperta_breve",
            "testo": "Scrivi il valore decimale di un quarto.",
            "argomento": "Aritmetica",
            "risposte_ammesse": ["0,25", "0.25"],
            "spiegazione": "Le varianti con virgola e punto sono ammesse esplicitamente.",
        },
        {
            "id": "mat-006",
            "tipo": "aperta_libera",
            "testo": "Spiega che cosa rappresenta una frazione e fai un esempio.",
            "argomento": "Aritmetica",
            "risposta_modello": "Una frazione rappresenta un rapporto o parti uguali di un intero. In 3/4, il denominatore 4 indica in quante parti uguali è diviso l'intero e il numeratore 3 indica quante parti si considerano.",
            "criteri": [
                "Descrive il significato della frazione",
                "Distingue numeratore e denominatore",
                "Presenta un esempio coerente",
            ],
        },
    ]
    return validate_bank(
        {
            "versione_schema": 2,
            "id": "raccolta-demo",
            "titolo": "Primi passi - Geografia e matematica",
            "domande": questions,
        }
    )


def question_lines(q, number, inline=True):
    lines = [f"{number}. {q['testo']}"]
    if q["tipo"].startswith("scelta"):
        lines += [f"{r['id']}) {r['testo']}" for r in q["risposte"]]
        if inline:
            marker = "Risposta corretta" if q["tipo"] == "scelta_singola" else "Risposte corrette"
            lines.append(marker + ": " + ", ".join(q["corrette"]))
    else:
        lines.append("Tipo: " + q["tipo"])
        if q["tipo"] == "aperta_breve":
            lines.append("Risposte ammesse: " + " | ".join(q["risposte_ammesse"]))
        else:
            lines += ["Risposta modello: " + q["risposta_modello"], "Criteri:"]
            lines += ["- " + x for x in q["criteri"]]
    lines.append("Argomento: " + q["argomento"])
    if q.get("spiegazione"):
        lines.append("Spiegazione: " + q["spiegazione"])
    return lines


def render_pdf(path, questions, inline=True):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "QuizText",
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            spaceAfter=3,
            textColor=HexColor("#203940"),
        )
    )
    styles.add(
        ParagraphStyle(
            "QuizQuestion", parent=styles["QuizText"], fontName="Helvetica-Bold", spaceBefore=4
        )
    )
    story = []
    for i, q in enumerate(questions, 1):
        lines = question_lines(q, i, inline)
        block = [
            Paragraph(escape(line), styles["QuizQuestion"] if j == 0 else styles["QuizText"])
            for j, line in enumerate(lines)
        ]
        block.append(Spacer(1, 15))
        story.append(KeepTogether(block))
    if not inline:
        story.append(Paragraph("SOLUZIONI", styles["QuizQuestion"]))
        for i, q in enumerate(questions, 1):
            story.append(Paragraph(f"{i}: " + ", ".join(q["corrette"]), styles["QuizText"]))
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=44,
        leftMargin=44,
        topMargin=35,
        bottomMargin=35,
        title="Quiz Simulator - esempi importabili",
        author="Raffaele / t0shiro94",
    )
    doc.build(story)


def main():
    destination = ROOT / "examples"
    destination.mkdir(exist_ok=True)
    bank = make_bank()
    (destination / "raccolta_demo.json").write_text(
        json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for kind in ("scelta_singola", "scelta_multipla", "aperta_breve", "aperta_libera"):
        subset = {
            **bank,
            "id": "esempio-" + kind,
            "titolo": "Esempio " + kind.replace("_", " "),
            "domande": [q for q in bank["domande"] if q["tipo"] == kind],
        }
        (destination / (kind + ".json")).write_text(
            json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    render_pdf(destination / "quiz_demo.pdf", bank["domande"])
    render_pdf(
        destination / "quiz_soluzioni_finali.pdf",
        [q for q in bank["domande"] if q["tipo"].startswith("scelta")],
        False,
    )
    print("Creati 5 JSON e 2 PDF nella cartella examples.")


if __name__ == "__main__":
    main()
