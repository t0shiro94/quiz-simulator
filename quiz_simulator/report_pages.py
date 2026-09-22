from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHeaderView,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .domain import TYPES
from .storage import Store
from .widgets import button, card, confirm, error, label, row, run_task


def when(stamp):
    return datetime.fromtimestamp(stamp).strftime("%d/%m/%Y %H:%M") if stamp else "—"


def data_table(headers, rows, stretch=0):
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    for i, data in enumerate(rows):
        for j, text in enumerate(data):
            cell = QTableWidgetItem(str(text))
            cell.setToolTip(str(text))
            table.setItem(i, j, cell)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    table.setMinimumHeight(200)
    return table


class HomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, window.store
        layout = QVBoxLayout(self)
        layout.addWidget(label("Un passo avanti, ogni giorno.", "heading"))
        layout.addWidget(label("I tuoi quiz, i tuoi progressi. Tutto su questo computer.", "muted"))
        available = sum(c["count"] for c in self.store.collections() if not c["archived"])
        current = self.store.active_session()
        if current:
            banner = QFrame()
            banner.setObjectName("feedback")
            body = QVBoxLayout(banner)
            body.addWidget(label("Hai una prova in corso", "subheading"))
            body.addWidget(label("Le risposte sono salvate. Puoi riprendere da dove eri arrivato."))
            body.addWidget(
                button("Riprendi la prova", lambda: window.open_session(current), primary=True)
            )
            layout.addWidget(banner)
        layout.addLayout(
            row(
                card("Domande disponibili", available),
                card("Raccolte", len(self.store.collections())),
                card("Modalità", "3", "Allenamento · Esame · Intelligente"),
            )
        )
        if not available:
            welcome = QFrame()
            welcome.setObjectName("card")
            box = QVBoxLayout(welcome)
            box.addWidget(label("Costruisci il tuo primo quiz", "subheading"))
            box.addWidget(
                label(
                    "1. Importa un JSON o PDF\n2. Controlla domande e argomenti\n3. Comincia ad allenarti"
                )
            )
            box.addLayout(
                row(
                    button("Importa le tue domande", window.import_file, primary=True),
                    button("Prova la raccolta di esempio", window.import_examples),
                    None,
                )
            )
            layout.addWidget(welcome)
        else:
            layout.addLayout(
                row(
                    button("Nuovo allenamento", lambda: window.new_quiz(), primary=True),
                    button("Allenami sui punti deboli", lambda: window.new_quiz("intelligente")),
                    button("Simula un esame", lambda: window.new_quiz("esame")),
                    None,
                )
            )
            layout.addWidget(label("Continua il tuo percorso", "subheading"))
            layout.addWidget(
                label(
                    "In Risultati trovi lo storico delle prove. In Ripasso intelligente puoi vedere gli argomenti da rinforzare e i quesiti che tornano più spesso tra gli errori.",
                    "muted",
                )
            )
            sessions = [s for s in self.store.sessions() if s["status"] == "submitted"][:5]
            table = data_table(
                ["Data", "Modalità", "Corrette", "Da valutare"],
                [
                    [
                        when(s["created_at"]),
                        s["mode"].capitalize(),
                        f"{s['correct']}/{s['total']}",
                        s["pending"],
                    ]
                    for s in sessions
                ],
            )
            table.doubleClicked.connect(lambda idx: window.open_session(sessions[idx.row()]["id"]))
            layout.addWidget(table)
        layout.addStretch()


class ResultsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, window.store
        self.page = 0
        self.page_size = 100
        layout = QVBoxLayout(self)
        layout.addWidget(label("Il tuo percorso", "heading"))
        layout.addWidget(
            label(
                "Le prove mantengono domande e soluzioni della versione utilizzata. I risultati pendenti richiedono la tua autovalutazione.",
                "muted",
            )
        )
        self.trash = QCheckBox("Mostra prove nel cestino")
        self.trash.toggled.connect(self.reset_page)
        layout.addWidget(self.trash)
        self.table = data_table(["Data", "Modalità", "Stato", "Corrette", "Da valutare"], [])
        self.table.doubleClicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self.update_actions)
        layout.addWidget(self.table, 1)
        self.open_button = button("Apri risultati", self.open_selected, primary=True)
        self.trash_button = button("Sposta nel cestino", lambda: self.action("trash"))
        self.restore_button = button("Ripristina", lambda: self.action("restore"))
        self.purge_button = button(
            "Elimina definitivamente", lambda: self.action("purge"), danger=True
        )
        layout.addLayout(
            row(
                self.open_button,
                self.trash_button,
                self.restore_button,
                self.purge_button,
                None,
            )
        )
        self.previous = button("Pagina precedente", lambda: self.change_page(-1))
        self.next = button("Pagina successiva", lambda: self.change_page(1))
        self.page_info = label("", "muted")
        layout.addLayout(row(self.previous, self.page_info, self.next))
        self.refresh()

    def reset_page(self, *_):
        self.page = 0
        self.refresh()

    def change_page(self, step):
        self.page += step
        self.refresh()

    def refresh(self, *_):
        total = self.store.session_count(self.trash.isChecked())
        last_page = max(0, (total - 1) // self.page_size)
        self.page = min(max(0, self.page), last_page)
        self.records = self.store.sessions(
            self.trash.isChecked(), self.page_size, self.page * self.page_size
        )
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(len(self.records))
        for i, s in enumerate(self.records):
            for j, text in enumerate(
                [
                    when(s["created_at"]),
                    s["mode"].capitalize(),
                    "In corso" if s["status"] == "active" else "Consegnata",
                    f"{s['correct']}/{s['total']}",
                    str(s["pending"]),
                ]
            ):
                self.table.setItem(i, j, QTableWidgetItem(text))
        start = self.page * self.page_size + 1 if total else 0
        end = min(total, (self.page + 1) * self.page_size)
        self.page_info.setText(
            f"Prove {start}–{end} di {total} · pagina {self.page + 1} di {last_page + 1}"
        )
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < last_page)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.update_actions()

    def update_actions(self):
        enabled = bool(self.table.selectedIndexes())
        in_trash = self.trash.isChecked()
        self.open_button.setEnabled(enabled)
        self.trash_button.setEnabled(enabled and not in_trash)
        self.restore_button.setEnabled(enabled and in_trash)
        self.purge_button.setEnabled(enabled and in_trash)

    def selected(self):
        index = self.table.currentRow()
        if index < 0:
            error(self, "Seleziona una prova.")
            return None
        return self.records[index]

    def open_selected(self, *_):
        s = self.selected()
        if s:
            self.window.open_session(s["id"])

    def action(self, action):
        s = self.selected()
        if not s:
            return
        if action == "purge" and not s["deleted_at"]:
            error(self, "Sposta prima la prova nel cestino.")
            return
        if action in ("purge", "trash") and not confirm(
            self,
            "Elimina prova",
            "Eliminare "
            + ("definitivamente " if action == "purge" else "dal percorso attivo ")
            + f"la prova del {when(s['created_at'])}, modalità {s['mode']}? Le statistiche saranno ricalcolate.",
        ):
            return
        try:
            self.store.session_action(s["id"], action)
            self.refresh()
        except Exception as exc:
            error(self, exc)


class LearningPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, window.store
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(label("Capisci dove migliorare", "heading"))
        self.layout.addWidget(
            label(
                "Memoria locale, suggerimenti basati sui tuoi risultati. Le autovalutazioni sono distinte dalle correzioni automatiche.",
                "muted",
            )
        )
        self.layout.addLayout(
            row(
                button(
                    "Allenami sui punti deboli",
                    lambda: window.new_quiz("intelligente"),
                    primary=True,
                ),
                button("Aggiorna analisi", self.refresh),
                None,
            )
        )
        self.content = QVBoxLayout()
        self.layout.addLayout(self.content, 1)
        self.refresh()

    def refresh(self):
        root = self.store.root

        def work(cancel, progress):
            store = Store(root)
            try:
                return store.dashboard()
            finally:
                store.close()

        ok, data = run_task(self, "Analisi dei progressi…", work)
        if not ok:
            return
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        counts = data["summary"]
        metrics = QWidget()
        metrics.setLayout(
            row(
                card("Tentativi ricordati", counts["attempts"]),
                card("Da recuperare", counts["unresolved"]),
                card("Ripassi previsti", counts["due"]),
            )
        )
        layout.addWidget(metrics)
        layout.addWidget(label("Situazione recente per argomento", "subheading"))
        layout.addWidget(
            label(
                "Finestra: ultimi 20 tentativi valutati. Servono almeno 5 risposte su 3 quesiti distinti per una conclusione. Una risposta parziale pesa come mezza difficoltà.",
                "muted",
            )
        )
        topics = data["topics"]
        rows = [
            [
                s["topic"],
                "Autovalutazione" if s["origin"] == "manuale" else "Automatica",
                f"{s['count']} / {s['distinct']}",
                f"{s['difficulty']:.0%}",
                "Dati insufficienti"
                if not s["enough"]
                else "Da rinforzare"
                if s["weak"]
                else "In consolidamento",
                s["trend"],
            ]
            for s in topics
        ]
        table = data_table(
            [
                "Argomento",
                "Valutazione",
                "Tentativi / quesiti",
                "Difficoltà",
                "Indicazione",
                "Andamento",
            ],
            rows,
        )
        table.setMinimumHeight(min(480, max(200, 50 + 38 * len(rows))))
        layout.addWidget(table)
        if not topics:
            layout.addWidget(
                label(
                    "Non ci sono ancora dati per argomento. Importa domande classificate e svolgi qualche allenamento.",
                    "muted",
                )
            )
        layout.addWidget(label("Risultati dall'ultimo azzeramento", "subheading"))
        totals = {}
        for r in data["totals"]:
            totals.setdefault((r["kind"], r["origin"]), Counter())[r["outcome"]] += r["count"]
        totals_table = data_table(
            ["Tipo", "Origine", "Corrette", "Parziali", "Sbagliate", "Omesse", "Da valutare"],
            [
                [
                    TYPES[kind],
                    origin,
                    c["corretta"],
                    c["parziale"],
                    c["sbagliata"],
                    c["omessa"],
                    c["da_valutare"],
                ]
                for (kind, origin), c in totals.items()
            ],
        )
        layout.addWidget(totals_table)
        layout.addWidget(label("Errori ricorrenti", "subheading"))
        recurring = data["recurring"]
        rec_table = data_table(
            ["Domanda", "Argomento", "Errori", "Stato", "Prossimo ripasso"],
            [
                [
                    json.loads(r["payload"])["testo"],
                    r["topic"],
                    r["wrong"],
                    "Da recuperare" if r["unresolved"] else "Recuperata",
                    when(r["due"]),
                ]
                for r in recurring
            ],
        )
        layout.addWidget(rec_table)
        layout.addWidget(
            label(
                "Sono mostrati fino a 30 quesiti ricorrenti. Per le risposte scelte e le note usa Archivio → Storico / note. Le raccolte archiviate o eliminate non alimentano il ripasso.",
                "muted",
            )
        )
        layout.addStretch()
        scroll.setWidget(widget)
        self.content.addWidget(scroll)
