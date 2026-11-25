# BOM: ketersediaan di Tokopedia

Setiap part aktif dan part khusus sudah dicek ketersediaannya di Tokopedia (November 2026, lewat pencarian web; harga dan stok bisa berubah). Resistor dan kapasitor 0603/0805/1206 standar dijual di banyak toko komponen dan tidak dicantumkan satu per satu. Daftar lengkap per referensi ada di [`bom.csv`](bom.csv).

> **Keaslian:** IC TI (TPS65988, BQ25713) dari toko servis laptop bisa saja barang copotan atau remark. Minta foto marking chip, pilih toko dengan rating dan ulasan bagus, dan beli 1–2 cadangan.

## IC

| Ref | Part | Fungsi | Contoh listing |
|---|---|---|---|
| U101 | **TPS65988DH** (QFN-56) | USB-C PD dua arah | [TeknisiPro](https://www.tokopedia.com/teknisipro/ic-tps65988dh-tps-65988dh-tps65988-tps-65988), [Tekno Sparepart](https://www.tokopedia.com/teknospare/tps65988dh-tps65988-tps65988dhrshr-ti-new-original), [TPS65988CE](https://www.tokopedia.com/bengkelnotebook-asia/ic-tps65988ce-65988ce) |
| U102 | **W25Q16** (SOIC-8) | Flash konfigurasi PD | [parts-shop](https://www.tokopedia.com/parts-shop/w25q16-w25q16bvsig-2-mbyte-16-mbit-serial-flash-memory-25q16-sop-8), [CAXRA](https://www.tokopedia.com/caxrashop/eeprom-25q16-winbond-w25q16-w25q16) |
| U201 | **BQ25713RSNR** (WQFN-32) | Charger buck-boost 2–4S | [pencarian BQ25700A/BQ25713](https://www.tokopedia.com/find/bq25700a) |
| U301–U304 | **HY2213-BB3A** (SOT-23-6) | Balancer per cell | [10 pcs](https://www.tokopedia.com/tokosepatuyudia/10-pcs-new-original-hy2213-bb3a-screen-printing-bb3a-sot23-6-lithium-battery-protection-chipin-stock-1731081051346142343) |
| U401 | **XL4005E1** (TO-263-5) | Buck output 1–16V | [Fajar Kudus](https://www.tokopedia.com/fajarkudus/ic-xl4005-xl4005e1-5-32v-to-08-30v-5a-dc-buck-converter-step-down), [pencarian](https://www.tokopedia.com/find/xl4005) |
| U501 | **STM32G031K8T6** (LQFP-32) | Mikrokontroler | [pencarian STM32](https://www.tokopedia.com/find/stm32-microcontroller) |
| U502 | **HT7533-1** (SOT-89) | LDO 3.3V | [StarElektro](https://www.tokopedia.com/starelektro-1/7533-1-sot-89-sot-smd-umw-ht7533-1-ic-regulator-ldo-3-3v-3-3v-holtek-7533?extParam=src%3Dshop&whid=11077640), [20 pcs](https://www.tokopedia.com/borokoelektronik/20picis-ht7533-1-7533-1-sot89-sot89-ht7533) |

## MOSFET dan dioda

| Ref | Part | Contoh listing |
|---|---|---|
| Q201–Q204 | **AON7410** (DFN 3x3, N 30V 24A) | [StarElektro](https://www.tokopedia.com/starelektro-1/7410-7a10-ao-aon7410-ao7410-mosfet-n-ch-qfn-8-24a-30v-ic-smd-n7410), [Home Business](https://www.tokopedia.com/homebusiness/mosfet-aon7410-aon-7410-ao7410-ao-7410-n-ch-n-channel-n-channel) |
| Q205, Q301, Q302 | **AO4407A** (SO-8, P -30V 12A) | [Pi Toserba](https://www.tokopedia.com/pitoserba/mosfet-p-channel-4407a-4407-ao4407-ao4407a-smd-8-pin), [LED-Pekanbaru](https://www.tokopedia.com/ledpekanbaru/mosfet-ao4407a-ao4407-sop8-4407-30v-p-channel-ic) |
| Q303, Q304, Q311–Q314, Q401 | **AO3400** (SOT-23, A09T) | [WKH Elektronik](https://www.tokopedia.com/wkh-elektronik/original-ao3400-ao3400a-ao-3400-a-sot-23-n-channel-30v-5-8a-mosfet), [pencarian](https://www.tokopedia.com/find/ao3400) |
| D101, D402 | **SMBJ24A** (SMB) | [StarElektro](https://www.tokopedia.com/starelektro-1/lz-smbj24a-smb-do-214aa-j24a-diode-surge-esd-protection-smbj-24a-600w-24v-tvs-littlefuse-circuit-zener-dioda-5-pcs-b0d90) |
| D401 | **SS54** (SMB, 5A 40V) | [WKH Elektronik](https://www.tokopedia.com/wkh-elektronik/dioda-ss54-smb-5a-1n5824-smd-do-214aa-schottky-barrier-rectifier-sr540) |
| D503 | **BAT54C** (SOT-23, KL3) | [indo-ware](https://www.tokopedia.com/indo-ware/bat54c-dioda-200ma-30v-smd-schottky-barrier-diode-bat54-kl3-sot-23) |
| D301, D302 | **Zener 12V SOD-123** | [pencarian zener 12V](https://www.tokopedia.com/find/zener-12v) |

## Pasif khusus

| Ref | Part | Contoh listing / catatan |
|---|---|---|
| R201, R205 | Shunt **10 mΩ 1% 2512** | [WKH Elektronik](https://www.tokopedia.com/wkh-elektronik/smd-2512-alloy-resistor-r010-0-010-ohm-10mr-accuracy-1-rshunt-10milir), [mega arduino](https://www.tokopedia.com/megaarduino/2512-smd-alloy-resistor-r010-0-010-ohm-10mr-accuracy-1-rshunt-10milir) |
| R321–R324 | **39 Ω 1W** (THT) | Resistor 1W 39R biasa (contoh: Electronic Thingies) |
| L201 | **2.2 µH 12x12** (DS1207/CD127 "2R2") | [Meiryo Electronic](https://www.tokopedia.com/mayri/ds-1207-induktor-smd-2r2-uh-2-2-uh-smd-induktor-smd-lilit). **Cek Isat**, lalu batasi arus induktor di firmware |
| L401 | **33 µH 12x12x7** (CD127 "330") | [Aisyah Arduino](https://www.tokopedia.com/aisyahrobot/induktor-33uh-330-smd-12x12x7-patch-shielding-power-inductor-33-uh), [liagemilang](https://www.tokopedia.com/liage/induktor-33uh-smd-12x12x7mm-power-inductor-lilit-33-uh-kode-330). Sekitar 3A, jadi output dibatasi 3A |
| F301 | **Sekring blade mini 15A** (disolder langsung) | [Ono Shop](https://www.tokopedia.com/onoshop/fuse-blade-mini-15-ampere) |

## Konektor dan saklar

| Ref | Part | Contoh listing |
|---|---|---|
| J101 | USB Type-C female **16P SMD** | [Jogjarobotika](https://www.tokopedia.com/jogjarobotika/konektor-connector-soket-socket-tipe-type-c-female-usb-3-1-16p-smd), [Rumah Komponen Malang](https://www.tokopedia.com/rumahkomponenmlg/soket-usb-type-c-16p-female-smd-16pin-betina-socket-connector-16-kaki) |
| SW201 | DIP switch **3P** 2.54mm | [DEEL Electronic](https://www.tokopedia.com/deel-electronic/dip-switch-3p-saklar-slide-dip-ds-3-channel-2-54mm-pitch-breadboard) |
| SW301 | DIP switch **2P** 2.54mm | [DI Electronics](https://www.tokopedia.com/dielectronics/2p-2-position-dip-switch-254mm-pitch-2-row-4-pin-dip-switch-30638) |
| SW501 | DIP switch **4P** 2.54mm | [Unique Electronics](https://www.tokopedia.com/uniquelectronics/dip-switch-slide-type-pitch2-54mm-2p-3p-4p-5p-6p-7p-8p-10p-12p-4-position) |
| SW502 | Tactile switch 6x6 THT | Umum |
| J302 | JST-XH 5 pin | Umum |
| J303 | JST-PH 2 pin + NTC 10k | Umum |
| J301, J401 | Terminal block 2P 5.08mm (atau XT30) | Umum |
| J501 | Pin header 1x5 | Umum |

## Belum dicek satu per satu

Hanya part generik: resistor dan kapasitor standar, LED 0603, elco 220 µF/50V dan 330 µF/25V, terminal block, header, JST, dan tactile switch.
