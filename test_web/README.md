# METU Curriculum Graph Validator

Bu klasor ana projeden ayrilmis, sadece data dogrulama icin kullanilan statik bir web arayuzudur.

## Veri uretme

```powershell
python .\test_web\build_graph_data.py
```

Bu komut `data/processed/curricula` ve `data/processed/prerequisites` altindaki temizlenmis veriyi okuyup `test_web/graph-data.json` dosyasini uretir.

## Calistirma

```powershell
python -m http.server 8765 --directory test_web
```

Tarayicida `http://127.0.0.1:8765/` adresini ac.

## Kapsam

- Her bolum icin dersler semester kolonlarina yerlestirilir.
- Prerequisite bagi olan dersler directed edge ile gosterilir.
- Ayni connected component icindeki dersler ayni renkte gosterilir.
- Baglantisiz dersler deterministik renklerle gosterilir.
- Bu arac main student planner uygulamasinin parcasi degildir.
