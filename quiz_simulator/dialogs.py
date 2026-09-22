from __future__ import annotations

import copy
import uuid
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .domain import TYPES, UNTAGGED, explanation_prompt, question_errors
from .storage import Store
from .widgets import button, confirm, error, label, row, run_task


def inspect_questions(questions, cancelled=None, progress=None):
    """Controlla le domande senza creare migliaia di righe nell'interfaccia."""
    counts = Counter(question.get("id", "") for question in questions)
    inspected = []
    total = max(1, len(questions))
    for index, question in enumerate(questions):
        if cancelled and cancelled():
            raise ValueError("Controllo annullato.")
        messages = question_errors(question)
        if counts[question.get("id", "")] > 1:
            messages.append("Identificatore duplicato")
        inspected.append(messages)
        if progress and index % 100 == 0:
            progress(int(100 * (index + 1) / total))
    return inspected


class QuestionDialog(QDialog):
    def __init__(self, parent, question=None, existing=False):
        super().__init__(parent)
        self.setWindowTitle("Modifica domanda" if question else "Nuova domanda")
        self.resize(780, 760)
        self.result_question = None
        q = copy.deepcopy(
            question or {"id": uuid.uuid4().hex[:12], "tipo": "scelta_singola", "testo": ""}
        )
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.ident = QLineEdit(str(q.get("id", "")))
        self.ident.setReadOnly(existing)
        self.kind = QComboBox()
        for key, value in TYPES.items():
            self.kind.addItem(value, key)
        self.kind.setCurrentIndex(max(0, self.kind.findData(q.get("tipo"))))
        self.topic = QLineEdit(q.get("argomento", ""))
        self.topic.setPlaceholderText(
            "Es. Capitali europee; serve per le statistiche per argomento"
        )
        self.text = QPlainTextEdit(q.get("testo", ""))
        self.text.setMinimumHeight(110)
        form.addRow("Identificatore", self.ident)
        form.addRow("Tipo", self.kind)
        form.addRow("Argomento", self.topic)
        form.addRow("Domanda", self.text)
        self.stack = QStackedWidget()
        choices = QWidget()
        choice_form = QFormLayout(choices)
        self.options = QPlainTextEdit(
            "\n".join(f"{r.get('id', '')} | {r.get('testo', '')}" for r in q.get("risposte", []))
            or "A | \nB | \nC | \nD | "
        )
        self.options.setPlaceholderText("Una alternativa per riga: A | Testo della risposta")
        self.correct = QLineEdit(", ".join(q.get("corrette", [])))
        self.correct.setPlaceholderText("Es. B oppure A, C")
        choice_form.addRow(
            label("Una alternativa per riga, nel formato identificatore | testo", "muted")
        )
        choice_form.addRow("Alternative", self.options)
        choice_form.addRow("Corrette", self.correct)
        self.stack.addWidget(choices)
        short = QWidget()
        short_form = QFormLayout(short)
        self.accepted = QPlainTextEdit("\n".join(q.get("risposte_ammesse", [])))
        short_form.addRow(
            label(
                "Inserisci una risposta ammessa per riga. Maiuscole e spazi sono ignorati; simboli e accenti restano significativi.",
                "muted",
            )
        )
        short_form.addRow("Varianti ammesse", self.accepted)
        self.stack.addWidget(short)
        free = QWidget()
        free_form = QFormLayout(free)
        self.model = QPlainTextEdit(q.get("risposta_modello", ""))
        self.criteria = QPlainTextEdit("\n".join(q.get("criteri", [])))
        free_form.addRow("Risposta modello", self.model)
        free_form.addRow("Criteri (uno per riga)", self.criteria)
        self.stack.addWidget(free)
        form.addRow(self.stack)
        self.explanation = QPlainTextEdit(q.get("spiegazione", ""))
        self.explanation.setMaximumHeight(100)
        form.addRow("Spiegazione della fonte", self.explanation)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.validation = label("", "error")
        layout.addWidget(self.validation)
        layout.addLayout(
            row(
                None,
                button("Annulla", self.reject),
                button("Salva domanda", self.save, primary=True),
            )
        )
        self.kind.currentIndexChanged.connect(self.change_kind)
        self.change_kind()

    def change_kind(self):
        kind = self.kind.currentData()
        self.stack.setCurrentIndex(
            0 if kind.startswith("scelta") else 1 if kind == "aperta_breve" else 2
        )

    def save(self):
        kind = self.kind.currentData()
        q = {
            "id": self.ident.text().strip(),
            "tipo": kind,
            "testo": self.text.toPlainText().strip(),
            "argomento": self.topic.text().strip() or UNTAGGED,
        }
        if kind.startswith("scelta"):
            options = []
            for line in self.options.toPlainText().splitlines():
                if not line.strip():
                    continue
                if "|" not in line:
                    self.validation.setText(
                        "Ogni alternativa deve contenere | tra identificatore e testo."
                    )
                    return
                key, text = line.split("|", 1)
                # Le righe segnaposto non compilate possono restare vuote.
                if text.strip():
                    options.append({"id": key.strip(), "testo": text.strip()})
            q["risposte"] = options
            q["corrette"] = [x.strip() for x in self.correct.text().split(",") if x.strip()]
        elif kind == "aperta_breve":
            q["risposte_ammesse"] = [
                x.strip() for x in self.accepted.toPlainText().splitlines() if x.strip()
            ]
        else:
            q["risposta_modello"] = self.model.toPlainText().strip()
            q["criteri"] = [
                x.strip() for x in self.criteria.toPlainText().splitlines() if x.strip()
            ]
        if self.explanation.toPlainText().strip():
            q["spiegazione"] = self.explanation.toPlainText().strip()
        errors = question_errors(q)
        if errors:
            self.validation.setText("\n".join(errors[:4]))
            return
        self.result_question = q
        self.accept()


class ImportDialog(QDialog):
    def __init__(
        self, parent, store, bank, source=None, warnings=None, pages=None, validation=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Controlla l'importazione")
        self.resize(1200, 820)
        self.store, self.bank, self.source = (
            store,
            copy.deepcopy(bank),
            Path(source) if source else None,
        )
        self.pages = pages or {}
        self.imported_id = None
        self.page = 0
        self.page_size = 200
        self.validation = validation or inspect_questions(self.bank["domande"])
        self.included = {index for index, messages in enumerate(self.validation) if not messages}
        layout = QVBoxLayout(self)
        layout.addWidget(label("Controlla, classifica e importa", "heading"))
        layout.addWidget(
            label(
                "Le domande con errori non sono selezionate. Correggile oppure importa soltanto quelle valide.",
                "muted",
            )
        )
        form = QFormLayout()
        self.title = QLineEdit(bank.get("titolo", ""))
        self.ident = QLineEdit(bank.get("id", uuid.uuid4().hex))
        form.addRow("Titolo raccolta", self.title)
        form.addRow("ID raccolta", self.ident)
        layout.addLayout(form)
        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Importa", "Domanda", "Argomento", "Controllo"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 65)
        self.table.setColumnWidth(2, 155)
        self.table.setColumnWidth(3, 180)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self.show_pdf_page)
        self.table.itemChanged.connect(self.choice_changed)
        left_layout.addWidget(self.table)
        left_layout.addLayout(
            row(
                button("Modifica", self.edit_selected),
                button("Aggiungi domanda", self.add_question),
                button("Assegna argomento", self.assign_topic),
            )
        )
        self.previous = button("← Precedenti", lambda: self.change_page(-1))
        self.next = button("Successive →", lambda: self.change_page(1))
        self.page_label = label("", "muted")
        left_layout.addLayout(
            row(
                button("Seleziona tutte le valide", lambda: self.select_all(True)),
                button("Deseleziona tutte", lambda: self.select_all(False)),
            )
        )
        left_layout.addLayout(row(self.previous, self.page_label, self.next))
        splitter.addWidget(left)
        if self.source and self.source.suffix.lower() == ".pdf":
            self.pdf = QPdfDocument(self)
            self.pdf.load(str(self.source))
            self.viewer = QPdfView()
            self.viewer.setDocument(self.pdf)
            self.viewer.setPageMode(QPdfView.PageMode.MultiPage)
            self.viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            splitter.addWidget(self.viewer)
            splitter.setSizes([650, 450])
        layout.addWidget(splitter, 1)
        self.warning_label = label("\n".join((warnings or [])[:8]), "error")
        self.warning_label.setMaximumHeight(95)
        self.warning_label.setToolTip("\n".join(warnings or []))
        layout.addWidget(self.warning_label)
        self.mode = QComboBox()
        for text, key in [
            ("Crea nuova raccolta", "create"),
            ("Aggiorna raccolta", "update"),
            ("Sostituisci raccolta", "replace"),
        ]:
            self.mode.addItem(text, key)
        self.target = QComboBox()
        for c in store.collections():
            self.target.addItem(c["title"], c["id"])
        if self.target.findData(bank.get("id")) >= 0:
            self.mode.setCurrentIndex(1)
            self.target.setCurrentIndex(self.target.findData(bank["id"]))
        self.keep = QCheckBox("Mantieni i progressi delle domande identiche")
        self.keep.setChecked(True)
        self.mode.currentIndexChanged.connect(self.update_mode)
        layout.addLayout(row(self.mode, self.target))
        layout.addWidget(self.keep)
        self.summary = label("", "muted")
        layout.addWidget(self.summary)
        layout.addLayout(
            row(
                None,
                button("Annulla", self.reject),
                button("Controlla e importa", self.import_now, primary=True),
            )
        )
        self.refresh()
        self.update_mode()

    def update_mode(self):
        self.target.setEnabled(self.mode.currentData() != "create")
        self.ident.setEnabled(self.mode.currentData() == "create")
        self.keep.setEnabled(self.mode.currentData() != "create")

    def remember_choices(self):
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, 0)
            question_index = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self.included.add(question_index)
            else:
                self.included.discard(question_index)

    def refresh(self, remember=True):
        if remember:
            self.remember_choices()
        total = len(self.bank["domande"])
        last_page = max(0, (total - 1) // self.page_size)
        self.page = min(max(0, self.page), last_page)
        start = self.page * self.page_size
        stop = min(total, start + self.page_size)
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.setRowCount(stop - start)
        for row_index, question_index in enumerate(range(start, stop)):
            q = self.bank["domande"][question_index]
            errors = self.validation[question_index]
            ident = q.get("id", "")
            checked = QTableWidgetItem()
            checked.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            checked.setData(Qt.ItemDataRole.UserRole, question_index)
            checked.setCheckState(
                Qt.CheckState.Checked
                if question_index in self.included
                else Qt.CheckState.Unchecked
            )
            self.table.setItem(row_index, 0, checked)
            self.table.setItem(row_index, 1, QTableWidgetItem(f"{ident}. {q.get('testo', '')}"))
            self.table.setItem(row_index, 2, QTableWidgetItem(q.get("argomento") or UNTAGGED))
            state = QTableWidgetItem("Da correggere" if errors else "Valida")
            state.setToolTip("\n".join(errors))
            self.table.setItem(row_index, 3, state)
        valid = sum(not messages for messages in self.validation)
        self.summary.setText(
            f"{total} domande riconosciute · {valid} valide · {total - valid} da correggere · {len(self.included)} selezionate"
        )
        self.page_label.setText(
            f"{start + 1 if total else 0}–{stop} di {total} · pagina {self.page + 1}/{last_page + 1}"
        )
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < last_page)
        self.table.blockSignals(False)

    def choice_changed(self, item):
        if item.column() != 0:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.included.add(index)
        else:
            self.included.discard(index)
        valid = sum(not messages for messages in self.validation)
        total = len(self.bank["domande"])
        self.summary.setText(
            f"{total} domande riconosciute · {valid} valide · {total - valid} da correggere · {len(self.included)} selezionate"
        )

    def change_page(self, step):
        self.remember_choices()
        self.page += step
        self.refresh(remember=False)

    def select_all(self, include):
        self.remember_choices()
        self.included = (
            {index for index, messages in enumerate(self.validation) if not messages}
            if include
            else set()
        )
        self.refresh(remember=False)

    def revalidate(self):
        questions = copy.deepcopy(self.bank["domande"])
        ok, validation = run_task(
            self,
            "Controllo delle domande…",
            lambda cancelled, progress: inspect_questions(questions, cancelled, progress),
        )
        if ok:
            self.validation = validation
            self.included.difference_update(
                index for index, messages in enumerate(validation) if messages
            )
        return ok

    def selected_question_indexes(self):
        return {
            self.table.item(cell.row(), 0).data(Qt.ItemDataRole.UserRole)
            for cell in self.table.selectedIndexes()
        }

    def edit_selected(self, *_):
        row_index = self.table.currentRow()
        if row_index < 0:
            return
        self.remember_choices()
        index = self.table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
        was_invalid = bool(self.validation[index])
        previous = copy.deepcopy(self.bank["domande"][index])
        dialog = QuestionDialog(self, self.bank["domande"][index])
        if dialog.exec():
            self.bank["domande"][index] = dialog.result_question
            if self.revalidate():
                if was_invalid and not self.validation[index]:
                    self.included.add(index)
                self.refresh(remember=False)
            else:
                self.bank["domande"][index] = previous

    def add_question(self):
        dialog = QuestionDialog(self)
        if dialog.exec():
            self.bank["domande"].append(dialog.result_question)
            new_index = len(self.bank["domande"]) - 1
            self.included.add(new_index)
            if self.revalidate():
                self.page = new_index // self.page_size
                self.refresh(remember=False)
            else:
                self.bank["domande"].pop()
                self.included.discard(new_index)

    def assign_topic(self):
        selected = self.selected_question_indexes()
        if not selected:
            error(self, "Seleziona una o più righe. Usa Ctrl o Maiusc per selezioni multiple.")
            return
        text, ok = QInputDialog.getText(
            self, "Assegna argomento", "Argomento per le domande selezionate:"
        )
        if ok:
            for i in selected:
                self.bank["domande"][i]["argomento"] = text.strip() or UNTAGGED
            self.refresh()

    def show_pdf_page(self):
        if hasattr(self, "viewer") and self.table.currentRow() >= 0:
            index = self.table.item(self.table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
            q = self.bank["domande"][index]
            page = self.pages.get(q.get("id"), 1)
            from PySide6.QtCore import QPointF

            self.viewer.pageNavigator().jump(page - 1, QPointF(0, 0))

    def import_now(self):
        self.remember_choices()
        bank = {
            "versione_schema": 2,
            "id": self.ident.text().strip(),
            "titolo": self.title.text().strip(),
            "domande": [q for i, q in enumerate(self.bank["domande"]) if i in self.included],
        }
        mode, target = (
            self.mode.currentData(),
            self.target.currentData() if self.mode.currentData() != "create" else None,
        )
        try:
            details = self.store.preview_import(bank, target)
        except Exception as exc:
            error(self, exc)
            return
        message = (
            f"Nuove: {details['new']}\nModificate: {details['changed']}\nIdentiche: {details['identical']}\n"
            f"Rimosse dalla raccolta: {details['removed'] if mode == 'replace' else 0}"
        )
        if mode == "replace":
            message += (
                "\n\nLe domande rimosse andranno nel cestino. Verrà creato un backup preventivo."
            )
        if not confirm(self, "Riepilogo importazione", message):
            return
        root, source, keep = self.store.root, self.source, self.keep.isChecked()

        def work(cancelled, progress):
            worker_store = Store(root)
            try:
                return worker_store.import_bank(
                    bank, mode, target, keep, source, cancelled, progress
                )
            finally:
                worker_store.close()

        ok, value = run_task(self, "Importazione delle domande…", work)
        if ok:
            self.imported_id = value
            self.accept()


class ExplanationDialog(QDialog):
    def __init__(self, parent, store, item):
        super().__init__(parent)
        self.store, self.item = store, item
        self.setWindowTitle("Spiegazione e annotazioni")
        self.resize(820, 720)
        layout = QVBoxLayout(self)
        layout.addWidget(label("Approfondisci con ChatGPT", "heading"))
        layout.addWidget(
            label(
                "Copia la richiesta, apri ChatGPT e incollala nella chat con il tuo account. Il simulatore non invia dati automaticamente.",
                "muted",
            )
        )
        self.prompt = QPlainTextEdit(explanation_prompt(item["question"], item.get("answer")))
        self.prompt.setMaximumHeight(240)
        layout.addWidget(self.prompt)
        layout.addLayout(
            row(
                button("Copia richiesta", self.copy_prompt),
                button("Copia e apri ChatGPT", self.open_chat, primary=True),
                None,
            )
        )
        layout.addWidget(label("Incolla qui la spiegazione ricevuta oppure scrivi una tua nota"))
        self.note = QPlainTextEdit()
        layout.addWidget(self.note)
        self.source = QComboBox()
        self.source.addItems(["ChatGPT · riportata dall'utente", "Nota personale"])
        layout.addWidget(self.source)
        pk = item.get("question_pk")
        self.saved = QPlainTextEdit()
        self.saved.setReadOnly(True)
        self.saved.setMaximumHeight(130)
        layout.addWidget(self.saved)
        self.refresh_notes()
        save = button("Salva spiegazione", self.save_note, primary=True)
        save.setEnabled(pk is not None)
        layout.addLayout(
            row(
                button("Elimina una nota", self.remove_note),
                None,
                button("Chiudi", self.accept),
                save,
            )
        )

    def copy_prompt(self):
        QApplication.clipboard().setText(self.prompt.toPlainText())

    def open_chat(self):
        self.copy_prompt()
        if not QDesktopServices.openUrl(QUrl("https://chatgpt.com/")):
            error(self, "Richiesta copiata. Apri manualmente chatgpt.com nel browser.")

    def refresh_notes(self):
        self.notes = (
            self.store.notes(self.item.get("question_pk"), self.item["revision"])
            if self.item.get("question_pk")
            else []
        )
        self.saved.setPlainText(
            "\n\n".join(f"{n['source']}\n{n['text']}" for n in self.notes)
            or "Nessuna spiegazione salvata per questa versione della domanda."
        )

    def save_note(self):
        try:
            self.store.add_note(
                self.item["question_pk"],
                self.item["revision"],
                self.note.toPlainText(),
                self.source.currentText(),
            )
            self.note.clear()
            self.refresh_notes()
        except Exception as exc:
            error(self, exc)

    def remove_note(self):
        if not self.notes:
            return
        titles = [f"{i + 1}. {n['text'][:80]}" for i, n in enumerate(self.notes)]
        title, ok = QInputDialog.getItem(
            self, "Elimina nota", "Nota da eliminare:", titles, editable=False
        )
        if ok and confirm(self, "Elimina nota", "Eliminare definitivamente questa annotazione?"):
            self.store.delete_note(self.notes[titles.index(title)]["pk"])
            self.refresh_notes()
