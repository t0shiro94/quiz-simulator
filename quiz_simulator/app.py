from __future__ import annotations

import json
import logging
import sys
import time

from PySide6.QtCore import QLockFile, QModelIndex, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .library import LibraryPage
from .paths import app_root, resource
from .quiz_pages import NewQuizPage, QuizPage
from .report_pages import HomePage, LearningPage, ResultsPage
from .storage import Store
from .widgets import button, confirm, error, label, row, run_task

STYLE = """
QWidget { color: #203940; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow, QWidget#workspace { background: #f3f6f5; }
QFrame#sidebar { background: #14343d; border: none; }
QFrame#sidebar QLabel { color: #d4e9e7; background: transparent; }
QFrame#sidebar QLabel#brand { font-size: 24px; font-weight: 700; color: white; }
QListWidget#nav { background: transparent; color: #d4e9e7; border: none; outline: 0; }
QListWidget#nav::item { padding: 14px 14px; margin: 3px 0; border-radius: 7px; }
QListWidget#nav::item:selected { background: #256068; color: white; }
QListWidget#nav::item:hover { background: #204b55; }
QLabel { background: transparent; }
QLabel#heading { font-size: 28px; font-weight: 700; padding-bottom: 6px; color: #14343d; }
QLabel#subheading { font-size: 19px; font-weight: 600; padding-top: 8px; }
QLabel#question { font-size: 23px; font-weight: 600; padding: 14px 0; }
QLabel#eyebrow { color: #277d7d; font-size: 13px; font-weight: 600; }
QLabel#muted { color: #637b80; padding-bottom: 5px; }
QLabel#error { color: #a53e35; }
QLabel#timer { font-size: 24px; font-weight: 700; color: #277d7d; }
QLabel#metric { font-size: 31px; font-weight: 700; color: #14343d; }
QFrame#card { background: white; border: 1px solid #dbe6e3; border-radius: 10px; padding: 14px; }
QFrame#feedback { background: #e5f1ed; border: 1px solid #bfdad1; border-radius: 9px; padding: 14px; }
QPushButton { background: white; color: #25464d; border: 1px solid #c8d8d5; border-radius: 6px; padding: 9px 13px; min-height: 20px; }
QPushButton:hover { background: #e8f2ef; border-color: #75a69c; }
QPushButton:pressed { background: #d3e9e2; }
QPushButton[primary="true"] { background: #157f75; color: white; border: 1px solid #157f75; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #116a61; }
QPushButton[danger="true"] { color: #a53e35; border-color: #e4c6c1; }
QPushButton:disabled { color: #92a2a1; background: #edf1ef; border-color: #dbe3e0; }
QLineEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox { background: white; border: 1px solid #c8d8d5; border-radius: 5px; padding: 7px; selection-background-color: #b5dfd6; selection-color: #14343d; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #157f75; }
QComboBox { min-height: 23px; padding-right: 22px; }
QComboBox::drop-down { border: none; width: 22px; }
QTableWidget, QListWidget { background: white; border: 1px solid #dbe6e3; border-radius: 6px; gridline-color: #edf2ef; alternate-background-color: #f5f8f6; }
QTableWidget::item { padding: 7px; }
QTableWidget::item:selected, QListWidget::item:selected { background: #d4eae3; color: #14343d; }
QHeaderView::section { background: #e8efec; padding: 10px 7px; border: none; border-bottom: 1px solid #d2dfd9; font-weight: 600; }
QTableCornerButton::section { background: #e8efec; border: none; border-bottom: 1px solid #d2dfd9; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: #f3f6f5; }
QGroupBox { border: 1px solid #d1dfd9; border-radius: 7px; margin-top: 12px; padding-top: 15px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QCheckBox, QRadioButton { spacing: 9px; padding: 5px; }
QCheckBox::indicator, QRadioButton::indicator { width: 18px; height: 18px; }
QRadioButton { background: white; border: 1px solid #dbe6e3; border-radius: 6px; padding: 11px; }
QRadioButton:checked { background: #e1f1ea; border-color: #157f75; }
QLabel#answerOption { background: white; color: #25464d; border: 1px solid #dbe6e3; border-radius: 6px; padding: 10px; }
QLabel#answerOption[answerState="correct"] { background: #e1f4e9; color: #185a37; border: 2px solid #3b8c60; font-weight: 600; }
QLabel#answerOption[answerState="wrong"] { background: #fae9e6; color: #8b302b; border: 2px solid #bd6259; font-weight: 600; }
QProgressBar { border: none; background: #dce8e2; border-radius: 5px; height: 12px; max-height: 15px; text-align: center; font-size: 10px; }
QProgressBar::chunk { background: #249488; border-radius: 5px; }
QStatusBar { background: #edf3ef; color: #637b80; }
QDialog { background: #f3f6f5; }
QToolTip { background: #14343d; color: white; border: none; padding: 5px; }
"""


class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.store = window, window.store
        layout = QVBoxLayout(self)
        layout.addWidget(label("Le tue impostazioni", "heading"))
        layout.addWidget(
            label(
                "I file del progetto e tutti i dati dell'app restano nella cartella del programma.",
                "muted",
            )
        )
        layout.addWidget(label(str(self.store.root)))
        layout.addLayout(
            row(
                button(
                    "Apri cartella del programma",
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root))),
                ),
                button(
                    "Apri cartella backup",
                    lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(self.store.root / "backups"))
                    ),
                ),
                None,
            )
        )
        form = QFormLayout()
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 20)
        self.font_size.setValue(self.store.get_setting("font_size", 14))
        form.addRow("Dimensione testo", self.font_size)
        form.addRow(button("Applica dimensione", self.apply_font))
        layout.addLayout(form)
        layout.addWidget(label("Archivio e sicurezza dei dati", "subheading"))
        layout.addLayout(
            row(
                button("Crea backup completo", self.backup, primary=True),
                button("Ripristina un backup", self.restore),
                None,
            )
        )
        layout.addWidget(
            label(
                "Il backup include domande, prove, note e fonti importate. Prima di un ripristino verrà salvata una copia dell'archivio attuale.",
                "muted",
            )
        )
        layout.addLayout(
            row(
                button("Azzera memoria di apprendimento", self.reset, danger=True),
                button("Ricostruisci indicatori", self.rebuild),
                None,
            )
        )
        layout.addWidget(
            label(
                "L'azzeramento riguarda tutti gli errori e i ripassi attivi. Le prove precedenti restano consultabili in Risultati. Per azzerare una sola raccolta usa Archivio → Gestisci raccolta.",
                "muted",
            )
        )
        layout.addWidget(label("Manuale e formati", "subheading"))
        layout.addLayout(
            row(
                button("Leggi la guida completa", window.show_guide),
                button(
                    "Apri esempi",
                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resource("examples")))),
                ),
                None,
            )
        )
        layout.addWidget(
            label(
                "Quiz Simulator 1.0 · Applicazione locale. Le spiegazioni ChatGPT richiedono copia/incolla nel browser; nessuna chiave API è necessaria.",
                "muted",
            )
        )
        layout.addStretch()

    def apply_font(self):
        self.store.set_setting("font_size", self.font_size.value())
        self.window.apply_style()

    def store_task(self, title, method):
        root = self.store.root

        def work(cancelled, progress):
            store = Store(root)
            try:
                return method(store, cancelled, progress)
            finally:
                store.close()

        return run_task(self, title, work)

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva backup",
            str(self.store.root / "backups" / (time.strftime("%Y%m%d-%H%M%S") + "-backup.zip")),
            "Backup ZIP (*.zip)",
        )
        if path:
            ok, result = self.store_task(
                "Creazione backup…",
                lambda store, cancel, progress: store.backup(
                    path, progress=progress, cancelled=cancel
                ),
            )
            if ok:
                self.window.statusBar().showMessage("Backup salvato: " + str(result), 10000)

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ripristina backup", str(self.store.root / "backups"), "Backup ZIP (*.zip)"
        )
        if path and confirm(
            self,
            "Ripristina archivio",
            "Sostituire l'archivio attuale con quello del backup? Verrà prima creata una copia di sicurezza dei dati attuali.",
        ):
            ok, safety = self.store_task(
                "Verifica e ripristino backup…",
                lambda store, cancel, progress: store.restore_backup(path, progress, cancel),
            )
            if ok:
                self.window.statusBar().showMessage(
                    "Ripristino completato. Copia preventiva: " + str(safety), 15000
                )
                self.window.apply_style()
                self.window.show_page("home")

    def reset(self):
        if confirm(
            self,
            "Azzera apprendimento",
            "Azzerare errori e ripassi per tutte le raccolte? Lo storico delle prove resterà disponibile e verrà creato un backup.",
        ):
            ok, _ = self.store_task(
                "Azzeramento dei progressi…", lambda store, cancel, progress: store.reset_learning()
            )
            if ok:
                self.window.statusBar().showMessage(
                    "La memoria di apprendimento riparte da zero.", 5000
                )

    def rebuild(self):
        ok, _ = self.store_task(
            "Ricostruzione degli indicatori…",
            lambda store, cancel, progress: store.rebuild_learning(),
        )
        if ok:
            self.window.statusBar().showMessage(
                "Indicatori ricostruiti rispettando gli azzeramenti.", 5000
            )


class MainWindow(QMainWindow):
    def __init__(self, root=None):
        super().__init__()
        self.store = Store(root or app_root())
        self.busy = False
        self.current = None
        self.page = "home"
        self.setWindowTitle("Quiz Simulator")
        self.resize(1320, 880)
        self.setMinimumSize(1000, 680)
        workspace = QWidget()
        workspace.setObjectName("workspace")
        main = QHBoxLayout(workspace)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(245)
        self.sidebar = sidebar
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(19, 29, 19, 20)
        side.addWidget(label("QUIZ\nSIMULATOR", "brand"))
        side.addWidget(label("Il tuo spazio per imparare"))
        side.addSpacing(30)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setWordWrap(True)
        self.nav.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_entries = [
            ("home", "Panoramica"),
            ("library", "Archivio domande"),
            ("new", "Nuovo quiz"),
            ("learning", "Ripasso intelligente"),
            ("results", "Risultati"),
            ("settings", "Impostazioni"),
            ("guide", "Guida all'uso"),
        ]
        for key, title in self.nav_entries:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self.navigate)
        side.addWidget(self.nav)
        side.addWidget(label("LOCALE · PERSONALE\nDati sotto il tuo controllo"))
        main.addWidget(sidebar)
        center = QWidget()
        self.center = QVBoxLayout(center)
        self.center.setContentsMargins(28, 25, 28, 20)
        main.addWidget(center, 1)
        self.setCentralWidget(workspace)
        self.statusBar().showMessage("Dati locali: " + str(self.store.data))
        self.apply_style()
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.show_page("home")

    def apply_style(self):
        size = self.store.get_setting("font_size", 14)
        controls = min(size, 16)
        nav_padding = 8 if size > 16 else 14
        stylesheet = STYLE.replace("font-size: 14px", f"font-size: {size}px")
        stylesheet += (
            f"\nQPushButton, QListWidget#nav, QHeaderView::section {{ font-size: {controls}px; }}"
            f"\nQListWidget#nav::item {{ padding: {nav_padding}px 14px; }}"
        )
        QApplication.instance().setStyleSheet(stylesheet)
        self.sidebar.setFixedWidth(245 if size <= 16 else 265)

    def exam_active(self):
        sid = self.store.active_session()
        if sid:
            s = self.store.db.execute("SELECT mode FROM sessions WHERE id=?", (sid,)).fetchone()
            return s[0] == "esame"
        return False

    def update_nav(self):
        locked = self.exam_active()
        for i, (key, _) in enumerate(self.nav_entries):
            item = self.nav.item(i)
            flags = Qt.ItemFlag.ItemIsSelectable
            if not locked or key == "home":
                flags |= Qt.ItemFlag.ItemIsEnabled
            item.setFlags(flags)
            item.setToolTip("Consegna prima la prova d'esame." if locked and key != "home" else "")

    def navigate(self, index):
        if index >= 0:
            self.show_page(self.nav_entries[index][0])

    def select_nav(self, page=None):
        index = next((i for i, (key, _) in enumerate(self.nav_entries) if key == page), -1)
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(index)
        if index < 0:
            self.nav.clearSelection()
            self.nav.setCurrentIndex(QModelIndex())
        self.nav.blockSignals(False)

    def set_content(self, widget, scroll=False):
        if self.current and hasattr(self.current, "persist"):
            self.current.persist()
        while self.center.count():
            child = self.center.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.current = widget
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setWidget(widget)
            self.center.addWidget(area)
        else:
            self.center.addWidget(widget)

    def show_page(self, page):
        if self.busy:
            return
        if self.exam_active() and page != "home":
            sid = self.store.active_session()
            self.open_session(sid)
            return
        if self.current and hasattr(self.current, "persist"):
            self.current.persist()
        self.page = page
        self.select_nav(page)
        if page == "guide":
            application = QApplication.instance()
            palette = application.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#146f68"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#146f68"))
            application.setPalette(palette)
            view = QTextBrowser()
            view.setOpenExternalLinks(True)
            view.setPalette(palette)
            view.document().setDefaultStyleSheet(
                "a { color: #146f68; text-decoration: underline; } "
                "code, pre { color: #203940; background-color: #eef4f1; }"
            )
            guide = resource("GUIDA_UTENTE.md")
            view.setMarkdown(
                guide.read_text(encoding="utf-8")
                if guide.exists()
                else "# Guida\nIl manuale sarà disponibile nella cartella del programma."
            )
            self.set_content(view)
        else:
            factories = {
                "home": HomePage,
                "library": LibraryPage,
                "new": NewQuizPage,
                "learning": LearningPage,
                "results": ResultsPage,
                "settings": SettingsPage,
            }
            self.set_content(factories[page](self), scroll=page in ("home", "new", "settings"))
        self.update_nav()

    def new_quiz(self, mode="allenamento"):
        if self.exam_active():
            self.open_session(self.store.active_session())
            return
        self.page = "new"
        self.select_nav("new")
        self.set_content(NewQuizPage(self, mode), scroll=True)
        self.update_nav()

    def open_session(self, sid):
        if not sid:
            return
        try:
            active = self.store.active_session()
            if self.exam_active() and sid != active:
                error(self, "Consegna prima la prova d'esame in corso.")
                return
            self.page = "quiz"
            self.select_nav()
            self.set_content(QuizPage(self, sid))
            self.update_nav()
        except Exception as exc:
            error(self, exc)

    def import_file(self):
        self.show_page("library")
        if isinstance(self.current, LibraryPage):
            self.current.import_file()

    def import_examples(self):
        self.show_page("library")
        if isinstance(self.current, LibraryPage):
            self.current.import_file(resource("examples/raccolta_demo.json"))

    def show_guide(self):
        self.show_page("guide")

    def tick(self):
        if self.busy:
            return
        sid = self.store.active_session()
        if sid:
            expired = self.store.check_deadline(sid)
            if expired:
                self.statusBar().showMessage(
                    "Tempo scaduto: la prova è stata consegnata automaticamente.", 15000
                )
                if isinstance(self.current, QuizPage) and self.current.sid == sid:
                    self.current.refresh()
                elif self.page == "home":
                    self.show_page("home")
                self.update_nav()
        if isinstance(self.current, QuizPage):
            self.current.tick()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            return
        if self.current and hasattr(self.current, "persist"):
            self.current.persist()
        self.timer.stop()
        self.store.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QuizSimulator")
    app.setOrganizationName("QuizSimulator")
    app.setStyle("Fusion")
    root = app_root()
    if "--smoke-test" in sys.argv:
        root = root / "tmp" / "smoke-test"
    (root / "data").mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "data" / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(
            None, "Quiz Simulator", "Il simulatore è già aperto da questa cartella."
        )
        return 1
    logging.basicConfig(filename=root / "data" / "app.log", level=logging.WARNING, encoding="utf-8")

    def report_exception(kind, value, tb):
        logging.error("Errore non gestito", exc_info=(kind, value, tb))
        QMessageBox.warning(
            None, "Operazione non completata", f"{value}\n\nI dettagli sono in data/app.log."
        )

    sys.excepthook = report_exception
    try:
        window = MainWindow(root)
        if "--smoke-test" in sys.argv:
            window.show()

            def finish_smoke():
                (root / "smoke-result.json").write_text(
                    json.dumps(
                        {
                            "ok": True,
                            "sqlite": window.store.db.execute("SELECT sqlite_version()").fetchone()[
                                0
                            ],
                            "guide": resource("GUIDA_UTENTE.md").exists(),
                            "examples": resource("examples/raccolta_demo.json").exists(),
                        }
                    ),
                    encoding="utf-8",
                )
                window.close()
                app.quit()

            QTimer.singleShot(800, finish_smoke)
        else:
            window.show()
        return app.exec()
    finally:
        lock.unlock()
