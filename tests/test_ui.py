import copy
import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from quiz_simulator.app import MainWindow
from quiz_simulator.dialogs import ImportDialog, QuestionDialog
from quiz_simulator.domain import validate_bank
from quiz_simulator.importing import read_pdf
from quiz_simulator.library import LibraryPage
from quiz_simulator.quiz_pages import QuizPage
from quiz_simulator.report_pages import HomePage, ResultsPage


@pytest.fixture
def window(qtbot, tmp_path, bank):
    w = MainWindow(tmp_path)
    w.store.import_bank(bank)
    qtbot.addWidget(w)
    w.show()
    yield w
    w.close()


def test_choice_quiz_click_and_review(window, qtbot, monkeypatch):
    monkeypatch.setattr("quiz_simulator.quiz_pages.confirm", lambda *a: True)
    monkeypatch.setattr(
        "quiz_simulator.quiz_pages.error",
        lambda parent, message: (_ for _ in ()).throw(AssertionError(str(message))),
    )
    sid = window.store.create_session("allenamento", 1, {"kinds": ["scelta_multipla"]})
    window.open_session(sid)
    page = window.current
    for key, control in page.choice_controls:
        if key in ("A", "C"):
            control.setChecked(True)
    page.confirm_answer()
    assert window.store.session(sid)["items"][0]["outcome"] == "corretta"
    page.submit()
    assert window.store.session(sid)["status"] == "submitted"
    assert "Punteggio: 1" in page.summary.text()


def test_free_text_pending_grade_and_no_duplicate(window, qtbot, monkeypatch):
    monkeypatch.setattr("quiz_simulator.quiz_pages.confirm", lambda *a: True)
    monkeypatch.setattr(
        "quiz_simulator.quiz_pages.error",
        lambda parent, message: (_ for _ in ()).throw(AssertionError(str(message))),
    )
    sid = window.store.create_session("allenamento", 1, {"kinds": ["aperta_libera"]})
    window.open_session(sid)
    page = window.current
    page.input.setPlainText("Tre parti di quattro parti uguali.")
    page.confirm_answer()
    assert window.store.session(sid)["items"][0]["outcome"] == "da_valutare"
    page.grade("parziale")
    page.submit()
    assert window.store.session_summary(sid)["points"] == 0.5
    assert window.store.db.execute("SELECT count(*) FROM items").fetchone()[0] == 1


def test_exam_no_solutions_until_submit_and_nav_locked(window, qtbot, monkeypatch):
    monkeypatch.setattr("quiz_simulator.quiz_pages.confirm", lambda *a: True)
    monkeypatch.setattr(
        "quiz_simulator.quiz_pages.error",
        lambda parent, message: (_ for _ in ()).throw(AssertionError(str(message))),
    )
    sid = window.store.create_session("esame", 1, {"kinds": ["scelta_singola"]})
    window.open_session(sid)
    page = window.current
    assert not page.confirm_button.isVisible()
    assert not any("Spiegami" in b.text() for b in page.findChildren(QPushButton))
    window.show_page("library")
    assert isinstance(window.current, QuizPage)
    page = window.current
    page.choice_controls[1][1].setChecked(True)
    page.submit()
    assert any("Spiegami" in b.text() for b in page.findChildren(QPushButton))


def test_question_editor_preserves_correctness(window, qtbot, bank):
    dialog = QuestionDialog(window, bank["domande"][1], existing=True)
    qtbot.addWidget(dialog)
    dialog.text.setPlainText("Nuovo testo della domanda")
    dialog.save()
    assert dialog.result_question["corrette"] == ["A", "C"]
    dialog.kind.setCurrentIndex(dialog.kind.findData("aperta_breve"))
    dialog.accepted.setPlainText("Una\nDue")
    dialog.save()
    assert dialog.result_question["tipo"] == "aperta_breve"
    assert "risposte" not in dialog.result_question


def test_pdf_examples_roundtrip(window, qtbot):
    root = Path(__file__).resolve().parents[1]
    for name, expected in [("quiz_demo.pdf", 12), ("quiz_soluzioni_finali.pdf", 9)]:
        bank, warnings, pages = read_pdf(root / "examples" / name)
        assert len(bank["domande"]) == expected
        validate_bank(bank)
        dialog = ImportDialog(window, window.store, bank, root / "examples" / name, warnings, pages)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.table.selectRow(1)
        qtbot.wait(20)
        assert dialog.pdf.pageCount() > 0
        dialog.close()


def test_all_main_pages_render(window, qtbot):
    for key in ("home", "library", "new", "results", "settings", "guide", "learning"):
        window.show_page(key)
        qtbot.wait(15)
        assert window.current is not None


def test_import_review_preserves_exclusions_across_pages(window, qtbot, bank):
    template = bank["domande"][0]
    large = copy.deepcopy(bank)
    large["id"] = "large-review"
    large["domande"] = [
        {**copy.deepcopy(template), "id": f"question-{index}"} for index in range(205)
    ]
    dialog = ImportDialog(window, window.store, large)
    qtbot.addWidget(dialog)
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    dialog.change_page(1)
    assert 0 not in dialog.included
    assert dialog.table.rowCount() == 5
    dialog.change_page(-1)
    assert dialog.table.item(0, 0).checkState() == Qt.CheckState.Unchecked


def test_library_and_results_clear_stale_selection(window, qtbot, bank):
    template = bank["domande"][0]
    large = copy.deepcopy(bank)
    large["domande"] = [
        {**copy.deepcopy(template), "id": f"library-{index}"} for index in range(60)
    ]
    window.store.import_bank(large, "replace", "test")
    window.show_page("library")
    library = window.current
    assert isinstance(library, LibraryPage)
    library.table.selectRow(10)
    assert library.edit_button.isEnabled()
    library.turn_page(1)
    assert not library.selected()
    assert not library.edit_button.isEnabled()

    config = json.dumps(
        {
            "correct_points": 1,
            "wrong_points": 0,
            "omitted_points": 0,
            "shuffle_options": False,
            "minutes": 0,
        }
    )
    with window.store.transaction():
        window.store.db.executemany(
            """INSERT INTO sessions(id,mode,status,created_at,finished_at,config)
               VALUES(?,'allenamento','submitted',?,?,?)""",
            ((f"ui-history-{index}", index, index, config) for index in range(105)),
        )
    window.show_page("results")
    results = window.current
    assert isinstance(results, ResultsPage)
    results.table.selectRow(10)
    assert results.open_button.isEnabled()
    results.change_page(1)
    assert results.table.currentRow() == -1
    assert not results.open_button.isEnabled()


def test_expired_exam_rebuilds_home_and_navigation_state(window, qtbot):
    window.new_quiz()
    assert window.nav.item(window.nav.currentRow()).data(Qt.ItemDataRole.UserRole) == "new"
    sid = window.store.create_session("esame", 1, config={"minutes": 1})
    window.open_session(sid)
    assert window.nav.currentRow() == -1
    window.show_page("home")
    assert isinstance(window.current, HomePage)
    assert any(
        button.text() == "Riprendi la prova" for button in window.current.findChildren(QPushButton)
    )
    with window.store.db:
        window.store.db.execute("UPDATE sessions SET deadline=? WHERE id=?", (time.time() - 1, sid))
    window.tick()
    assert window.store.active_session() is None
    assert isinstance(window.current, HomePage)
    assert not any(
        button.text() == "Riprendi la prova" for button in window.current.findChildren(QPushButton)
    )


def test_wrong_choice_marks_user_answer_and_solution(window):
    sid = window.store.create_session("allenamento", 1, {"kinds": ["scelta_singola"]})
    window.open_session(sid)
    page = window.current
    controls = dict(page.choice_controls)
    controls["A"].setChecked(True)
    page.confirm_answer()
    controls = dict(page.choice_controls)
    assert controls["A"].property("answerState") == "wrong"
    assert controls["A"].text().startswith("✗ La tua scelta")
    assert controls["B"].property("answerState") == "correct"
    assert controls["B"].text().startswith("✓ Corretta")


def test_large_text_keeps_sidebar_labels_readable(window, qtbot):
    window.store.set_setting("font_size", 20)
    window.apply_style()
    window.resize(1000, 680)
    qtbot.wait(20)
    assert window.sidebar.width() == 265
    assert window.nav.wordWrap()
    assert window.nav.textElideMode() == Qt.TextElideMode.ElideNone
    assert window.nav.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
