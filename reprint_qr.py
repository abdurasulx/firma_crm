"""Bir martalik yordamchi dasturcha — 20 ta muayyan Serial QR kodini
XPrinter'ga qayta chop etish uchun. `desktop_agent`ga hech qanday
bog'liqligi yo'q (mustaqil, alohida skript) — ishlatib bo'lingach
o'chirib tashlash mumkin.

Ishga tushirish: shu faylni Desktop Agent'ning venv python'i bilan
ishga tushiring (pywin32 allaqachon o'rnatilgan):
    D:\\firma_crm\\desktop_agent\\venv\\Scripts\\python.exe reprint_qr.py
"""
import tkinter as tk
from tkinter import ttk, messagebox

import win32print

BASE_URL = "https://safiya.stockfirm.uz/p/"
DEFAULT_DPI = 203

KODLAR = [
    "66687192-7220-4a4c-950a-eaac9eb445b0",
    "30dc4283-77eb-4558-aaa7-69840bfa539b",
    "2d7e5054-b9dc-447e-b254-332087eb5eaf",
    "97d4a08f-9c1e-4a4c-b583-bb4b3cc0ae03",
    "b2420bd8-d8db-4a26-ba43-dabacc1d8ef4",
    "b3acedf2-5dfa-476a-9c27-fcdab0576a2c",
    "abc4f1be-260c-4ffb-97ce-210f9ea7528f",
    "eefeff19-0db1-4ddf-a32a-a1082b737d7c",
    "c2e12261-ba0c-4010-b631-390929d78e69",
    "ec2bf871-a621-471f-bfdd-a6599761582e",
    "89e5ccc9-4d40-466e-90b8-1534d81ca031",
    "b4a3d261-eaa8-4ad7-b887-67c016da462a",
    "3eb9a3b3-6dd2-4d69-af62-74b0c289664b",
    "8c804331-ae23-4b69-9907-5d06304f0f4b",
    "2e71535f-d69c-46db-a262-ff93a9656ba8",
    "2c3774bc-321b-426a-a7d9-e4161607b2f7",
    "11321847-4377-4117-9e1a-06b02fd1904f",
    "6d6658bc-abde-4073-b20c-562c15eb3744",
    "157c6ae5-6009-46ee-9750-543eab71c931",
    "c741aa0e-b13b-4a2c-8dc7-a935a2871308",
]


def _mm_to_dots(mm: float, dpi: int = DEFAULT_DPI) -> int:
    return round(mm * dpi / 25.4)


def build_tspl_label(qr_data: str, width_mm: float, height_mm: float, gap_mm: float, dpi: int = DEFAULT_DPI) -> bytes:
    """`desktop_agent/app/label_printer_service.py::build_tspl_label` bilan
    bir xil — mustaqil nusxa (agentga tegmaslik uchun)."""
    margin_dots = _mm_to_dots(2, dpi)
    qr_cell_size = 6
    lines = [
        f"SIZE {width_mm:g} mm,{height_mm:g} mm",
        f"GAP {gap_mm:g} mm,0",
        "DIRECTION 0",
        "DENSITY 8",
        "SPEED 4",
        "CLS",
        f'QRCODE {margin_dots},{margin_dots},L,{qr_cell_size},A,0,"{qr_data}"',
        "PRINT 1,1",
    ]
    body = "\r\n".join(lines) + "\r\n"
    return body.encode("gbk", errors="replace")


def print_raw(printer_name: str, data: bytes, doc_name: str = "Reprint QR"):
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, (doc_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("QR qayta chop etish (bir martalik)")
        self.geometry("480x420")

        ttk.Label(self, text=f"Chop etiladigan kodlar soni: {len(KODLAR)}", font=("Segoe UI", 11, "bold")).pack(pady=(14, 6))

        frm = ttk.Frame(self)
        frm.pack(pady=6, padx=14, fill="x")

        ttk.Label(frm, text="Printer:").grid(row=0, column=0, sticky="w", pady=4)
        printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
        self.printer_var = tk.StringVar(value=printers[0] if printers else "")
        ttk.Combobox(frm, textvariable=self.printer_var, values=printers, width=32, state="readonly").grid(row=0, column=1, pady=4)

        ttk.Label(frm, text="Kenglik (mm):").grid(row=1, column=0, sticky="w", pady=4)
        self.width_var = tk.DoubleVar(value=40)
        ttk.Entry(frm, textvariable=self.width_var, width=10).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Balandlik (mm):").grid(row=2, column=0, sticky="w", pady=4)
        self.height_var = tk.DoubleVar(value=30)
        ttk.Entry(frm, textvariable=self.height_var, width=10).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Oraliq (mm):").grid(row=3, column=0, sticky="w", pady=4)
        self.gap_var = tk.DoubleVar(value=2)
        ttk.Entry(frm, textvariable=self.gap_var, width=10).grid(row=3, column=1, sticky="w", pady=4)

        self.status = tk.Text(self, height=14, width=56)
        self.status.pack(pady=10, padx=14)

        ttk.Button(self, text="Barchasini chop etish", command=self._print_all).pack(pady=6)

        single_frm = ttk.Frame(self)
        single_frm.pack(pady=(2, 10), padx=14, fill="x")
        ttk.Label(single_frm, text="Bitta kodni qayta chop etish (kod yoki 1-20 raqami):").pack(anchor="w")
        row = ttk.Frame(single_frm)
        row.pack(fill="x", pady=4)
        self.single_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.single_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Shuni chop etish", command=self._print_single).pack(side="left", padx=(6, 0))

    def _log(self, text: str):
        self.status.insert("end", text + "\n")
        self.status.see("end")
        self.update_idletasks()

    def _print_all(self):
        printer = self.printer_var.get()
        if not printer:
            messagebox.showerror("Xato", "Printer topilmadi.")
            return
        width, height, gap = self.width_var.get(), self.height_var.get(), self.gap_var.get()
        ok, fail = 0, 0
        for i, kod in enumerate(KODLAR, start=1):
            url = BASE_URL + kod + "/"
            try:
                data = build_tspl_label(url, width, height, gap)
                print_raw(printer, data)
                ok += 1
                self._log(f"{i}/{len(KODLAR)} ✓ {kod}")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                self._log(f"{i}/{len(KODLAR)} ✗ {kod} — {exc}")
        messagebox.showinfo("Tugadi", f"Chop etildi: {ok}, xato: {fail}")

    def _print_single(self):
        printer = self.printer_var.get()
        if not printer:
            messagebox.showerror("Xato", "Printer topilmadi.")
            return
        raw = self.single_var.get().strip()
        if not raw:
            messagebox.showerror("Xato", "Kod yoki raqam kiriting.")
            return
        # Yoki ro'yxatdagi tartib raqami (1-20), yoki to'g'ridan-to'g'ri kod.
        if raw.isdigit() and 1 <= int(raw) <= len(KODLAR):
            kod = KODLAR[int(raw) - 1]
        else:
            kod = raw
        width, height, gap = self.width_var.get(), self.height_var.get(), self.gap_var.get()
        url = BASE_URL + kod + "/"
        try:
            data = build_tspl_label(url, width, height, gap)
            print_raw(printer, data)
            self._log(f"[YAKKA] ✓ {kod}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"[YAKKA] ✗ {kod} — {exc}")
            messagebox.showerror("Xato", str(exc))


if __name__ == "__main__":
    App().mainloop()
