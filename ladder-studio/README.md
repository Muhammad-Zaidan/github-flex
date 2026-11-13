# Rangkai: ladder PLC dari template, editor, dan simulasi

> Nama sementara. Proyek ini nanti dipindah ke repo sendiri.

Web app untuk membuat program ladder PLC: pilih template parametrik atau gambar sendiri, jalankan simulasinya langsung di browser, lalu export ke software PLC. Seluruhnya berjalan di browser (statis), tanpa server dan tanpa akun.

## Status MVP: tahap 1

| Fitur | Status |
|---|---|
| Model ladder generik (seri/paralel, satu logika → semua brand) | ✅ |
| Editor: palet ketuk/seret, sisip seri/paralel, pilih grup, undo/redo, rung naik/turun/duplikat | ✅ |
| Simulator scan-cycle: NO/NC, tepi P/N, coil, set/reset, TON/TOF/TP, CTU/CTD, compare, MOV/ADD/SUB/MUL/DIV/INC/DEC | ✅ |
| 13 template parametrik (motor, proses, umum) + penjelasan per rung + wiring PLC | ✅ |
| Tabel I/O, alamat otomatis per brand + override manual | ✅ |
| Export Omron CX-Programmer (mnemonic + simbol) | ✅ belum diverifikasi |
| Export GX Works2 / GX Works3 (IL + CSV + komentar device) | ✅ belum diverifikasi |
| Export Machine Expert Basic M221 (IL + konfigurasi) | ✅ belum diverifikasi |
| Export Machine Expert / CODESYS (PLCopen XML), IEC Structured Text | ✅ belum diverifikasi |
| Bahasa Indonesia / Inggris, desktop + HP, mode gelap | ✅ |
| Prompt AI (free tier + BYOK) | ⏳ tahap 2 |
| File project native (.smbp, .cxp, .gxw, .gx3) | ⏳ riset, tahap 3 |
| Instruksi lanjutan: analog scaling, shift register, PID | ⏳ |
| Visualisasi: animasi mesin, timing diagram, mode cerita | ⏳ setelah MVP di-acc |

"Belum diverifikasi" artinya format dibuat dari dokumentasi publik dan belum dites dengan membukanya di software vendor.

## Menjalankan

```bash
npm install
npm run dev      # http://localhost:5173
npm test         # unit test simulator, template, exporter
npm run build    # hasil statis di dist/ (bisa di-host di Cloudflare Pages / GitHub Pages)
```

## Struktur

```
src/core/          model ladder, alamat per brand, simulator
src/core/export/   exporter per software
src/templates/     template parametrik (DSL kecil di dsl.ts)
src/ui/            editor, simulasi, I/O, penjelasan, export
```

Program ini adalah draft dan wajib direview serta diuji oleh orang yang kompeten sebelum dijalankan di mesin sungguhan.
