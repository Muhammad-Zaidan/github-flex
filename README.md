# Cetakan

**Satu contoh format, semua tulisan ikut formatnya.**

Cetakan mempelajari format dari **satu dokumen contoh utuh** (.docx), misalnya template dari kampus, panduan penulisan jurnal, atau skripsi/artikel orang lain yang formatnya sudah benar. Setelah itu, tulisan Anda dicetak ulang mengikuti format tersebut. Tulisannya bisa berupa teks mentah yang ditempel atau .docx yang formatnya berantakan.

Cetakan tidak memakai AI, gratis, dan bisa berjalan tanpa internet. Pengenalan struktur memakai pola teks, nama gaya, dan ciri format, sehingga hasilnya konsisten dan cepat: naskah sekitar 140 ribu kata selesai dalam sekitar satu detik.

---

## Menjalankan

### Windows
1. Pasang [Python 3.10+](https://www.python.org/downloads/). Saat memasang, centang **"Add python.exe to PATH"**.
2. Klik dua kali **`jalankan.bat`**. Pada pemakaian pertama, Cetakan menyiapkan dirinya selama sekitar satu menit. Setelah itu browser terbuka otomatis di `http://127.0.0.1:8000`.

### macOS / Linux
```bash
./jalankan.sh
```

### Docker (PDF dan font sudah termasuk)
```bash
docker build -t cetakan .
docker run -p 8000:8000 cetakan
```

> **Untuk ekspor PDF/ODT/RTF**, pasang [LibreOffice](https://www.libreoffice.org/download/) (gratis). Cetakan menemukannya secara otomatis. Format Word, HTML, Markdown, LaTeX, EPUB, dan teks bisa langsung dipakai tanpa LibreOffice.

---

## Cara pakai

1. **Unggah contoh format** (.docx). Panel kiri lalu menampilkan gaya yang berhasil dipelajari untuk setiap bagian: judul bab, subjudul, paragraf, daftar pustaka, dan lain-lain.
2. **Masukkan naskah.** Tempel teks mentah atau unggah .docx berantakan. Pratinjau halaman langsung muncul dengan format contoh.
3. **Periksa.** Jika ada bagian yang salah dikenali, klik paragrafnya di pratinjau lalu pilih peran yang benar. Kesalahan deteksi pada contoh juga bisa dikoreksi di bagian *Periksa deteksi pada contoh*.
4. **Unduh** sebagai Word, PDF, ODT, RTF, HTML, Markdown, LaTeX, EPUB, atau teks polos. Tombol *Lihat PDF asli* menampilkan hasil akhir sebelum diunduh.

### Yang dipelajari dari contoh

| Aspek | Contoh |
|---|---|
| Huruf, ukuran, tebal/miring, KAPITAL | Judul bab Times New Roman 14 pt tebal kapital |
| Perataan, menjorok, indentasi gantung | Paragraf rata kiri-kanan, menjorok 1,25 cm; daftar pustaka menggantung 1 cm |
| Spasi baris, jarak sebelum/sesudah | Spasi 1,5; 6 pt sebelum keterangan gambar |
| Baris kosong antarbagian | Satu baris kosong setelah nama bab |
| Halaman baru | Setiap bab dan *Daftar Pustaka* mulai di halaman baru |
| Bentuk judul bab | `BAB I` + `PENDAHULUAN` di dua baris, satu baris, atau penomoran otomatis Word |
| Penomoran subjudul | `1.1`, `1.1.1`, `A.`, `I.`, atau penomoran otomatis. Nomor dibuat dan disesuaikan otomatis |
| Kapitalisasi | `TINJAUAN PUSTAKA` menjadi `Tinjauan Pustaka` jika contoh memakai Huruf Awal Kapital |
| Label bergaya | **Gambar 1.1** tebal, keterangannya tidak; **Kata kunci:** tebal |
| Gaya judul khusus | *Abstrak*, *Daftar Pustaka*, dan sejenisnya memakai gaya persis seperti di contoh |
| Daftar berbutir/bernomor | Termasuk memulai ulang nomor di setiap daftar |
| Tabel | Garis, arsiran, gaya sel kepala dan isi |
| Catatan kaki | Ukuran, perataan, dan pemisah dari catatan kaki contoh |
| Kertas & margin, header/footer | A4 dengan margin 4-4-3-3, nomor halaman |

### Bagian naskah yang dikenali otomatis
Judul dokumen, penulis/identitas, judul bab, nama bab, subjudul tingkat 1–3, paragraf, abstrak, kata kunci, butir daftar, kutipan panjang, gambar, keterangan gambar/tabel, tabel, entri daftar pustaka, dan catatan kaki.

Dari .docx, unsur berikut ikut dibawa: **gambar, tabel, persamaan (Equation), catatan kaki, tebal/miring/garis bawah, superskrip/subskrip**. Format yang berantakan (font campur aduk, ukuran acak, baris kosong berlebih) dibuang dan diganti format contoh.

### Penanda opsional untuk teks mentah
Semuanya opsional. Tanpa penanda pun, struktur dikenali dari polanya, misalnya `BAB I`, `1.1 Judul`, `Gambar 1.`, dan `DAFTAR PUSTAKA`.

```
# Judul bab           ## Subjudul 1          ### Subjudul 2
**tebal**  *miring*   x^2^ (superskrip)      H~2~O (subskrip)
- butir daftar        1. butir bernomor      > kutipan panjang
Teks dengan catatan kaki[^1]
[^1]: Isi catatan kaki.
| tabel | pipa |      atau tempel tabel langsung dari Word/Excel
```

Centang **Gabungkan baris yang terputus** jika teks disalin dari PDF, karena PDF memutus kalimat di setiap akhir baris.

---

## Baris perintah

```bash
python -m cetakan.cli contoh.docx naskah.txt -o hasil.pdf
python -m cetakan.cli contoh.docx naskah-berantakan.docx -o hasil.docx
python -m cetakan.cli contoh.docx naskah.txt --periksa           # lihat hasil deteksi
python -m cetakan.cli contoh.docx naskah.txt --peran 5=kutipan   # koreksi peran blok ke-5
```

Ekstensi berkas keluaran menentukan formatnya.

---

## Cara kerja singkat

1. **Analisis contoh** (`cetakan/template.py`): setiap paragraf diberi peran menggunakan pola teks, nama gaya, dan ciri format. Untuk setiap peran, Cetakan memilih paragraf yang formatnya paling sering muncul sebagai *cetakan*. Format paragraf dan hurufnya disalin apa adanya dari XML Word, sehingga hasilnya identik dengan contoh. Jarak antarbagian, pemisah halaman, bentuk penomoran, dan kapitalisasi juga dipelajari.
2. **Baca naskah** (`cetakan/reader.py`): teks mentah atau .docx diubah menjadi blok berperan dengan pengenal yang sama (`cetakan/classify.py`). Tingkat judul disesuaikan dengan hierarki contoh. Misalnya, naskah tanpa BAB yang dicetak dengan contoh skripsi akan dinaikkan satu tingkat.
3. **Cetak** (`cetakan/render.py`): dokumen contoh dibuka dan isinya dikosongkan. Gaya, header/footer, ukuran kertas, dan margin tetap dipakai. Blok naskah lalu ditulis ulang dengan format cetakan masing-masing.
4. **Ekspor** (`cetakan/export.py`): PDF, ODT, dan RTF melalui LibreOffice; HTML, Markdown, LaTeX, EPUB, dan teks melalui Pandoc.

## Batasan yang perlu diketahui

- Contoh dan naskah harus berformat **.docx**. File .doc, .odt, atau PDF perlu disimpan ulang sebagai .docx terlebih dahulu.
- Halaman sampul, lembar pengesahan, dan daftar isi pada contoh tidak ikut disalin, karena yang dicetak adalah isi naskah. Daftar isi bisa dibuat ulang di Word melalui menu *References → Table of Contents*.
- Jika contoh memakai beberapa *section* dengan penomoran halaman berbeda (misalnya romawi untuk bagian awal), hasil memakai pengaturan section terakhir.
- Grafik Word (chart) dan objek tertanam selain gambar belum dapat disalin. Sitasi Zotero/Mendeley ikut sebagai teks biasa.
- Makin lengkap contohnya (memuat bab, subbab, daftar, gambar, tabel, dan daftar pustaka), makin presisi hasilnya. Bagian yang tidak ada di contoh memakai gaya terdekat.

## Pengembangan

```bash
pip install -r requirements.txt pytest httpx
python -m pytest
python -m cetakan --port 8000      # server web
```

Struktur: `cetakan/` (mesin + server FastAPI), `cetakan/static/` (antarmuka tanpa build step), `tests/` (contoh sintetis skripsi & jurnal, serta uji keabsahan urutan XML agar berkas pasti terbuka di Word).
