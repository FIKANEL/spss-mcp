# SPSS MCP

Menyambungkan Claude ke IBM SPSS Statistics 27 di PC ini.

**Penting:** MCP ini tidak menempel ke jendela SPSS yang sedang terbuka.
Simpan datamu ke file `.sav`, lalu arahkan tool ke file itu.

## Tool yang tersedia
- `spss_info` - cek SPSS kedeteksi atau belum.
- `read_sav` - baca isi .sav (variabel, N, contoh baris, label).
- `describe_sav` - metadata lengkap (tipe, measure, value label, missing).
- `export_csv` - konversi .sav ke CSV.
- `run_syntax` - jalanin syntax SPSS lewat engine, hasilnya balik ke Claude.

## Instalasi
1. Install dependency (pakai Python mana pun yang kamu punya):
   ```
   pip install -r C:\path\to\spss-mcp\requirements.txt
   ```
2. Tambahkan ke config MCP client:
   ```json
   {
     "mcpServers": {
       "spss": {
         "command": "python",
         "args": ["C:\\path\\to\\spss-mcp\\server.py"]
       }
     }
   }
   ```
   Kalau `python` tidak dikenal, ganti dengan path lengkap python.exe-mu.

## Kalau run_syntax gagal (tidak ada output)
Flag batch beda-beda antar versi SPSS. Default:
```
"{exe}" "{syntax}" -production -out "{out}" -type text
```
Kalau hasilnya kosong, set environment variable `SPSS_BATCH_ARGS` dengan
template lain, lalu restart MCP. Placeholder: `{exe} {syntax} {out} {err}`.

Alternatif format yang umum:
```
"{exe}" -f "{syntax}" -out "{out}" -type text -error "{err}"
```

Override path exe (kalau auto-detect salah): set `SPSS_STATS_EXE` ke path
lengkap `stats.exe`.

## Lisensi
MIT. Lihat [LICENSE](LICENSE).

> Proyek independen, tidak berafiliasi dengan IBM. IBM SPSS Statistics adalah merek dagang IBM.
