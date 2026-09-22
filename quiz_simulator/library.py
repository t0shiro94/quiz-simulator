from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .dialogs import ExplanationDialog, ImportDialog, QuestionDialog, inspect_questions
from .domain import OUTCOMES, TYPES, answer_text, solution_text
from .importing import read_json, read_pdf
from .storage import Store
from .widgets import button, confirm, error, label, row, run_task


class LibraryPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, window.store
        self.offset, self.limit = 0, 50
        layout = QVBoxLayout(self)
        layout.addWidget(label("Il tuo archivio", "heading"))
        layout.addWidget(
            label("Organizza i contenuti. Ogni raccolta resta sotto il tuo controllo.", "muted")
        )
        layout.addLayout(
            row(
                button("Importa JSON o PDF", self.import_file, primary=True),
                button("Nuova raccolta", self.new_collection),
                button("Gestisci raccolta", self.collection_menu),
                None,
            )
        )
        self.collection = QComboBox()
        self.collection.setMinimumWidth(190)
        self.topic = QComboBox()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cerca nel testo delle domande…")
        self.favorite = QCheckBox("Preferiti")
        self.trash = QCheckBox("Domande nel cestino")
        layout.addLayout(row(self.collection, self.topic, self.search))
        layout.addLayout(row(self.favorite, self.trash, None))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["★", "Tipo", "Domanda", "Argomento", "Raccolta"])
        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(3, 155)
        self.table.setColumnWidth(4, 150)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.edit_question)
        self.table.itemSelectionChanged.connect(self.update_actions)
        layout.addWidget(self.table, 1)
        self.edit_button = button("Modifica", self.edit_question)
        self.topic_button = button("Argomento…", self.assign_topic)
        self.favorite_button = button("Preferito", self.toggle_favorite)
        self.history_button = button("Storico / note", self.history)
        layout.addLayout(
            row(
                button("Nuova domanda", self.new_question),
                self.edit_button,
                self.topic_button,
                self.favorite_button,
                self.history_button,
                None,
            )
        )
        self.trash_button = button("Elimina", self.trash_questions, danger=True)
        self.restore_button = button("Ripristina", self.restore_questions)
        self.purge_button = button("Elimina definitivamente", self.purge_questions, danger=True)
        layout.addLayout(
            row(
                self.trash_button,
                self.restore_button,
                self.purge_button,
                None,
            )
        )
        self.pagination = label("", "muted")
        self.prev = button("← Precedenti", lambda: self.turn_page(-1))
        self.next = button("Successive →", lambda: self.turn_page(1))
        layout.addLayout(row(self.pagination, None, self.prev, self.next))
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(250)
        self.debounce.timeout.connect(self.reset_page)
        self.search.textChanged.connect(lambda: self.debounce.start())
        self.collection.currentIndexChanged.connect(self.reset_page)
        self.topic.currentIndexChanged.connect(self.reset_page)
        self.favorite.stateChanged.connect(self.reset_page)
        self.trash.stateChanged.connect(self.reset_page)
        self.refresh_filters()
        self.refresh()

    def refresh_filters(self, selected=None):
        previous = selected or self.collection.currentData()
        self.collection.blockSignals(True)
        self.collection.clear()
        self.collection.addItem("Tutte le raccolte attive", None)
        for c in self.store.collections():
            self.collection.addItem(
                c["title"] + (" [archiviata]" if c["archived"] else ""), c["id"]
            )
        self.collection.setCurrentIndex(max(0, self.collection.findData(previous)))
        self.collection.blockSignals(False)
        current_topic = self.topic.currentData()
        self.topic.blockSignals(True)
        self.topic.clear()
        self.topic.addItem("Tutti gli argomenti", None)
        for topic in self.store.topics():
            self.topic.addItem(topic, topic)
        self.topic.setCurrentIndex(max(0, self.topic.findData(current_topic)))
        self.topic.blockSignals(False)

    def reset_page(self, *_):
        self.offset = 0
        self.refresh()

    def refresh(self):
        try:
            self.records, total = self.store.list_questions(
                limit=self.limit,
                offset=self.offset,
                collection=self.collection.currentData(),
                topic=self.topic.currentData(),
                search=self.search.text(),
                favorite=self.favorite.isChecked(),
                trash=self.trash.isChecked(),
            )
            if total and self.offset >= total:
                self.offset = ((total - 1) // self.limit) * self.limit
                self.records, total = self.store.list_questions(
                    limit=self.limit,
                    offset=self.offset,
                    collection=self.collection.currentData(),
                    topic=self.topic.currentData(),
                    search=self.search.text(),
                    favorite=self.favorite.isChecked(),
                    trash=self.trash.isChecked(),
                )
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self.table.setRowCount(len(self.records))
            for i, record in enumerate(self.records):
                q = json.loads(record["payload"])
                for j, text in enumerate(
                    [
                        "★" if record["favorite"] else "",
                        TYPES[q["tipo"]],
                        q["testo"],
                        q["argomento"],
                        record["collection_title"],
                    ]
                ):
                    cell = QTableWidgetItem(text)
                    cell.setToolTip(text)
                    self.table.setItem(i, j, cell)
            self.pagination.setText(
                f"{total:,} domande · {self.offset + 1 if total else 0}–{self.offset + len(self.records)}".replace(
                    ",", "."
                )
            )
            self.prev.setEnabled(self.offset > 0)
            self.next.setEnabled(self.offset + self.limit < total)
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self.update_actions()
        except Exception as exc:
            error(self, exc)

    def turn_page(self, delta):
        self.offset = max(0, self.offset + self.limit * delta)
        self.refresh()

    def selected(self):
        return [
            self.records[i]
            for i in sorted({cell.row() for cell in self.table.selectedIndexes()})
            if 0 <= i < len(self.records)
        ]

    def update_actions(self):
        enabled = bool(self.table.selectedIndexes())
        in_trash = self.trash.isChecked()
        for action in (
            self.edit_button,
            self.topic_button,
            self.favorite_button,
            self.trash_button,
        ):
            action.setEnabled(enabled and not in_trash)
        for action in (self.restore_button, self.purge_button):
            action.setEnabled(enabled and in_trash)
        self.history_button.setEnabled(enabled)

    @staticmethod
    def selection_description(records):
        names = [json.loads(record["payload"])["testo"].replace("\n", " ") for record in records]
        lines = [f"• {name[:90]}" for name in names[:3]]
        if len(names) > 3:
            lines.append(f"• … e altre {len(names) - 3}")
        return "\n".join(lines)

    def one(self):
        selection = self.selected()
        if not selection:
            error(self, "Seleziona una domanda.")
            return None
        return selection[0]

    def new_collection(self):
        title, ok = QInputDialog.getText(self, "Nuova raccolta", "Titolo:")
        if ok:
            try:
                cid = self.store.create_collection(title)
                self.refresh_filters(cid)
                self.reset_page()
            except Exception as exc:
                error(self, exc)

    def new_question(self):
        cid = self.collection.currentData()
        if not cid:
            error(self, "Seleziona una raccolta oppure creane una nuova.")
            return
        dialog = QuestionDialog(self)
        if dialog.exec():
            try:
                self.store.save_question(cid, dialog.result_question)
                self.refresh_filters(cid)
                self.refresh()
            except Exception as exc:
                error(self, exc)

    def edit_question(self, *_):
        record = self.one()
        if not record:
            return
        if record["deleted_at"]:
            error(self, "Ripristina la domanda prima di modificarla.")
            return
        dialog = QuestionDialog(self, json.loads(record["payload"]), existing=True)
        if dialog.exec():
            try:
                self.store.save_question(
                    record["collection_id"], dialog.result_question, record["pk"]
                )
                self.refresh_filters()
                self.refresh()
            except Exception as exc:
                error(self, exc)

    def assign_topic(self):
        records = self.selected()
        if not records:
            error(self, "Seleziona una o più domande.")
            return
        text, ok = QInputDialog.getItem(
            self, "Assegna argomento", "Argomento:", self.store.topics(), editable=True
        )
        if ok:
            self.store.set_topic([r["pk"] for r in records], text)
            self.refresh_filters()
            self.refresh()

    def toggle_favorite(self):
        for record in self.selected():
            self.store.set_favorite(record["pk"], not record["favorite"])
        self.refresh()

    def trash_questions(self):
        records = self.selected()
        if records and confirm(
            self,
            "Sposta nel cestino",
            f"Spostare {len(records)} domande nel cestino? I risultati precedenti restano disponibili.\n\n{self.selection_description(records)}",
        ):
            self.store.question_action([r["pk"] for r in records], "trash")
            self.refresh()

    def restore_questions(self):
        self.store.question_action([r["pk"] for r in self.selected()], "restore")
        self.refresh()

    def purge_questions(self):
        records = self.selected()
        if not records or any(r["deleted_at"] is None for r in records):
            error(self, "Seleziona soltanto domande già nel cestino.")
            return
        if confirm(
            self,
            "Eliminazione definitiva",
            "Eliminare definitivamente le domande selezionate e le loro note? Le copie nei risultati storici resteranno disponibili.\n\n"
            + self.selection_description(records),
        ):
            self.store.question_action([r["pk"] for r in records], "purge")
            self.refresh()

    def collection_menu(self):
        menu = QMenu(self)
        cid = self.collection.currentData()
        if cid:
            menu.addAction("Rinomina", self.rename_collection)
            menu.addAction("Esporta JSON", self.export_collection)
            c = next(c for c in self.store.collections() if c["id"] == cid)
            menu.addAction(
                "Riattiva" if c["archived"] else "Archivia",
                lambda: self.change_collection("unarchive" if c["archived"] else "archive"),
            )
            menu.addAction("Azzera memoria di apprendimento", self.reset_collection)
            menu.addAction("Sposta raccolta nel cestino", lambda: self.change_collection("trash"))
        menu.addAction("Cestino delle raccolte…", self.collection_trash)
        menu.exec(self.mapToGlobal(self.rect().center()))

    def rename_collection(self):
        cid = self.collection.currentData()
        text, ok = QInputDialog.getText(
            self, "Rinomina raccolta", "Titolo:", text=self.collection.currentText()
        )
        if ok:
            try:
                self.store.rename_collection(cid, text)
                self.refresh_filters(cid)
            except Exception as exc:
                error(self, exc)

    def export_collection(self):
        try:
            bank = self.store.export_bank(self.collection.currentData())
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Esporta raccolta",
                str(self.store.root / "esportazione.json"),
                "JSON (*.json)",
            )
            if path:
                Path(path).write_text(
                    json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.window.statusBar().showMessage("Raccolta esportata.", 5000)
        except Exception as exc:
            error(self, exc)

    def change_collection(self, action):
        cid = self.collection.currentData()
        if action == "trash" and not confirm(
            self,
            "Elimina raccolta",
            "Spostare la raccolta nel cestino? Potrai ripristinarla o eliminarla definitivamente, scegliendo cosa fare dello storico.",
        ):
            return
        self.store.collection_action(cid, action)
        self.refresh_filters()
        self.reset_page()

    def reset_collection(self):
        cid = self.collection.currentData()
        if confirm(
            self,
            "Azzera apprendimento",
            "Ripartire da zero con errori e ripassi di questa raccolta? Lo storico delle prove resterà consultabile e verrà creato un backup.",
        ):

            def work(cancel, progress):
                store = Store(self.store.root)
                try:
                    store.reset_learning(cid)
                finally:
                    store.close()

            run_task(self, "Azzeramento della memoria…", work)

    def collection_trash(self):
        collections = self.store.collections(trash=True)
        if not collections:
            error(self, "Il cestino delle raccolte è vuoto.")
            return
        names = [f"{c['title']} ({c['id'][:12]})" for c in collections]
        name, ok = QInputDialog.getItem(
            self, "Cestino raccolte", "Raccolta:", names, editable=False
        )
        if not ok:
            return
        c = collections[names.index(name)]
        actions = [
            "Ripristina raccolta",
            "Elimina definitivamente, conserva risultati",
            "Elimina definitivamente anche le prove collegate",
        ]
        action, ok = QInputDialog.getItem(
            self, "Gestisci raccolta eliminata", "Operazione:", actions, editable=False
        )
        if not ok:
            return
        if action == actions[0]:
            self.store.collection_action(c["id"], "restore")
        elif confirm(
            self,
            "Eliminazione definitiva",
            "Questa operazione non si può annullare dal cestino.\n"
            + (
                "Verranno eliminate interamente anche le prove miste che contengono domande di questa raccolta."
                if action == actions[2]
                else "Le copie dei quesiti presenti nei risultati verranno conservate."
            ),
        ):
            self.store.collection_action(c["id"], "purge", action == actions[2])
        self.refresh_filters()
        self.refresh()

    def import_file(self, path=None):
        if not isinstance(path, (str, Path)):
            path, _ = QFileDialog.getOpenFileName(
                self, "Importa quiz", str(self.store.root / "examples"), "Domande (*.json *.pdf)"
            )
        if not path:
            return
        path = Path(path)
        try:
            if path.suffix.lower() == ".pdf":
                dialog = QDialog(self)
                dialog.setWindowTitle("Pagine da importare")
                form = QFormLayout(dialog)
                start, end = QSpinBox(), QSpinBox()
                start.setRange(1, 100000)
                end.setRange(0, 100000)
                end.setSpecialValueText("Ultima pagina")
                form.addRow("Dalla pagina", start)
                form.addRow("Alla pagina", end)
                form.addRow(button("Leggi PDF", dialog.accept, primary=True))
                if not dialog.exec():
                    return
                first, last = start.value(), end.value() or None
                ok, result = run_task(
                    self,
                    "Lettura del PDF…",
                    lambda cancel, progress: read_pdf(path, first, last, progress, cancel),
                )
                if not ok:
                    return
                bank, warnings, pages = result
            else:
                ok, bank = run_task(
                    self, "Lettura del JSON…", lambda cancel, progress: read_json(path)
                )
                if not ok:
                    return
                warnings, pages = [], {}
            ok, validation = run_task(
                self,
                "Controllo delle domande…",
                lambda cancel, progress: inspect_questions(bank["domande"], cancel, progress),
            )
            if not ok:
                return
            review = ImportDialog(
                self, self.store, bank, path, warnings, pages, validation=validation
            )
            if review.exec():
                self.refresh_filters(review.imported_id)
                self.reset_page()
                self.window.statusBar().showMessage("Importazione completata.", 5000)
        except Exception as exc:
            error(self, exc)

    def history(self):
        record = self.one()
        if not record:
            return
        question = json.loads(record["payload"])
        dialog = QDialog(self)
        dialog.setWindowTitle("Domanda, storico e annotazioni")
        dialog.resize(820, 680)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        lines = [question["testo"], "\nSOLUZIONE\n" + solution_text(question), "\nSTORICO"]
        for item in self.store.question_history(record["pk"]):
            snapshot = json.loads(item["payload"])
            answer = json.loads(item["answer"]) if item["answer"] else None
            when = datetime.fromtimestamp(item["graded_at"]).strftime("%d/%m/%Y %H:%M")
            lines.append(
                f"{when} · {OUTCOMES.get(item['outcome'], '')} · {item['origin']} · versione {item['revision']}\n{answer_text(snapshot, answer)}"
            )
        view.setPlainText("\n\n".join(lines))
        layout.addWidget(view)
        item = {
            "question_pk": record["pk"],
            "revision": record["revision"],
            "question": question,
            "answer": None,
        }
        layout.addLayout(
            row(
                button(
                    "Spiegazioni e note", lambda: ExplanationDialog(dialog, self.store, item).exec()
                ),
                None,
                button("Chiudi", dialog.accept),
            )
        )
        dialog.exec()
