import sys
import tempfile
import time
from pathlib import Path

# In CI va impostato esplicitamente QT_QPA_PLATFORM=offscreen. In locale il backend
# Windows restituisce un'immagine fedele dei caratteri e dei controlli nativi.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from quiz_simulator.app import MainWindow
from quiz_simulator.dialogs import ImportDialog
from quiz_simulator.importing import read_json, read_pdf

app = QApplication([])
app.setStyle("Fusion")
out = ROOT / "tmp" / "screenshots"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="ui-qa-") as directory:
    window = MainWindow(Path(directory))
    window.resize(1360, 920)
    window.store.import_bank(read_json(ROOT / "examples" / "raccolta_demo.json"))
    window.show()

    def settle():
        for _ in range(3):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
            time.sleep(0.08)

    def capture(name):
        settle()
        window.grab().save(str(out / (name + ".png")))

    for page in ("home", "library", "new", "settings", "guide"):
        window.show_page(page)
        capture(page)
    sid = window.store.create_session("allenamento", 1, {"kinds": ["scelta_multipla"]})
    window.open_session(sid)
    capture("quiz")
    item = window.store.session(sid)["items"][0]
    wrong = next(
        option["id"]
        for option in item["question"]["risposte"]
        if option["id"] not in item["question"]["corrette"]
    )
    window.store.save_answer(sid, 0, [wrong], True)
    window.store.submit(sid)
    window.current.refresh()
    capture("feedback")
    window.show_page("results")
    capture("results")
    window.show_page("learning")
    capture("learning")
    bank, warnings, pages = read_pdf(ROOT / "examples" / "quiz_demo.pdf")
    dialog = ImportDialog(
        window, window.store, bank, ROOT / "examples" / "quiz_demo.pdf", warnings, pages
    )
    dialog.show()
    settle()
    dialog.grab().save(str(out / "import.png"))
    dialog.close()
    window.store.set_setting("font_size", 20)
    window.apply_style()
    window.resize(1000, 680)
    window.show_page("library")
    capture("font20-library")
    window.close()
    app.processEvents()
print(out)
