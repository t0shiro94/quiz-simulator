from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


def button(text, slot=None, primary=False, danger=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setProperty("primary", True)
    if danger:
        widget.setProperty("danger", True)
    if slot:
        widget.clicked.connect(slot)
    return widget


def label(text, style=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if style:
        widget.setObjectName(style)
    return widget


def row(*widgets):
    layout = QHBoxLayout()
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        else:
            layout.addWidget(widget)
    return layout


def card(title, value, detail=""):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.addWidget(label(title, "muted"))
    layout.addWidget(label(str(value), "metric"))
    if detail:
        layout.addWidget(label(detail, "muted"))
    return frame


def error(parent, message):
    QMessageBox.warning(parent, "Controlla questa operazione", str(message))


def confirm(parent, title, message):
    dialog = QMessageBox(QMessageBox.Icon.Question, title, message, parent=parent)
    yes = dialog.addButton("Conferma", QMessageBox.ButtonRole.AcceptRole)
    dialog.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(dialog.buttons()[-1])
    dialog.exec()
    return dialog.clickedButton() == yes


class TaskThread(QThread):
    progress = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            value = self.fn(self.isInterruptionRequested, self.progress.emit)
            self.succeeded.emit(value)
        except Exception as exc:
            self.failed.emit(str(exc))


class TaskDialog(QDialog):
    def __init__(self, parent, title, fn):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.value = None
        self.failure = None
        self.ok = False
        self.task = TaskThread(fn)
        layout = QVBoxLayout(self)
        self.status = label(title)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.cancel_button = button("Annulla", self.cancel_task)
        layout.addWidget(self.status)
        layout.addWidget(self.bar)
        layout.addWidget(self.cancel_button)
        self.task.progress.connect(self.update_progress)
        self.task.succeeded.connect(self.succeeded)
        self.task.failed.connect(self.failed)
        self.task.finished.connect(self.accept)

    def update_progress(self, value):
        self.bar.setRange(0, 100)
        self.bar.setValue(value)

    def succeeded(self, value):
        self.ok, self.value = True, value

    def failed(self, message):
        self.failure = message

    def cancel_task(self):
        self.task.requestInterruption()
        self.status.setText("Annullamento richiesto. Attendo la fine dell'operazione in corso…")
        self.cancel_button.setEnabled(False)

    def reject(self):
        if self.task.isRunning():
            self.cancel_task()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.task.isRunning():
            self.cancel_task()
            event.ignore()
        else:
            super().closeEvent(event)


def run_task(parent, title, fn):
    dialog = TaskDialog(parent, title, fn)
    owner = getattr(parent, "window", None)
    owner = owner() if callable(owner) else owner
    if owner is None or not hasattr(owner, "busy"):
        owner = parent.topLevelWidget()
    if hasattr(owner, "busy"):
        owner.busy = True
    dialog.task.start()
    dialog.exec()
    dialog.task.wait()
    if hasattr(owner, "busy"):
        owner.busy = False
    if dialog.failure:
        error(parent, dialog.failure)
    return dialog.ok, dialog.value
