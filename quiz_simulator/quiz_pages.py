from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .dialogs import ExplanationDialog
from .domain import OUTCOMES, TYPES, normalize_short, solution_text
from .widgets import button, confirm, error, label, row


class NewQuizPage(QWidget):
    def __init__(self, window, mode="allenamento"):
        super().__init__()
        self.window, self.store = window, window.store
        layout = QVBoxLayout(self)
        layout.addWidget(label("Il prossimo passo", "heading"))
        layout.addWidget(
            label("Scegli una raccolta e comincia. Le opzioni avanzate sono facoltative.", "muted")
        )
        form = QFormLayout()
        self.collection = QComboBox()
        self.collection.addItem("Tutte le raccolte attive", None)
        for c in self.store.collections():
            if not c["archived"]:
                self.collection.addItem(f"{c['title']} · {c['count']} domande", c["id"])
        self.mode = QComboBox()
        for title, key in [
            ("Allenamento · correzione immediata", "allenamento"),
            ("Esame · correzione finale", "esame"),
            ("Intelligente · punti deboli e ripassi", "intelligente"),
        ]:
            self.mode.addItem(title, key)
        self.mode.setCurrentIndex(self.mode.findData(mode))
        self.count = QSpinBox()
        self.count.setRange(1, 1000)
        self.count.setValue(20)
        form.addRow("Raccolta", self.collection)
        form.addRow("Modalità", self.mode)
        form.addRow("Numero di domande", self.count)
        layout.addLayout(form)
        self.advanced_toggle = QCheckBox("Mostra opzioni avanzate")
        layout.addWidget(self.advanced_toggle)
        self.advanced = QGroupBox("Personalizza la prova")
        advanced = QFormLayout(self.advanced)
        self.topic = QComboBox()
        self.topic.addItem("Tutti gli argomenti", None)
        for topic in self.store.topics():
            self.topic.addItem(topic, topic)
        advanced.addRow("Argomento", self.topic)
        self.types = []
        types_widget = QWidget()
        types_layout = QVBoxLayout(types_widget)
        for key, title in TYPES.items():
            cb = QCheckBox(title)
            cb.setChecked(True)
            self.types.append((key, cb))
            types_layout.addWidget(cb)
        advanced.addRow("Tipi di domanda", types_widget)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 1440)
        self.minutes.setSpecialValueText("Senza timer")
        self.minutes.setSuffix(" minuti")
        advanced.addRow("Timer (solo esame)", self.minutes)
        self.shuffle = QCheckBox("Mescola le alternative")
        self.shuffle.setToolTip(
            "Lascia disattivato per alternative come 'tutte le precedenti' o riferimenti alle lettere."
        )
        advanced.addRow("Ordine", self.shuffle)
        self.favorite = QCheckBox("Solo domande preferite")
        advanced.addRow("Preferiti", self.favorite)
        self.correct, self.wrong, self.omitted = (
            QDoubleSpinBox(),
            QDoubleSpinBox(),
            QDoubleSpinBox(),
        )
        for widget in (self.correct, self.wrong, self.omitted):
            widget.setDecimals(2)
            widget.setRange(-100, 100)
        self.correct.setMinimum(0.01)
        self.correct.setValue(1)
        advanced.addRow("Punti per corretta", self.correct)
        advanced.addRow("Punti per sbagliata", self.wrong)
        advanced.addRow("Punti per omessa", self.omitted)
        advanced.addRow(
            label(
                "I testi liberi parziali valgono metà del punteggio pieno. La scelta multipla richiede tutte e soltanto le alternative corrette.",
                "muted",
            )
        )
        layout.addWidget(self.advanced)
        self.advanced.setVisible(False)
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        layout.addLayout(row(button("Inizia il quiz", self.start, primary=True), None))
        layout.addStretch()

    def start(self):
        kinds = [key for key, cb in self.types if cb.isChecked()]
        if not kinds:
            error(self, "Seleziona almeno un tipo di domanda.")
            return
        try:
            if self.store.active_session():
                self.window.open_session(self.store.active_session())
                return
            sid = self.store.create_session(
                self.mode.currentData(),
                self.count.value(),
                {
                    "collection": self.collection.currentData(),
                    "topic": self.topic.currentData(),
                    "kinds": kinds,
                    "favorite": self.favorite.isChecked(),
                },
                {
                    "correct_points": self.correct.value(),
                    "wrong_points": self.wrong.value(),
                    "omitted_points": self.omitted.value(),
                    "minutes": self.minutes.value(),
                    "shuffle_options": self.shuffle.isChecked(),
                },
            )
            self.window.open_session(sid)
        except Exception as exc:
            error(self, exc)


class QuizPage(QWidget):
    def __init__(self, window, sid):
        super().__init__()
        self.window, self.store, self.sid = window, window.store, sid
        self.loading = False
        self.index = self.store.session(sid)["current_index"]
        self.store.check_deadline(sid)
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(200)
        self.autosave.timeout.connect(self.persist)
        layout = QVBoxLayout(self)
        self.heading = label("", "heading")
        self.summary = label("", "muted")
        self.timer_label = label("", "timer")
        layout.addLayout(row(self.heading, None, self.timer_label))
        layout.addWidget(self.summary)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        splitter = QSplitter()
        self.navigator = QListWidget()
        self.navigator.setMaximumWidth(200)
        self.navigator.currentRowChanged.connect(self.jump)
        splitter.addWidget(self.navigator)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        scroll.setWidget(self.body)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        self.previous = button("← Precedente", lambda: self.go(-1))
        self.confirm_button = button("Conferma risposta", self.confirm_answer, primary=True)
        self.next = button("Avanti →", lambda: self.go(1))
        self.finish = button("Termina e vedi risultati", self.submit, primary=True)
        layout.addLayout(row(self.previous, self.confirm_button, self.next, None, self.finish))
        self.refresh()

    def clear_body(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def refresh(self):
        self.loading = True
        self.session = self.store.session(self.sid)
        if not self.session["items"]:
            return
        self.index = min(max(0, self.index), len(self.session["items"]) - 1)
        self.item = self.session["items"][self.index]
        q = self.item["question"]
        active = self.session["status"] == "active"
        exam = self.session["mode"] == "esame"
        revealed = not active or (self.item["confirmed"] and not exam)
        self.heading.setText("La tua prova" if active else "Risultati e revisione")
        info = self.store.session_summary(self.sid)
        if active:
            done = sum(i["confirmed"] or bool(i["answer"]) for i in self.session["items"])
            self.summary.setText(
                f"{self.session['mode'].capitalize()} · Domanda {self.index + 1} di {len(self.session['items'])} · {done} risposte inserite"
            )
        else:
            counts = info["counts"]
            pending = info["pending"]
            self.summary.setText(
                f"{counts.get('corretta', 0)} corrette · {counts.get('parziale', 0)} parziali · {counts.get('sbagliata', 0)} sbagliate · {counts.get('omessa', 0)} omesse\n"
                + (
                    f"Punteggio provvisorio: {info['points']:g} · {pending} risposte da valutare"
                    if pending
                    else f"Punteggio: {info['points']:g} · Corrette sul totale: {info['correct_percent']:.0f}%"
                )
            )
        self.progress.setRange(0, len(self.session["items"]))
        self.progress.setValue(sum(bool(i["confirmed"]) for i in self.session["items"]))
        self.navigator.blockSignals(True)
        self.navigator.clear()
        for i, item in enumerate(self.session["items"]):
            if exam and active:
                status = "Risposta inserita" if item["answer"] else "Da rispondere"
            else:
                status = OUTCOMES.get(
                    item["outcome"], "Bozza" if item["answer"] else "Da rispondere"
                )
            self.navigator.addItem(f"{i + 1}. {status}")
        self.navigator.setCurrentRow(self.index)
        self.navigator.blockSignals(False)
        self.clear_body()
        self.body_layout.addWidget(
            label(q.get("argomento", "Da classificare") + "  ·  " + TYPES[q["tipo"]], "eyebrow")
        )
        self.body_layout.addWidget(label(q["testo"], "question"))
        if self.session["mode"] == "intelligente":
            self.body_layout.addWidget(
                label("Perché questa domanda: " + self.item["reason"], "muted")
            )
        hint = {
            "scelta_singola": "Scegli una risposta.",
            "scelta_multipla": "Seleziona tutte le risposte corrette.",
            "aperta_breve": "Scrivi una risposta breve.",
            "aperta_libera": "Scrivi la tua risposta. Dopo la conferma potrai confrontarla con i criteri.",
        }
        self.body_layout.addWidget(label(hint[q["tipo"]], "muted"))
        self.choice_controls = []
        self.input = None
        if q["tipo"].startswith("scelta"):
            self.group = None if revealed else QButtonGroup(self.body)
            if self.group:
                self.group.setExclusive(q["tipo"] == "scelta_singola")
            for option in q["risposte"]:
                prefix = ""
                state = "neutral"
                if revealed and option["id"] in q["corrette"]:
                    prefix = "✓ Corretta · "
                    state = "correct"
                elif revealed and option["id"] in (self.item["answer"] or []):
                    prefix = "✗ La tua scelta · "
                    state = "wrong"
                if revealed:
                    control = label(prefix + option["id"] + ") " + option["testo"], "answerOption")
                    control.setProperty("answerState", state)
                else:
                    control = QRadioButton() if q["tipo"] == "scelta_singola" else QCheckBox()
                    control.setText(option["id"] + ") " + option["testo"])
                    control.setChecked(option["id"] in (self.item["answer"] or []))
                    self.group.addButton(control)
                    control.toggled.connect(self.schedule_save)
                control.setToolTip(option["testo"])
                control.setMinimumHeight(42)
                self.choice_controls.append((option["id"], control))
                self.body_layout.addWidget(control)
        else:
            self.input = QLineEdit() if q["tipo"] == "aperta_breve" else QPlainTextEdit()
            if isinstance(self.input, QLineEdit):
                self.input.setText(self.item["answer"] or "")
                self.input.returnPressed.connect(self.confirm_answer)
            else:
                self.input.setPlainText(self.item["answer"] or "")
                self.input.setMinimumHeight(170)
            self.input.setReadOnly(revealed)
            self.input.textChanged.connect(self.schedule_save)
            self.body_layout.addWidget(self.input)
        if revealed:
            result = QFrame()
            result.setObjectName("feedback")
            result_layout = QVBoxLayout(result)
            result_layout.addWidget(
                label(
                    OUTCOMES.get(self.item["outcome"], "Da valutare")
                    + (
                        " · autovalutazione / rettifica"
                        if self.item["origin"] == "manuale"
                        else " · correzione automatica"
                    ),
                    "subheading",
                )
            )
            result_layout.addWidget(label("Soluzione della fonte", "eyebrow"))
            result_layout.addWidget(label(solution_text(q)))
            if q.get("spiegazione"):
                result_layout.addWidget(label(q["spiegazione"]))
            self.body_layout.addWidget(result)
            if (
                q["tipo"].startswith("aperta")
                and isinstance(self.item["answer"], str)
                and self.item["answer"].strip()
            ):
                self.body_layout.addWidget(
                    label(
                        "Confronta la tua risposta e scegli una valutazione. Le rettifiche saranno indicate come manuali.",
                        "muted",
                    )
                )
                self.body_layout.addLayout(
                    row(
                        button("Corretta", lambda: self.grade("corretta")),
                        button("Parziale", lambda: self.grade("parziale")),
                        button("Sbagliata", lambda: self.grade("sbagliata")),
                        None,
                    )
                )
                if q["tipo"] == "aperta_breve" and self.item["question_pk"]:
                    self.body_layout.addWidget(
                        button("Aggiungi la mia risposta alle varianti ammesse", self.add_variant)
                    )
            self.body_layout.addWidget(button("Spiegami con ChatGPT / note", self.explain))
        if self.item["question_pk"]:
            self.body_layout.addWidget(button("Aggiungi / rimuovi dai preferiti", self.favorite))
        self.body_layout.addStretch()
        self.previous.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < len(self.session["items"]) - 1)
        self.confirm_button.setVisible(active and not exam)
        self.confirm_button.setEnabled(not self.item["confirmed"])
        self.finish.setVisible(active)
        self.loading = False
        self.tick()

    def answer(self):
        if self.choice_controls:
            return [key for key, control in self.choice_controls if control.isChecked()]
        if isinstance(self.input, QLineEdit):
            return self.input.text()
        return self.input.toPlainText() if self.input else None

    def schedule_save(self, *_):
        if not self.loading:
            self.autosave.start()

    def persist(self):
        self.autosave.stop()
        if (
            self.loading
            or not hasattr(self, "item")
            or self.session["status"] != "active"
            or self.item["confirmed"]
        ):
            return
        try:
            self.store.save_answer(self.sid, self.index, self.answer())
        except ValueError as exc:
            if self.store.session(self.sid)["status"] != "active":
                self.refresh()
            else:
                self.window.statusBar().showMessage(str(exc), 5000)

    def confirm_answer(self):
        if (
            self.session["mode"] == "esame"
            or self.session["status"] != "active"
            or self.item["confirmed"]
        ):
            return
        self.autosave.stop()
        try:
            self.store.save_answer(self.sid, self.index, self.answer(), confirm=True)
            self.refresh()
        except Exception as exc:
            error(self, exc)

    def jump(self, index):
        if self.loading or index < 0 or index == self.index:
            return
        self.persist()
        self.index = index
        with self.store.db:
            self.store.db.execute(
                "UPDATE sessions SET current_index=? WHERE id=?", (index, self.sid)
            )
        self.refresh()

    def go(self, delta):
        self.jump(self.index + delta)

    def submit(self):
        self.persist()
        message = "Consegnare la prova e visualizzare i risultati?"
        if self.session["mode"] != "esame":
            message += " Le bozze non confermate saranno considerate omesse."
        if confirm(self, "Termina prova", message):
            self.store.submit(self.sid)
            self.refresh()
            self.window.update_nav()

    def grade(self, outcome):
        try:
            self.store.manual_grade(self.sid, self.index, outcome)
            self.refresh()
        except Exception as exc:
            error(self, exc)

    def add_variant(self):
        try:
            record = self.store.question(self.item["question_pk"])
            if record["revision"] != self.item["revision"]:
                error(
                    self,
                    "La domanda è stata modificata dopo questa prova. Aggiungi la variante dall'archivio.",
                )
                return
            variant = str(self.item["answer"]).strip()
            if confirm(
                self,
                "Aggiorna varianti",
                f"Aggiungere «{variant}» alle risposte ammesse? Verrà creata una nuova versione della domanda; questa risposta sarà rettificata manualmente.",
            ):
                q = record["question"]
                if normalize_short(variant) not in {
                    normalize_short(answer) for answer in q["risposte_ammesse"]
                }:
                    q["risposte_ammesse"].append(variant)
                    self.store.save_question(record["collection_id"], q, record["pk"])
                self.store.manual_grade(self.sid, self.index, "corretta")
                self.refresh()
        except Exception as exc:
            error(self, exc)

    def explain(self):
        ExplanationDialog(self, self.store, self.item).exec()

    def favorite(self):
        record = self.store.question(self.item["question_pk"])
        self.store.set_favorite(record["pk"], not record["favorite"])
        self.window.statusBar().showMessage("Preferiti aggiornati.", 3000)

    def tick(self):
        deadline = self.session.get("deadline")
        if self.session["status"] == "active" and deadline:
            remaining = max(0, int(deadline - time.time()))
            self.timer_label.setText(f"{remaining // 60:02d}:{remaining % 60:02d}")
        else:
            self.timer_label.setText("")
