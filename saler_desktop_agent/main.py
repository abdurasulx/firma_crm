"""Saler Agent — kirish nuqtasi.

Ombor/ishlab chiqarish Desktop Agent'idan (`desktop_agent/`) MUSTAQIL,
faqat savdogar (shtrix-kod orqali tezkor sotuv) uchun."""
import sys

from PyQt6.QtWidgets import QApplication

from app.windows.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("StockFirm Saler Agent")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
