# Power bank / BMS 2–4S + USB-C PD + Output 1–16V

Skematik KiCad (v0.2) untuk pack Li-ion/Li-Po **2–4 cell**:

- **USB-C PD dua arah**: charging (sink) dan output PD (source lewat OTG charger)
- **Output terminal 1–16V**, dipilih dengan DIP switch 4 bit + tombol APPLY
- **Proteksi baterai tanpa modul BMS**: sekring, FET proteksi, balancer per cell, dan monitor per cell lewat MCU
- **Semua part tersedia di Tokopedia**, lihat [`docs/bom_tokopedia.md`](docs/bom_tokopedia.md)

> Nama folder masih `bms-1-4s` dari versi pertama. Versi 1S akan dibuat terpisah.

> **Status: DRAFT.** Netlist sudah dicek otomatis (export netlist KiCad = netlist generator, 113 net cocok). Tapi beberapa nilai komponen dan konfigurasi **wajib diverifikasi** sebelum layout. Lihat [Daftar VERIFIKASI](#daftar-verifikasi).

## Isi folder

| Path | Isi |
|---|---|
| `kicad/bms.kicad_pro` | Proyek KiCad. Buka file ini (KiCad 7/8/9) |
| `kicad/*.kicad_sch` | Root (diagram blok) + 5 sheet |
| `kicad/bms.kicad_sym` | Library simbol proyek |
| `docs/bms_schematic.pdf` | PDF semua halaman |
| `docs/bom.csv`, `docs/bom_tokopedia.md` | BOM per referensi + link Tokopedia |
| `docs/netlist.md` | Semua net dan koneksinya |
| `tools/gen_schematic.py`, `tools/schlib.py` | Generator skematik (sumber netlist) |
| `tools/check_netlist.py` | Membandingkan netlist KiCad dengan netlist generator |

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

> Boleh juga langsung merapikan di KiCad. Tapi setelah itu jangan generate ulang, karena hasil edit akan tertimpa.

## Gaya skematik

- Komponen pendukung diletakkan **di dekat pin IC-nya** dan disambung dengan **wire**. Alur daya dari kiri ke kanan, GND ke bawah.
- Rail daya memakai **simbol power**: `VBUS_SYS`, `VSYS`, `PACK+`, `BATT+`, `+3V3`, `GND`.
- Sinyal antar sheet memakai **hierarchical label + sheet pin**. Halaman root berisi diagram blok dengan wire antar sheet.
- Label lokal hanya dipakai untuk net yang jauh di dalam satu sheet (misalnya gate drive dan tap balance).
- Nomor referensi per sheet: 1xx USB/PD, 2xx charger, 3xx baterai, 4xx output, 5xx MCU.
- Setiap blok fungsi diberi kotak bertitel.

## Arsitektur

```
USB-C ─ TPS65988 ─(PP_HV1)─ VBUS_SYS ─┬─ BQ25713 (buck-boost) ─ VSYS ─ BATFET ─ PACK+ ─ Q302/Q301 ─ F301 ─ Cell 2-4S
        (PD DRP)                      │      ▲ OTG (baterai -> VBUS_SYS)                                  │
                                      └─ XL4005 (buck) ─ Terminal 1-16V                    HY2213 x4 + tap -> ADC
BATT+ / VSYS ─ BAT54C ─ HT7533 ─ +3V3 ─ STM32G031K8 (I2C: BQ25713, TPS65988)
```

| Sheet | Isi |
|---|---|
| 1. USB-C PD | J101 USB-C 16P, U101 TPS65988, U102 flash W25Q16 |
| 2. Charger | U201 BQ25713, Q201–Q204 + L201 (buck-boost), Q205 BATFET, SW201 DIP jumlah cell |
| 3. Baterai | F301 sekring, Q301/Q302 FET proteksi + driver, U301–U304 HY2213, divider tap, SW301, NTC |
| 4. Output | U401 XL4005, L401, D401, injeksi PWM ke FB, sense tegangan |
| 5. MCU | U501 STM32G031K8T6, U502 HT7533, SW501 DIP VOUT, SW502 APPLY, LED, SWD |

### Cara kerja daya

| Kondisi | VBUS_SYS diisi oleh | Keterangan |
|---|---|---|
| Adapter PD tercolok | Adapter, lewat TPS65988 (sink) | BQ25713 mengisi baterai, XL4005 jalan dari adapter |
| Dari baterai, terminal dipakai | BQ25713 mode **OTG** (= Vout + 2V, maks 20.8V) | XL4005 tetap punya input di atas Vout, termasuk pada 2S (6–8.4V) |
| Dari baterai, USB-C jadi source | BQ25713 OTG (= tegangan PD) | TPS65988 menyambungkan PP_HV1 ke port |
| USB-C source + terminal bersamaan | OTG = tegangan PD | Terminal maks sekitar V_PD − 2V (diatur firmware) |

### Bus I2C (STM32 PB6/PB7, 100 kHz)

| Perangkat | Alamat |
|---|---|
| BQ25713 | 0x6B |
| TPS65988 (I2C1) | sesuai ADCIN2 = index 000 (lihat datasheet tabel 8-6) |

## Proteksi baterai (tanpa modul BMS)

| Lapisan | Komponen | Bergantung firmware? |
|---|---|---|
| Short circuit | F301 sekring blade 15A | Tidak |
| Overcharge per cell + balancing | HY2213 per cell: bleed ~100mA saat cell > 4.20V | Tidak |
| Tegangan total pack, arus input, watchdog | BQ25713 (BATOVP, ILIM_HIZ, watchdog) | Tidak |
| Over-discharge, overvoltage per cell, suhu | STM32 baca CELL_B1..B4 + NTC, lalu mematikan Q301 (DSG) / Q302 (CHG) | **Ya** |
| Default saat MCU mati | Gate Q301/Q302 ditarik ke source, jadi baterai terputus | Tidak |

MCU tetap mendapat daya dari baterai lewat BAT54C walaupun FET proteksi OFF, jadi bisa menyala lagi dan memutuskan.

## DIP switch

### SW201 (charger) + SW301 (baterai): jumlah cell

Atur saat baterai **dilepas**. Kedua switch harus konsisten.

| Cell | SW201 pos1 | pos2 | pos3 | SW301 pos1 (B4↔B3) | pos2 (B3↔B2) |
|---|---|---|---|---|---|
| 2S | **ON** | off | off | **ON** | **ON** |
| 3S | off | **ON** | off | **ON** | off |
| 4S | off | off | **ON** | off | off |

- SW201 memilih divider `CELL_BATPRESZ` BQ25713 (40/55/75% VDDA). Ini juga menentukan **SYSOVP** (2S = 12V, 3–4S = 19.5V). Hanya satu yang boleh ON; kalau semua OFF, charging mati.
- SW301 menyambungkan tap balance yang tidak dipakai lewat 100Ω, supaya HY2213 dan divider untuk cell kosong tidak mengambang. Kalau salah set, arusnya hanya sekitar 42mA dan terdeteksi firmware.
- Saat boot, firmware mencocokkan `CELL_SENSE`, tegangan tiap tap, dan default `MaxChargeVoltage` BQ25713. Kalau tidak cocok: FAULT, LED merah, dan FET tetap OFF.

### SW501 (MCU): tegangan output + SW502 APPLY

| Kode | V | Kode | V | Kode | V | Kode | V |
|---|---|---|---|---|---|---|---|
| 0000 | OFF | 0100 | 3.3 | 1000 | 7.4 | 1100 | 12.0 |
| 0001 | 1.0 | 0101 | 3.7 | 1001 | 8.4 | 1101 | 13.8 |
| 0010 | 1.8 | 0110 | 5.0 | 1010 | 9.0 | 1110 | 15.0 |
| 0011 | 2.5 | 0111 | 6.0 | 1011 | 11.1 | 1111 | 16.0 |

Alur:
1. Kalau DIP berubah, output langsung dimatikan (BB_EN = 0).
2. Tunggu tombol APPLY ditekan.
3. Siapkan VBUS_SYS (OTG kalau dari baterai).
4. Atur PWM BB_ADJ.
5. Set BB_EN = 1.
6. Loop tertutup dengan `VOUT_SENSE`.

Rentang hardware: Vdac 3.3V memberi sekitar 0.97V, Vdac 0V memberi sekitar 16.6V. Q401 membalik PWM, jadi kalau pin LOW atau MCU mati, output ke minimum.

## Daftar VERIFIKASI

### Kritis
- [ ] **Konfigurasi TPS65988** (TPS65988 Configuration Tool TI): port 1 DRP, sink PDO sampai 20V/3A, source PDO 5/9/15/20V lewat PP_HV1. PP_HV1 diisi charger oleh MCU (bukan TPS65988), jadi pastikan konfigurasi "source dari supply eksternal di PP_HV" dan timing PS_RDY bisa dipenuhi MCU (interrupt `PD_IRQ_N`, lalu set tegangan OTG). Uji di prototipe.
- [ ] **TPS65988 port 2 tidak dipakai**: VBUS2/PP_HV2/PP2_CABLE ke GND, C2_CC1/2 NC. **PP1_CABLE ke GND** artinya VCONN tidak didukung (kabel 3A). Cek dengan panduan TI.
- [ ] Boot strap TPS65988: ADCIN1 = 20k/100k (DIV 0.83, BP_NoWait + Safe Config), SPI_POCI pull-up = flash ada.
- [ ] **Pinout HY2213-BB3A** (1/4/5 = NC, 2 = VDD, 3 = VSS, 6 = CB) diambil dari potongan datasheet di alldatasheet karena situs HYcontek tidak bisa diakses. Cocokkan dengan datasheet lengkap, termasuk nilai RC di VDD.
- [ ] **AON7410 di footprint PowerPAK 1212-8**: land pattern mirip DFN 3.3x3.3, tapi cek dimensi dengan datasheet AON7410.

### Nilai komponen
- [ ] Kompensasi BQ25713 (R219/C223/C224, R220/C225/C226): dari diagram aplikasi datasheet, bandingkan dengan EVM.
- [ ] **L201 2.2µH 12x12**: cek Isat. Batasi arus charge/OTG supaya arus induktor di bawah Isat.
- [ ] **L401 33µH CD127** sekitar 3A: output terminal dibatasi **3A** (48W @16V) di firmware.
- [ ] XL4005: CFF = 1nF (dari rumus datasheet untuk R402 30k). Uji stabilitas di 1V dan 16V.
- [ ] Bleeder 39Ω 1W: sekitar 0.45W per cell saat balancing. Beri jarak di PCB.

### Firmware
- [ ] Batas cell: UV 3.0V (DSG OFF), OV 4.25V (CHG OFF), suhu charge 0–45°C, discharge −10–60°C.
- [ ] ChargeVoltage = 4.2V × N, ChargeCurrent sesuai kapasitas, watchdog BQ25713 di-refresh.
- [ ] Gauge persentase dari ADC BQ25713 (VBAT, ICHG, IDCHG): coulomb counting sederhana + koreksi OCV saat idle.
- [ ] Divider tap 1M/200k: pakai sampling time ADC panjang (kapasitor reservoir 100nF sudah ada) dan kalibrasi per channel.
