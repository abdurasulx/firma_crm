import sys

import win32api
import win32event
import winerror
from PyQt6.QtWidgets import QApplication, QMessageBox

from app import db
from app.windows.main_window import MainWindow

# Bitta kompyuterda bir vaqtning o'zida dasturning ikkinchi nusxasi
# ochilib ketmasligi uchun — Windows nomlangan mutex orqali (jarayon
# qanday tugasa ham, hatto majburan o'chirilsa ham, OS uni darhol
# bo'shatadi — `QSharedMemory`dan farqli, u ba'zan avvalgi
# yiqilgan/majburan o'chirilgan jarayondan qolgan "orfan" holatga
# tushib, keyingi urinishlarni noto'g'ri "band" deb ko'rsatib
# qo'yishi mumkin edi, sinovda aynan shu aniqlandi).
_MUTEX_NAME = "Global\\StockFirmAgent-SingleInstance-Lock"


def _acquire_single_instance_lock():
    mutex = win32event.CreateMutex(None, False, _MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return mutex  # dastur davomida ushlab turiladi — GC bo'lib, handle yopilib ketmasligi uchun


def main():
    app = QApplication(sys.argv)

    lock = _acquire_single_instance_lock()
    if lock is None:
        QMessageBox.warning(
            None, "Allaqachon ishga tushirilgan",
            "StockFirm Desktop Agent allaqachon ishlab turibdi — bir vaqtning "
            "o'zida bitta nusxa ishlashi mumkin. Avval eskisini yoping.",
        )
        sys.exit(1)

    db.init_db()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
