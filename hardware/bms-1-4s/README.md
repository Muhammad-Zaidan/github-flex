# BMS 1-4S + USB-C PD + Output 1-16V

Skematik KiCad untuk power bank/BMS 1–4 cell Li-ion/Li-Po:

- **Charging lewat USB-C PD** (sink sampai 20V/3A, sekitar 60W)
- **Output USB-C PD** (source, lewat mode OTG BQ25713)
- **Output terminal 1–16V**, dipilih dengan DIP switch 4 bit lalu tombol APPLY
- **BMS**: proteksi, balancing, fuel gauge, dan NTC (BQ40Z50-R2)

> **Status: DRAFT v0.1.** Netlist sudah dicek otomatis (KiCad vs generator: cocok). Tapi beberapa nilai komponen dan topologi **wajib diverifikasi** sebelum layout PCB. Lihat [Daftar VERIFIKASI](#daftar-verifikasi).

## Isi folder

| Path | Isi |
|---|---|
| `kicad/bms.kicad_pro` | Proyek KiCad. Buka file ini (KiCad 7/8/9) |
| `kicad/*.kicad_sch` | Root + 5 sheet hierarkis |
| `kicad/bms.kicad_sym` | Library simbol proyek (sudah terdaftar di `sym-lib-table`) |
| `docs/bms_schematic.pdf` | PDF semua sheet |
| `docs/netlist.md` | Daftar semua net dan koneksinya |
| `docs/bom.csv` | BOM ringkas (dikelompokkan per value/footprint) |
| `tools/gen_schematic.py` | **Sumber netlist.** Ubah di sini, lalu generate ulang |
| `tools/check_netlist.py` | Membandingkan netlist hasil export KiCad dengan netlist generator |

Cara generate ulang dan memverifikasi:

```bash
python3 tools/gen_schematic.py
```

```bash
kicad-cli sch export netlist -o /tmp/bms.net kicad/bms.kicad_sch
```

```bash
python3 tools/check_netlist.py /tmp/bms.net
```

```bash
kicad-cli sch export pdf -o docs/bms_schematic.pdf kicad/bms.kicad_sch
```

> Kalau Anda mengedit langsung di KiCad (memindahkan komponen, merapikan wire), itu boleh. Tapi setelah itu jangan generate ulang, karena hasil edit akan tertimpa.

## Arsitektur

```
USB-C ── TPS25750D ──VBUS_SYS── BQ25713 ──VSYS──┬── TPS55289 ── Terminal 1-16V
 (PD DRP)   │  (switch 28V/7A)  (buck-boost)    ├── NCP718 ── +3V3 ── STM32G031
            │                       │           └── (BATFET Q5)
         EEPROM                     │                   │
        (config)                    │                PACK_P
                                    │                   │
                                    │        BQ40Z50 + FET proteksi Q6/Q7
                                    │                   │
                                    └──── I2C ────── Cell 1-4S
```

| Sheet | Isi |
|---|---|
| 1. USB-C & PD | J1 USB-C 16P, U1 TPS25750D, U2 EEPROM 24LC256 |
| 2. Charger | U3 BQ25713, Q1–Q4 + L1 (buck-boost), Q5 BATFET, SW1 DIP CELL CONFIG |
| 3. Baterai + BMS | U4 BQ40Z50-R2, Q6/Q7 FET proteksi, sense 1mΩ, konektor balance/NTC |
| 4. Output | U5 TPS55289 + L2, sense 10mΩ, J5 terminal output |
| 5. MCU | U6 STM32G031G8U6, U7 LDO NCP718, SW2 DIP VOUT, SW3 APPLY, LED, SWD/UART |

### Bus I2C

| Bus | Perangkat | Alamat 7-bit |
|---|---|---|
| I2C1 MCU (PB6/PB7, 100 kHz) | BQ25713 | 0x6B |
| | BQ40Z50-R2 (SMBus) | 0x0B |
| | TPS55289 (MODE=VCC) | 0x74 |
| | TPS25750 I2Cs (ADCIN index #1) | 0x20 |
| I2Cm TPS25750 (terpisah) | 24LC256 | 0x50 |

I2Cm TPS25750 **tidak mendukung multi-master**, jadi MCU tidak boleh ikut di bus itu.

### Pin MCU (STM32G031G8U6, UFQFPN-28)

| Pin | Port | Fungsi |
|---|---|---|
| 1 | PC14 | `BB_EN`: enable TPS55289 |
| 6 | PA0 | `VSYS_SENSE`: ADC, divider 100k/15k |
| 7 | PA1 | `CELL_SENSE`: ADC, readback DIP jumlah cell |
| 8/9 | PA2/PA3 | UART debug |
| 10 | PA4 | `VOUT_SENSE`: ADC, divider 100k/10k |
| 11 | PA5 | Tombol APPLY |
| 12/13 | PA6/PA7 | LED status (hijau) / fault (merah) |
| 14 | PB0 | `CHRG_OK` dari BQ25713 |
| 15 | PB1 | `PROCHOT_N` dari BQ25713 |
| 16 | PA8 | `OTG_EN`: pin OTG/VAP BQ25713 |
| 17 | PC6 | `BB_INT_N`: fault TPS55289 |
| 18 | PA9 | `PD_IRQ_N`: interrupt TPS25750 |
| 19 | PA10 | LED charging (biru) |
| 20/21 | PA13/PA14 | SWD |
| 23/24/25/22 | PB3/PB4/PB5/PA15 | DIP VOUT bit 0–3 (aktif-low, pull-up internal) |
| 26/27 | PB6/PB7 | I2C1 SCL/SDA |
| 2, 28 | PC15, PB8 | Cadangan |

## DIP switch

### SW1: CELL CONFIG (8 posisi, sheet Charger)

Atur saat baterai **dilepas**. Posisinya dibaca saat boot.

| Cell | pos1 | pos2 | pos3 | pos4 | pos5 | pos6 | pos7 |
|---|---|---|---|---|---|---|---|
| 1S | **ON** | off | off | off | **ON** | **ON** | **ON** |
| 2S | off | **ON** | off | off | **ON** | **ON** | off |
| 3S | off | off | **ON** | off | **ON** | off | off |
| 4S | off | off | off | **ON** | off | off | off |

- **pos1–4**: memilih resistor divider `CELL_BATPRESZ` BQ25713 (25/40/55/75% dari VDDA). **Hanya satu yang boleh ON.** Kalau semuanya OFF, baterai dianggap tidak ada dan charging mati.
- **pos5–7**: men-short pin VC BQ40Z50 yang tidak dipakai (wajib menurut datasheet). Short ini ada di sisi IC, di belakang resistor 100Ω. Kalau salah setting, arus yang lewat hanya sekitar 20mA dan terdeteksi sebagai cell 0V, jadi masuk FAULT.
- Saat boot, firmware **wajib mencocokkan tiga sumber**: ADC `CELL_SENSE`, nilai default register `MaxChargeVoltage` BQ25713 (cerminan cell yang terdeteksi), dan tegangan per cell dari BQ40Z50. Kalau ada yang tidak cocok, charging dan output tidak dinyalakan.

> **Penting:** `CELL_BATPRESZ` juga menentukan **SYSOVP** BQ25713 (1S = 5V, 2S = 12V, 3–4S = 19.5V). Jadi pin ini harus sesuai jumlah cell yang sebenarnya, tidak bisa dibiarkan default 1S lalu dikoreksi lewat firmware.

### SW2: VOUT SELECT (4 bit, sheet MCU) + SW3 APPLY

Usulan tabel preset di firmware (ON = 1, bit0 = posisi 1):

| Kode | V | Kode | V | Kode | V | Kode | V |
|---|---|---|---|---|---|---|---|
| 0000 | OFF | 0100 | 3.3 | 1000 | 7.4 | 1100 | 12.0 |
| 0001 | 1.0 | 0101 | 3.7 | 1001 | 8.4 | 1101 | 13.8 |
| 0010 | 1.8 | 0110 | 5.0 | 1010 | 9.0 | 1110 | 15.0 |
| 0011 | 2.5 | 0111 | 6.0 | 1011 | 11.1 | 1111 | 16.0 |

Alur firmware:
1. Kalau DIP berubah, output langsung dimatikan (bit OE TPS55289 = 0).
2. Tunggu debounce sekitar 500 ms.
3. Tunggu tombol APPLY ditekan.
4. Tulis tegangan baru ke register REF.
5. Set OE = 1.
6. Cek `VOUT_SENSE`.

## Hal yang berubah dari diskusi awal (hasil membaca datasheet)

1. **BQ25713 tidak punya driver ACFET/RBFET.** Proteksi dan pemutusan jalur input ditangani oleh switch 28V/7A di dalam TPS25750D (PPHV ↔ VBUS_IN).
2. **Tidak ada load switch MOSFET terpisah di output terminal.** Output harus bisa turun sampai 1V, sehingga load switch P-FET tidak akan menyala. Sebagai gantinya dipakai bit **OE** TPS55289 (default mati), dan menurut datasheet TPS55289 memblokir arus balik dari output ke input.
3. **Halaman produk TI TPS25750 merekomendasikan BQ25731** (bukan BQ25713) sebagai companion untuk sistem di atas 45W, yang dikontrol langsung oleh TPS25750. Pinout BQ25731 sama dengan BQ25713, kecuali pin 21 (BATDRV menjadi NC, karena BQ25731 tidak punya BATFET/NVDC). Di desain ini **MCU yang mengontrol BQ25713**, supaya logika jumlah cell, NTC, dan BQ40Z50 terpusat di satu tempat.
4. Charge current default BQ25713 = 0A. Jadi baterai tidak akan diisi tanpa MCU. Ini fitur keamanan.

## Daftar VERIFIKASI

Wajib dicek sebelum layout atau pemesanan PCB.

### Kritis
- [ ] **Source PD > 5V lewat PPHV + OTG BQ25713.** Di TPS25750 Application Customization Tool, pastikan mode DRP dengan charger di PPHV bisa dipakai **tanpa** TPS25750 mengontrol charger. MCU perlu menangani interrupt kontrak lalu mengatur tegangan OTG; timing PS_RDY harus diuji. Kalau tidak bisa, opsinya: (a) ganti U3 ke **BQ25731** yang dikontrol TPS25750 (footprint sama, Q5 diganti jumper), atau (b) source hanya 5V lewat PP5V.
- [ ] **R8 (PP5V ke GND).** Pastikan dari dokumentasi TI bahwa PP5V boleh di-ground-kan bila tidak dipakai.
- [ ] **TPS25750 ADCIN1/ADCIN2** (R1–R4): pastikan decoding "7" = tied ke LDO_3V3 dan "0" = tied ke GND dari Technical Reference Manual.
- [ ] **BQ40Z50 pin VCC dan PACK** (R49 2k, VCC ke node tengah FET): bandingkan dengan skematik BQ40Z50EVM.
- [ ] **Konfigurasi awal BQ40Z50 untuk 1S/2S**: datasheet menyebut PACK perlu diberi tegangan saat pertama kali. Firmware harus memberi charge kecil lewat BQ25713 dulu, lalu menulis `DA Configuration` (jumlah cell) lewat `ManufacturerBlockAccess`.

### Nilai komponen
- [ ] Kompensasi BQ25713 COMP1/COMP2 (R22/C45/C46, R23/C47/C48): diambil dari diagram aplikasi datasheet, bandingkan dengan BQ25713 EVM.
- [ ] Kompensasi TPS55289 (R64/C74/C75): **hitung** dengan persamaan 24–26 datasheet untuk L = 4.7µH, Cout sekitar 88µF, fsw 400kHz.
- [ ] MOSFET Q1–Q4 (30V), Q5 (−30V P-ch), Q6/Q7 (30V): pilih part final dan footprint-nya (footprint masih kosong).
- [ ] Induktor L1 (2.2µH, Isat > 10A) dan L2 (4.7µH, Isat > 12A): footprint masih kosong.
- [ ] Footprint IC TI (U1, U3, U4, U5) masih kosong. Buat atau impor (misalnya lewat easyeda2kicad atau Ultra Librarian), lalu cocokkan nomor pad termasuk thermal pad (pin 33 di U3/U4).
- [ ] Rating USB-C 16P (J1): HRO TYPE-C-31-M-12 cukup untuk 3A. Untuk 5A perlu konektor 24P dan e-marker.

### Batas daya (firmware)
- [ ] 1S: terminal sekitar 20W, PDO 5V/3A + 9V/2A.
- [ ] 2S: sekitar 40W.
- [ ] 3–4S: 60W, PDO sampai 20V/3A + PPS.
- [ ] Pada 1S, VSYS sekitar 3.5–4.2V, jadi LDO 3.3V bekerja dekat dropout. Set MinSystemVoltage minimal 3.5V.

## Firmware: urutan boot (ringkas)

1. Baca SW1 lewat `CELL_SENSE`, baca default `MaxChargeVoltage` BQ25713, dan baca tegangan per cell BQ40Z50. Kalau tidak cocok, masuk FAULT.
2. Kalau jumlah cell di BQ40Z50 berbeda: unseal, tulis data flash (`DA Configuration` dan ambang proteksi), reset, lalu seal kembali.
3. Loop sekitar 1 detik:
   - Ambil `ChargingVoltage()` dan `ChargingCurrent()` dari BQ40Z50.
   - Tulis ke BQ25713. Ini juga me-reset watchdog BQ25713.
   - Cek PROCHOT dan suhu.
4. Event TPS25750 (`PD_IRQ_N`): kalau kontrak sink, atur `InputCurrentLimit` BQ25713. Kalau kontrak source, set tegangan OTG dan `OTG_EN`.
5. SW2 dan APPLY: atur TPS55289 dengan batas daya sesuai jumlah cell.
