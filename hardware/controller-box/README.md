# Controller Box Anti Air (3D Print)

Model parametrik CadQuery, solid B-rep **tanpa mesh**. File STEP bisa langsung dibuka di Bambu Studio, OrcaSlicer, PrusaSlicer, Fusion 360, atau FreeCAD.

![iso](renders/01_iso.png)

| Bawah (gland) | Belakang (mount) | Isi | Layout atas | Part cetak |
|---|---|---|---|---|
| ![](renders/02_bottom_glands.png) | ![](renders/03_back_mount.png) | ![](renders/04_open.png) | ![](renders/05_layout_top.png) | ![](renders/06_print_parts.png) |

## File

| File | Isi |
|---|---|
| `controller_box.py` | Sumber parametrik. Semua ukuran ada di bagian `Parameters` |
| `out/controller_box_assembly.step` | Assembly lengkap: box, komponen, dan jalur kabel |
| `out/print/base.step` | **Cetak:** badan box |
| `out/print/lid.step` | **Cetak:** tutup |
| `out/print/gasket_tpu.step` | **Cetak (TPU):** gasket |
| `out/print/opi_tray.step` | **Cetak:** tray Orange Pi |

## Ukuran

| | |
|---|---|
| Interior | 200 × 170 × 110 mm |
| Base (luas cetak) | 250 × 208 × 103 mm |
| Lid (luas cetak) | 244 × 214 × 21 mm |
| **Bed printer minimum** | **256 × 256 mm** (Bambu A1/P1/X1, Prusa XL, dll.) |

## Isi box

| Komponen | Ukuran | Posisi |
|---|---|---|
| PSU 12 V | 128 × 97.5 × 30 | Berdiri di sisi panjangnya, menempel dinding belakang. Dijepit 2 U-channel di lantai dan 2 pad penahan di bawah tutup (tambahkan foam 2 mm) |
| Orange Pi 5 Ultra | 89 × 57 | Di atas **tray dengan lubang slot**, jadi posisi lubang board bisa disetel (jarak lubang 58–82 × 49–50 mm). Posisi lubang board ini belum dipublikasikan, cek di board aslinya |
| TP-Link LS1005 | 83.6 × 45.7 × 22.8 | Cradle 4 sudut, diikat zip-tie |
| Buck converter 12 V → 5 V | sekitar 65 × 40 × 22 | Cradle 4 sudut. Untuk Orange Pi (USB-C 5 V) dan switch (5 V 0.6 A). **Pakai minimal 5 V 6 A** |
| 2× WAGO 221-415 | | Kantong di lantai, untuk distribusi 12 V (+) dan (−) |
| 2× kipas 60 × 60 × 37.5 | | **Intake** kiri bawah meniup ke Orange Pi. **Exhaust** kanan atas. Aliran udara menyilang diagonal melewati semua komponen |

## Anti air

1. **Tutup:** sambungan tongue-and-groove dengan **gasket TPU**, ditambah **skirt** tutup yang menutupi flange dari luar. Jadi ada dua lapis penghalang, dikencangkan 12 baut M4.
2. **Kipas:** udara keluar-masuk lewat **rain cowl** yang hanya terbuka **ke bawah**. Air hujan tidak bisa masuk langsung. Di dalam cowl ada slot untuk lembaran filter (stainless mesh atau busa filter, tebal 1.6 mm) supaya serangga dan debu tertahan.
3. **Kabel:** semua masuk dari **lantai** lewat cable gland. Air yang mengalir di kabel tidak akan menetes masuk.

Catatan jujur: karena ada kipas, box ini **tahan hujan dan cipratan (sekitar IPX4)**, bukan kedap total (IP67). Pasang dengan cowl menghadap ke bawah, seperti di model.

## Jalur kabel

Semua kabel masuk dari lantai depan. Gland dari kiri ke kanan:

| Gland | Ukuran | Fungsi |
|---|---|---|
| 1–4 | M16 | Kamera 1–4 (Ethernet + 12 V). Pakai insert 2 lubang |
| 5 | M16 | Uplink/cadangan |
| 6 | M20 | AC masuk ke PSU |

Rute di dalam box (warna kabel sesuai preview):

- **AC (hitam):** gland M20, naik melewati buck, lalu ke terminal AC PSU di sisi kanan.
- **12 V (merah):** dari PSU ke WAGO. Dari WAGO bercabang ke:
  - kipas exhaust (dekat)
  - kipas intake (melalui jalur di dinding depan, diikat ke 4 anchor zip-tie)
  - input buck converter
  - kamera, keluar lewat gland 1–4
- **5 V (oranye):** dari buck ke USB-C Orange Pi dan ke jack DC switch.
- **Ethernet (biru):** dari gland kamera, naik di dinding kiri **di atas** kipas intake, lalu turun ke port switch. Orange Pi tersambung ke switch dengan kabel pendek.

**Perhatian:** LS1005 hanya punya **5 port**. 4 kamera + Orange Pi = 5 port, jadi **tidak ada port tersisa untuk uplink**. Pilihannya: uplink lewat Wi-Fi Orange Pi, atau ganti ke switch 8 port (ubah `SWITCH` di parameter).

## Panduan cetak

| Part | Orientasi | Material | Setting |
|---|---|---|---|
| base | Lantai di bed, bukaan ke atas | **ASA** (tahan UV) atau PETG | 0.2 mm, 4 dinding, infill 25 % gyroid, 5 lapis atas/bawah |
| lid | **Permukaan atas di bed** | ASA/PETG | Sama dengan base |
| gasket_tpu | Datar | TPU 95A | 100 % infill, kecepatan rendah |
| opi_tray | Datar | PETG/ASA | 3 dinding |

- **Tidak perlu support.** Semua overhang (flange, atap cowl, anchor) sudah di-chamfer 45°. Lubang grill kipas dibuat berupa slot vertikal, jadi tidak ada lengkungan besar yang menggantung.
- **Heat-set insert:**
  - 12× M4 (lubang Ø5.6, kedalaman 8) di flange untuk tutup
  - 8× M3 (Ø4.2) untuk kipas
  - 4× M3 untuk tray
- **Baut:** M4 × 16 untuk tutup (kepala masuk counterbore), M3 × 45 untuk kipas (menembus badan kipas 37.5 mm), dan M2.5 untuk Orange Pi di tray.
- **Mount:** 2 rail di belakang punya slot untuk **klem selang/stainless band** (lebar sampai 14 mm, untuk tiang) dan lubang M6 untuk dinding.
- **Setelah cetak,** lapisi sambungan gland dengan O-ring bawaan gland. Kalau pakai PETG, cat dengan cat UV-resistant untuk pemakaian outdoor.

## Daya (perkiraan)

| Beban | Daya |
|---|---|
| Orange Pi 5 Ultra | 10–20 W |
| LS1005 | 2 W |
| 2 kipas 60 × 38 | 2–10 W (tergantung model) |
| 4 kamera DS-2DE2C400MWG-E (dari box ini) | 4 × 9 W = 36 W |
| **Total** | **sekitar 50–70 W, jadi PSU 12 V minimal 6–8 A** |
