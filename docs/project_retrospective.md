# METU Student Planner Project Retrospective

Bu rapor, mevcut sohbetin devamı başka bir oturuma taşındığında projeyi sıfırdan
anlatabilmek için yazıldı. Raporun amacı sadece yapılan işleri özetlemek değil;
verinin nereden geldiğini, neden böyle modellendiğini, hangi dosyaların önemli
olduğunu, hangi kısımların güvenilir olduğunu ve hangi risklerin kaldığını da
açıkça kaydetmektir.

Son güncelleme tarihi: 2026-05-08.

## Kısa Cevap

Evet, ODTÜ Ankara kampüsü mühendislik fakültesindeki hedef 13 aktif lisans
bölümü için prerequisite ağı üretildi.

İki tür çıktı var:

1. Tüm mühendislikleri birlikte kapsayan birleşik graph:
   `data/processed/prerequisites/engineering-latest-prerequisite-closure.json`
2. Her bölüm için ayrı graph:
   `data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure.json`

Birleşik graph durumu:

- Program sayısı: 13
- Node sayısı: 393
- Edge sayısı: 504
- Unresolved course sayısı: 26
- Graph tipi: DAG
- Edge yönü: prerequisite -> course

Bölüm bazlı graph dosyaları da üretildi ve hepsinde `is_dag=True`.

Önemli ayrım: Buradaki `unresolved` kayıtları "pipeline hiç çalışmadı" anlamına
gelmez. Bunlar SAIS üzerinde aranan dönemlerde bulunamayan, eski/özel/servis
dersi olabilecek veya manuel kontrol gerektiren derslerdir. İnsan gözüyle
akademik doğrulama ayrıca yapılmalıdır.

## Ürün Vizyonu

Projenin hedefi bir öğrenci asistanı / ders planlayıcısı geliştirmektir.
Öğrenci şu bilgileri verecek:

- Bölümü
- Şimdiye kadar aldığı dersler
- Mümkünse aldığı notlar
- Planlamak istediği dönem

Sistem şunları söyleyebilmeli:

- Müfredatta hangi zorunlu dersler kaldı?
- Hangi derslerin prerequisite şartları sağlandı?
- Hangi dersleri almak gelecekte en çok dersi açar?
- Hangi dersler kritik zincir oluşturuyor?
- Önümüzdeki dönem için makul ders önerisi nedir?

Bu yüzden veri modeli sadece "ders listesi" değil; müfredat, prerequisite ağı,
dönem açılma bilgisi ve öğrenci geçmişi birlikte düşünülerek tasarlandı.

## En Önemli Mimari Karar

Projedeki en kritik karar şudur:

Bir bölümün açtığı dersler o bölümün müfredatı değildir.

Örnek:

- CENG bölümü CENG dersleri açar.
- Ama CENG öğrencisinin müfredatında MATH, PHYS, EE, STAT, ENG, TURK, HIST gibi
  başka bölümlerden dersler de vardır.
- Aynı durum diğer mühendislikler için de geçerlidir.

Bu yüzden veri iki ana katmanda modelleniyor:

1. Curriculum layer:
   Bir öğrencinin mezun olmak için tamamlaması gereken gereksinimler.
   Örnek: `MATH 119`, `MATH 120`, `CENG 213`, teknik seçmeli havuzu.

2. Prerequisite layer:
   Dersler arasındaki yönlü bağımlılıklar.
   Örnek: `MATH 119 -> MATH 120 -> MATH 219 -> CENG 384`.

Bu ayrım sayesinde bölüm dışı servis dersleri de doğru şekilde graph içine dahil
edilebiliyor.

## Hedef Bölümler

Aktif lisans mühendislik programları olarak şu 13 bölüm işlendi:

- AE: Aerospace Engineering
- CE: Civil Engineering
- CENG: Computer Engineering
- CHE: Chemical Engineering
- EEE: Electrical and Electronics Engineering
- ENVE: Environmental Engineering
- FDE: Food Engineering
- GEOE: Geological Engineering
- IE: Industrial Engineering
- ME: Mechanical Engineering
- METE: Metallurgical and Materials Engineering
- MINE: Mining Engineering
- PETE: Petroleum and Natural Gas Engineering

ES config içinde duruyor ama `is_active_undergraduate=false` olduğu için bu
aşamada işlenmedi.

Program konfigürasyonu:

- `config/engineering_programs.json`

Not: Bu dosyada Türkçe bölüm adlarında encoding bozulması görünüyor. Sistemin
ana işleyişi İngilizce adlar ve abbreviation üzerinden çalıştığı için bu şu an
veri üretimini bozmuyor; fakat UI aşamasından önce düzeltilmeli.

## Repository Yapısı

Ana yapı şu hale getirildi:

```text
student_planner/
  domain/
    models.py
  sources/
    base.py
    metu_catalog.py
  repositories/
  services/
  db/
    schema.sql
config/
  engineering_programs.json
data/
  raw/
  processed/
    curricula/
    prerequisites/
  db/
scripts/
  init_db.py
  load_programs.py
  scrape_curricula.py
  load_curricula.py
  build_prerequisite_closure.py
  load_prerequisite_closure.py
docs/
  architecture.md
  data_model.md
  curriculum_ingestion_plan.md
  roadmap.md
  project_retrospective.md
```

Eski deneme scriptleri de root altında duruyor:

- `scrape_metu_program_courses.py`
- `scrape_prerequisite_graph.py`

Bunlar tamamen çöpe atılmadı; SAIS login, form parse etme ve prerequisite
çekme mantığının önemli bölümleri yeni pipeline tarafından da kullanılıyor.

## Veri Katmanları

### Raw

`data/raw` altında kaynak sayfaların ham snapshot'ları saklanır. Amaç, parser
değişse bile aynı kaynak snapshot üzerinden yeniden işleme yapabilmektir.

METU Catalog sayfaları şu yapıda saklanır:

```text
data/raw/catalog/<PROGRAM>/<timestamp>/program.html
data/raw/catalog/<PROGRAM>/<timestamp>/metadata.json
```

### Processed

`data/processed` normalize edilmiş dosyaları içerir.

Curriculum çıktıları:

```text
data/processed/curricula/<PROGRAM>-latest.curriculum.json
data/processed/curricula/<PROGRAM>-latest.curriculum_requirements.csv
data/processed/curricula/all_engineering_latest_curriculum_requirements.csv
data/processed/curricula/curriculum_scrape_summary.csv
data/processed/curricula/curriculum_review_report.md
```

Prerequisite çıktıları:

```text
data/processed/prerequisites/engineering-latest-prerequisite-closure.json
data/processed/prerequisites/engineering-latest-prerequisite-closure-nodes.csv
data/processed/prerequisites/engineering-latest-prerequisite-closure-edges.csv
data/processed/prerequisites/engineering-latest-prerequisite-closure-unresolved.csv

data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure.json
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-nodes.csv
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-edges.csv
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-unresolved.csv
```

### Database

SQLite dosyası:

```text
data/db/student_planner.sqlite
```

SQLite ilk aşama için seçildi çünkü servis kurulumu gerektirmiyor, local scraping
ve validasyon için yeterli, ileride PostgreSQL'e taşınabilecek kadar ilişkisel
bir model sunuyor.

## Database Şeması

Şema dosyası:

- `student_planner/db/schema.sql`

Ana tablolar:

- `source_documents`: Kaynağın URL/path/hash/tarih bilgisini tutar.
- `programs`: Bölüm bilgileri.
- `courses`: Canonical dersler.
- `course_aliases`: İleride eşdeğer/eski kod gibi alias'lar için.
- `curriculum_versions`: Bölümün müfredat versiyonu.
- `curriculum_requirements`: Müfredattaki gereksinim slotları.
- `requirement_options`: Bir requirement içindeki ders seçenekleri.
- `prerequisite_edges`: Ders bağımlılıkları.
- `offerings`: Dönem açılan ders bilgisi için ayrılmıştır, henüz ana pipeline'da
  doldurulmuyor.
- `student_profiles`: İleride öğrenci input'u için.
- `student_completed_courses`: Öğrencinin tamamladığı dersler için.

Mevcut DB sayımları:

```text
programs: 14
courses: 393
curriculum_versions: 13
curriculum_requirements: 696
requirement_options: 652
prerequisite_edges: 504
source_documents: 14
```

`programs=14` olmasının sebebi ES'in config içinde pasif program olarak
tutulmasıdır. Aktif işlenen curriculum sayısı 13'tür.

## Curriculum Scraping Pipeline

Script:

- `scripts/scrape_curricula.py`

Parser:

- `student_planner/sources/metu_catalog.py`

Kaynak:

- METU Academic Catalog
- URL formatı: `https://catalog.metu.edu.tr/program.php?fac_prog=<program_id>`

Çalıştırma:

```powershell
python .\scripts\scrape_curricula.py
```

Belirli programlar için:

```powershell
python .\scripts\scrape_curricula.py --programs CENG EEE
```

Pipeline şu işleri yapar:

1. `config/engineering_programs.json` dosyasından aktif lisans programlarını okur.
2. Her programın METU Catalog sayfasını indirir.
3. Ham HTML dosyasını `data/raw/catalog/...` altına kaydeder.
4. `Undergraduate Curriculum` bölümünü parse eder.
5. Course requirement, choice group ve elective placeholder ayrımını yapar.
6. JSON ve CSV çıktılarını yazar.
7. Özet CSV ve review raporu üretir.

Curriculum parser şu tür requirement'ları ayırır:

- `required_course`
- `course_choice`
- `technical_elective_pool`
- `restricted_elective_pool`
- `nontechnical_elective_pool`
- `free_elective_pool`
- `summer_practice`
- `other`

Bu ayrım önemli çünkü öneri motoru ileride sadece tekil dersleri değil,
seçmeli havuzlarını da hesaba katmak zorunda.

## Curriculum Mevcut Durumu

`data/processed/curricula/curriculum_scrape_summary.csv` sonuçları:

| Program | Requirement | Unique Course | Course Option | Placeholder |
| --- | ---: | ---: | ---: | ---: |
| CENG | 50 | 46 | 46 | 10 |
| ENVE | 53 | 50 | 50 | 9 |
| EEE | 54 | 47 | 47 | 13 |
| IE | 56 | 53 | 53 | 9 |
| FDE | 52 | 49 | 49 | 9 |
| AE | 55 | 50 | 50 | 11 |
| CE | 54 | 49 | 49 | 11 |
| GEOE | 55 | 52 | 52 | 9 |
| CHE | 52 | 50 | 50 | 8 |
| MINE | 53 | 52 | 52 | 7 |
| ME | 54 | 51 | 51 | 9 |
| METE | 54 | 51 | 51 | 9 |
| PETE | 54 | 52 | 52 | 8 |

Birleşik curriculum CSV satır sayısı: 774.

Not: Bu veriler otomatik scrape edildi. `review_status=scraped` olarak ele
alınmalı; production seviyesinde kullanmadan önce insan kontrolü yapılmalıdır.

## Curriculum Verisini Database'e Yükleme

DB oluşturma ve program yükleme:

```powershell
python .\scripts\init_db.py
python .\scripts\load_programs.py
```

Curriculum JSON dosyalarını DB'ye yükleme:

```powershell
python .\scripts\load_curricula.py
```

`load_curricula.py` her `*-latest.curriculum.json` dosyasını okur, ilgili
programı bulur, source document kaydı açar, curriculum version oluşturur,
requirement'ları ve option derslerini DB'ye yazar.

## Prerequisite Closure Pipeline

Script:

- `scripts/build_prerequisite_closure.py`

Bu script SAIS üzerinden çalışır ve login gerektirir. Giriş bilgileri
`env.local` dosyasından okunur. Bu dosya `.gitignore` içindedir ve rapora
şifre/kullanıcı adı yazılmamalıdır.

Birleşik graph üretmek:

```powershell
python .\scripts\build_prerequisite_closure.py
```

Bölüm bazlı graph üretmek:

```powershell
python .\scripts\build_prerequisite_closure.py --programs CENG
```

Birden fazla program için:

```powershell
python .\scripts\build_prerequisite_closure.py --programs CENG EEE ME
```

Debug amaçlı limit:

```powershell
python .\scripts\build_prerequisite_closure.py --programs CENG --max-courses 10
```

Pipeline mantığı:

1. `data/processed/curricula/*-latest.curriculum.json` dosyalarını okur.
2. Müfredatlardaki gerçek dersleri seed node olarak alır.
3. Graduate dersleri filtreler. Normal 5xx/6xx/7xx/8xx/9xx blokları dışarıda
   bırakılır. `HIST 2201` gibi dört haneli undergraduate servis dersleri özel
   olarak korunur.
4. SAIS'e giriş yapar.
5. View Program Course Details ekranını açar.
6. Dersin numeric code'una göre department value ve semester seçeneklerinde arar.
7. Ders bulunduğunda radio input ile o dersi seçer.
8. `Prerequisite` butonuna karşılık gelen form post'unu yapar.
9. Gelen prerequisite tablosunu parse eder.
10. Bulunan prerequisite dersleri graph'a edge olarak ekler.
11. Yeni prerequisite dersleri de kuyruğa koyar.
12. Kuyruk bitene kadar recursive closure devam eder.

Bu yüzden sadece müfredatta görünen derslerin değil, onların prerequisite'lerinin
de prerequisite'leri bulunur.

Örnek zincirler bu yaklaşımla yakalanır:

```text
MATH 119 -> MATH 120 -> MATH 219 -> CENG 384
MATH 119 -> MATH 120 -> EE 281
CENG 140 -> CENG 213
```

## Prerequisite Graph Semantiği

Graph JSON içinde:

- `nodes`: Dersler.
- `edges`: Bağımlılıklar.
- `unresolved`: SAIS aramasında bulunamayan dersler.
- `topological_order`: Numeric code sırasına göre değil, prerequisite yönüne göre
  topological sıralama.

Edge yönü:

```text
from = prerequisite
to = prerequisite'e bağlı ders
```

Yani:

```text
MATH 119 -> MATH 120
```

şu anlama gelir:

`MATH 120` alabilmek için `MATH 119` gerekir.

Edge alanları:

- `from`
- `from_course_code`
- `to`
- `to_course_code`
- `set_no`
- `min_grade`
- `type`
- `position`

`set_no`, `type`, `position` ve `min_grade` alanları özellikle korunuyor.
Çünkü prerequisite mantığı bazen sadece düz "şu ders gerekir" değildir; alternatif
setler, minimum notlar veya farklı requirement pozisyonları olabilir. Recommendation
engine yazılırken bu alanlar akademik anlamı doğrulanarak kullanılmalıdır.

## Birleşik Prerequisite Graph Durumu

Dosya:

- `data/processed/prerequisites/engineering-latest-prerequisite-closure.json`

Metadata:

```text
programs:
  AE, CE, CENG, CHE, EEE, ENVE, FDE, GEOE, IE, ME, METE, MINE, PETE
generated_at_utc: 2026-05-08T05:15:12+00:00
searched_semesters:
  20252, 20251, 20243, 20242, 20241, 20233, 20232, 20231,
  20223, 20222, 20221, 20213, 20212, 20211, 20203
node_count: 393
edge_count: 504
unresolved_count: 26
is_dag: true
edge_direction: prerequisite -> course
```

Bu birleşik graph DB'ye de yüklendi.

DB'ye yükleme:

```powershell
python .\scripts\load_prerequisite_closure.py --clear-existing
```

Varsayılan olarak birleşik engineering closure dosyasını yükler. Bölüm bazlı
dosyalar ayrıca export olarak durur; DB'ye hepsini ayrı ayrı yüklemek edge
tekrarlarına yol açabileceği için şu aşamada birleşik graph source of truth gibi
kullanıldı.

## Bölüm Bazlı Prerequisite Graph Durumu

`data/processed/prerequisites/prerequisite_closure_summary.csv`:

| Program | Nodes | Edges | Unresolved | DAG |
| --- | ---: | ---: | ---: | --- |
| AE | 67 | 47 | 13 | True |
| CE | 63 | 50 | 4 | True |
| CENG | 77 | 93 | 3 | True |
| CHE | 75 | 133 | 6 | True |
| EEE | 58 | 73 | 1 | True |
| ENVE | 74 | 84 | 5 | True |
| FDE | 80 | 126 | 9 | True |
| GEOE | 72 | 78 | 4 | True |
| IE | 74 | 65 | 7 | True |
| ME | 68 | 69 | 1 | True |
| METE | 69 | 64 | 5 | True |
| MINE | 72 | 72 | 4 | True |
| PETE | 88 | 113 | 7 | True |

Bunlar 2026-05-08 tarihinde yeniden üretildi. Dolayısıyla şu an hedef 13 bölüm
için "işlenmemiş curriculum JSON var ama prerequisite closure'a sokulmadı" gibi
bir durum kalmadı.

## Eski CSV Dosyalarının Durumu

Root altında eski deneysel dosyalar var:

```text
CENG-20241.csv
CENG-20242.csv
EEE-20241.csv
EEE-20242.csv
...
STAT-20241.csv
STAT-20242.csv
```

Bunlar SAIS üzerinden "bir departmanın bir dönemde açtığı dersler" olarak
çekilmişti. İlk prerequisite graph denemeleri de iki dönem CSV'si üzerinden
çalışıyordu.

Yeni ürün mimarisinde bunlar ana müfredat kaynağı değildir. Bunlar ileride
`offerings` tablosu için kullanılabilir, fakat şu anki "latest curriculum +
prerequisite closure" pipeline'ının source of truth'u değildir.

Bu yüzden "elimizde olup da işlenmemiş data" sorusunun cevabı şu şekilde:

- Current curriculum/prerequisite pipeline açısından işlenmemiş hedef bölüm
  datası kalmadı.
- Root altındaki eski offering CSV'leri henüz DB'deki `offerings` tablosuna
  normalize edilmedi; bu ayrı bir sonraki veri katmanı işi.
- STAT dosyaları mühendislik hedef kapsamına dahil değil, eski test verisi gibi
  düşünülmeli.

## Test ve Doğrulama

Yapılan otomatik kontroller:

1. 13 curriculum JSON dosyasının üretildiği doğrulandı.
2. `all_engineering_latest_curriculum_requirements.csv` satır sayısı kontrol
   edildi: 774.
3. Birleşik prerequisite graph metadata kontrol edildi:
   13 program, 393 node, 504 edge, 26 unresolved, `is_dag=true`.
4. Her program için ayrı prerequisite closure üretildi.
5. Her program için `is_dag=true` doğrulandı.
6. SQLite tablo sayımları kontrol edildi.
7. Örnek kritik edge'ler kontrol edildi:
   `MATH 119 -> MATH 120`,
   `MATH 120 -> MATH 219`,
   `MATH 120 -> EE 281`,
   `MATH 219 -> CENG 384`,
   `MATH 260 -> CENG 384`,
   `CENG 140 -> CENG 213`.

Bu kontroller graph'ın teknik olarak üretildiğini ve beklenen servis dersi
zincirlerini yakaladığını gösterir. Akademik doğruluk için manuel review
ayrı bir iş kalemidir.

## Bilinen Riskler ve Eksikler

### 1. Manual review henüz yapılmadı

Curriculum verileri `review_status=scraped` seviyesinde. Production için:

- Her bölümün Catalog sayfası ile JSON/CSV karşılaştırılmalı.
- En güncel müfredat gerçekten Catalog'daki mi kontrol edilmeli.
- Department web sayfasında daha güncel PDF varsa farklar not edilmeli.

### 2. Elective havuzları henüz tam modellenmedi

Parser seçmeli placeholder'ları ayırıyor ama teknik seçmeli listelerinin içerik
havuzları henüz detaylı çekilmiyor. Örneğin "Technical Elective" bir requirement
olarak var; ama hangi derslerin o havuza sayıldığı ayrı kaynaklardan
doğrulanmalı.

### 3. Prerequisite set mantığı engine'e dönüşmedi

`set_no`, `type`, `position`, `min_grade` korunuyor ama henüz "öğrenci bu dersi
alabilir mi?" diye karar veren servis yazılmadı. Bir sonraki aşamada prerequisite
fulfillment evaluator yazılırken SAIS'in set mantığı dikkatle doğrulanmalı.

### 4. Unresolved kayıtlar manuel incelenmeli

Birleşik graph'ta 26 unresolved var. Bölüm bazlı unresolved sayıları rapora
yazıldı. Bunlar genellikle şu sebeplerden olabilir:

- Ders aranan SAIS dönemlerinde açılmamıştır.
- Ders kodu değişmiş olabilir.
- Ders özel servis/uygulama/staj dersi olabilir.
- Catalog ve SAIS numeric code eşleşmesinde özel bir durum olabilir.

Unresolved dosyaları:

```text
data/processed/prerequisites/*-unresolved.csv
```

### 5. Offering layer henüz normalize edilmedi

Öğrenciye "önümüzdeki dönem ne al" demek için sadece prerequisite yetmez.
Dersin o dönem açılıp açılmayacağı da gerekir.

`offerings` tablosu hazır ama doldurulmadı. Eski root CSV'ler bunun ilk girdisi
olabilir; daha iyi çözüm ise offering scraper'ı `student_planner/sources` altına
taşımak ve dönem bazlı normalize loader yazmaktır.

### 6. Eski root scriptler yeni mimariye tam taşınmadı

`scrape_metu_program_courses.py` ve `scrape_prerequisite_graph.py` çalışır
durumda geçmiş deneme araçlarıdır. Yeni işlerin `student_planner/` ve `scripts/`
altında ilerlemesi daha doğru.

### 7. Test suite yok

Şu an doğrulamalar komutlar ve dosya sayımlarıyla yapıldı. Kalıcı güven için
unit/integration testleri eklenmeli:

- Catalog parser fixture testleri
- Prerequisite table parser testleri
- DAG/topological sort testleri
- DB loader idempotency testleri
- Recommendation evaluator testleri

## Önerilen Sonraki Aşamalar

### Aşama 1: Review workflow

Amaç otomatik scrape edilen verinin insan kontrolünden geçmesini kolaylaştırmak.

Yapılacaklar:

- `curriculum_review_report.md` daha detaylı hale getirilmeli.
- Her bölüm için diff/checklist üretilecek bir script yazılmalı.
- Unresolved prerequisite dosyaları tek bir review queue'ya dönüştürülmeli.
- Manuel correction dosyası tasarlanmalı.

Önerilen dosya:

```text
data/manual/corrections/curriculum_overrides.json
data/manual/corrections/prerequisite_overrides.json
```

### Aşama 2: Offering layer

Amaç dönem açılan ders bilgisini DB'ye almak.

Yapılacaklar:

- SAIS offering scraper yeni mimariye taşınmalı.
- Output JSON/CSV formatı standardize edilmeli.
- `offerings` tablosuna loader yazılmalı.
- Eski root CSV'ler ya archive edilmeli ya da normalize edilip DB'ye alınmalı.

### Aşama 3: Prerequisite fulfillment engine

Amaç öğrencinin aldığı derslere göre hangi dersleri alabileceğini hesaplamak.

Girdi:

- Student completed courses
- Grade bilgisi
- Prerequisite edges
- Min grade
- Set logic

Çıktı:

- `eligible`
- `blocked`
- `missing_prerequisites`
- `satisfied_sets`
- `blocking_chains`

### Aşama 4: Recommendation service

Amaç sadece uygun dersleri listelemek değil, iyi bir dönem planı önermek.

Hesaba katılacak sinyaller:

- Müfredatta önerilen yıl/dönem
- Kalan zorunlu dersler
- Dersin açacağı future ders sayısı
- Prerequisite zincirindeki kritikliği
- Dönem açılma olasılığı
- Öğrencinin kredi yükü
- Elective/required dengesi

### Aşama 5: API veya CLI prototipi

Önce basit CLI yeterli:

```powershell
python .\scripts\recommend_next_semester.py --program CENG --completed "MATH 119,CENG 140,PHYS 105"
```

Daha sonra web UI/API düşünülebilir.

## Yeni Bir Sohbet Oturumu İçin Başlangıç Rehberi

Yeni oturumda şu sırayla ilerlemek iyi olur:

1. Bu dosyayı oku:
   `docs/project_retrospective.md`
2. Mimari notları oku:
   `docs/architecture.md`
   `docs/data_model.md`
   `docs/curriculum_ingestion_plan.md`
   `docs/roadmap.md`
3. Mevcut veri özetlerini kontrol et:
   `data/processed/curricula/curriculum_scrape_summary.csv`
   `data/processed/prerequisites/prerequisite_closure_summary.csv`
4. Birleşik graph'ı incele:
   `data/processed/prerequisites/engineering-latest-prerequisite-closure.json`
5. DB sayımlarını doğrula:

```powershell
@'
import sqlite3
conn = sqlite3.connect("data/db/student_planner.sqlite")
for table in [
    "programs",
    "courses",
    "curriculum_versions",
    "curriculum_requirements",
    "requirement_options",
    "prerequisite_edges",
    "source_documents",
]:
    print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
'@ | python -
```

6. Bir sonraki mantıklı implementation task olarak prerequisite fulfillment
   engine veya review workflow seç.

## Reproduce Komutları

Tam veri pipeline'ını tekrar üretmek için:

```powershell
python .\scripts\init_db.py
python .\scripts\load_programs.py
python .\scripts\scrape_curricula.py
python .\scripts\load_curricula.py
python .\scripts\build_prerequisite_closure.py
python .\scripts\load_prerequisite_closure.py --clear-existing
```

Bölüm bazlı prerequisite closure üretmek için:

```powershell
$programs = @(
  'AE','CE','CENG','CHE','EEE','ENVE','FDE',
  'GEOE','IE','ME','METE','MINE','PETE'
)

foreach ($p in $programs) {
  python .\scripts\build_prerequisite_closure.py --programs $p
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

Not: SAIS login gerektiren komutlar için `env.local` içinde
`METU_USERNAME` ve `METU_PASSWORD` bulunmalıdır. Bu dosya paylaşılmamalıdır.

## Son Durum

Proje artık tekil scraper denemesi olmaktan çıktı. Elimizde:

- 13 bölüm için latest curriculum verisi
- Bölüm dışı servis derslerini de kapsayan recursive prerequisite closure
- Birleşik mühendislik prerequisite DAG
- Her bölüm için ayrı prerequisite DAG
- SQLite tabanlı başlangıç veri modeli
- Source snapshot ve provenance yaklaşımı
- İleride recommendation engine'e genişleyebilecek paket yapısı

Bir sonraki ana hedef, bu veriyi öğrenci input'u ile çalıştıracak domain
servislerini yazmaktır. En kritik ilk servis prerequisite fulfillment engine'dir:
öğrencinin aldığı dersleri ve notlarını verip hangi derslerin açık, hangilerinin
hangi zincirler yüzünden kapalı olduğunu hesaplamalıdır.
