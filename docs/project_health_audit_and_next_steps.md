# Project Health Audit and Next Steps

Son güncelleme: 2026-05-08

Bu doküman projenin mevcut teknik/veri durumunu denetlemek ve bir sonraki
birkaç adımı dikkatli biçimde planlamak için yazıldı. Odak noktası şudur:

Bir öğrenciye ders tavsiyesi verecek sisteme geçmeden önce elimizdeki veri
gerçekten temiz, güvenilir ve ürün mantığına hazır mı?

Kısa cevap:

- Teknik pipeline çalışır durumda.
- 13 mühendislik bölümü için latest curriculum ve prerequisite closure var.
- SQLite DB ilişkisel olarak sağlam.
- Ancak veri hâlâ `scraped` seviyesinde; production-grade recommendation için
  review, normalization, offerings ve planning service katmanları eksik.

## İncelenen Katmanlar

Bu audit sırasında şu katmanlar kontrol edildi:

- Proje dosya ağacı
- Mevcut mimari ve roadmap dokümanları
- SQLite DB dosyası
- DB tabloları ve ilişkileri
- Processed curriculum JSON/CSV dosyaları
- Processed prerequisite graph JSON/CSV dosyaları
- Raw catalog snapshot yapısı
- Root klasördeki eski deneysel CSV/JSON artefact'leri
- Kod organizasyonu ve eksik paket/test altyapısı

## Mevcut Roadmap Durumu

Dokümanlardaki ana fazlar:

```text
Phase 0: Foundation
Phase 1: Curriculum Ingestion
Phase 2: Prerequisite Closure
Phase 3: Student Planning Logic
Phase 4: UI Prototype
```

Mevcut durum:

- Phase 0 büyük ölçüde tamamlandı.
- Phase 1 teknik olarak tamamlandı ama manual review tamamlanmadı.
- Phase 2 teknik olarak tamamlandı ama data hardening tamamlanmadı.
- Phase 3 başlamadı.
- Phase 4 başlamadı.

Bu yüzden önerilen yeni ara faz:

```text
Phase 2.5: Data Hardening, Review Workflow, Identity Normalization
```

Bu ara faz yapılmadan Phase 3'e geçmek mümkün ama riskli olur. Çünkü öğrenciye
yanlış tavsiye verme riski doğrudan veri anlamlandırma hatalarından gelir.

## Dosya Sistemi Durumu

Ana kaynak ve çıktı yapısı doğru yerde:

```text
data/raw/catalog/
data/processed/curricula/
data/processed/prerequisites/
data/db/
student_planner/
scripts/
docs/
config/
```

Ancak root klasörde eski deneysel dosyalar duruyor:

```text
AE-20241.csv
AE-20242.csv
CENG-20241.csv
CENG-20242.csv
EEE-20241.csv
EEE-20242.csv
...
STAT-20241.csv
STAT-20242.csv
*-20241-20242-prerequisite-*.csv/json
```

Bunlar ana pipeline'ın source of truth'u değil. Bunlar:

- Eski offering scraper denemeleri
- Eski iki dönemlik prerequisite graph denemeleri
- STAT gibi mühendislik dışı test verileri

Karar:

- Silinmemeliler; historical/debug değeri var.
- Ama root klasörde kalmaları kafa karıştırıyor.
- `data/legacy/` veya `data/archive/experiments/` altına taşınmaları iyi olur.

Not: `env.local` var ve `.gitignore` içinde. Gizli bilgi dosyası paylaşılmamalı.

## DB Dosyaları

`data/db` altında iki dosya var:

```text
data/db/.gitkeep
data/db/student_planner.sqlite
```

### `.gitkeep`

Sadece klasörü repoda tutmak için placeholder. Veri içermez.

### `student_planner.sqlite`

DB teknik kontrolleri:

```text
integrity_check: ok
foreign_key_check: 0 hata
source hash mismatch: yok
DB üstünde DAG check: true
```

Sonuç:

DB dosyası bozuk değil, ilişkisel olarak tutarlı ve şu an local prototip için
kullanılabilir.

Ancak DB içindeki veriler production recommendation için henüz "reviewed" değil.

## DB Tablo Durumu

Mevcut tablo sayımları:

```text
programs: 14
courses: 393
curriculum_versions: 13
curriculum_requirements: 696
requirement_options: 652
prerequisite_edges: 504
source_documents: 14
course_aliases: 0
offerings: 0
student_profiles: 0
student_completed_courses: 0
```

`programs=14` çünkü ES pasif program olarak config içinde tutuluyor. Aktif
işlenen mühendislik lisans programı 13.

## Tablo Bazlı Kullanıma Hazırlık

### `programs`

Durum:

- 14 program var.
- 13 aktif lisans programı doğru şekilde işleniyor.
- ES pasif.

Sorun:

- `name_tr` alanlarında encoding bozulması var.
- Örnekler:
  - `Havacýlýk ve Uzay Mühendisliði`
  - `Ýnþaat Mühendisliði`
  - `Gýda Mühendisliði`

Etkisi:

- Core pipeline etkilenmiyor çünkü `abbr` ve `name_en` kullanılıyor.
- UI veya Türkçe raporlama aşamasında kötü görünür.

Karar:

- Kullanıma kısmen hazır.
- UI öncesi temizlenmeli.

### `courses`

Durum:

- 393 course var.
- Tüm course kayıtlarında `numeric_code` var.
- `level` alanı tümünde `undergraduate`.
- Duplicate `display_code` veya `numeric_code` constraint ile engellenmiş.
- 5xx-999 arası graduate course yok.

Sorunlar:

- 1 dersin title alanı boş:
  - `HIST 2202`
- 4 dersin course number'ı 999 üstünde:
  - `HIST 2201`
  - `HIST 2202`
  - `HIST 2205`
  - `HIST 2206`
- 35 node numeric subject code ile görünüyor:
  - `355 140`
  - `357 119`
  - `374 321`
  - benzeri

Yorum:

HIST 2201 gibi dersler undergraduate servis dersleri olduğu için 999 üstü
olmaları tek başına hata değil. Fakat "course number > 999" kuralı ileride
graduate/undergraduate ayrımında dikkatli ele alınmalı.

Numeric subject code'lar daha önemli bir konu. Bunların önemli bir kısmı NCC
veya farklı campus/eşdeğer ders alternatifleri gibi görünüyor. Mevcut graph
bunları kaybedip silmiyor; bu iyi. Ama UI'da veya Ankara öğrencisi önerisinde
`355 140` gibi görünmeleri doğru değil.

Karar:

- Teknik olarak kullanılabilir.
- Recommendation için course identity normalization gerekli.

### `curriculum_versions`

Durum:

- 13 latest curriculum version var.
- Hepsi `review_status=scraped`.

Sorun:

- Hiçbiri `reviewed` değil.
- Entrance-year-specific curriculum versiyonları yok.

Karar:

- Prototype için kullanılabilir.
- Production için manual review şart.

### `curriculum_requirements`

Durum:

- 696 requirement var.
- Hepsi `review_status=scraped`.
- Requirement type dağılımı:

```text
required_course: 496
technical_elective_pool: 57
course_choice: 52
nontechnical_elective_pool: 31
summer_practice: 26
restricted_elective_pool: 21
free_elective_pool: 13
```

İyi taraf:

- Müfredat sadece tekil ders listesi gibi modellenmemiş.
- Elective pool, course choice ve summer practice ayrımı korunmuş.

Sorun:

- Elective pool'ların gerçek ders havuzları henüz çözülmedi.
- Örneğin "Technical Elective" requirement olarak var ama hangi derslerin teknik
  seçmeli sayıldığı ayrı kaynaklardan alınmadı.

Karar:

- Zorunlu ders progress hesaplaması için iyi başlangıç.
- Tam mezuniyet planı ve seçmeli önerisi için eksik.

### `requirement_options`

Durum:

- 652 concrete course option var.
- Actual course option'larda missing numeric code yok.
- Program içinde duplicate required course görünmedi.

Önemli not:

Combined curriculum CSV'de 774 satır var. Bunun sebebi:

```text
652 concrete course option
122 placeholder/elective requirement row
= 774 CSV row
```

DB'de placeholder requirement'lar `requirement_options` içinde fake course olarak
tutulmuyor; `curriculum_requirements` içinde category requirement olarak duruyor.
Bu doğru modelleme.

Karar:

- Kullanıma hazır ama elective pool expansion eksik.

### `prerequisite_edges`

Durum:

- 504 edge var.
- Self edge yok.
- `set_no`, `min_grade`, `edge_type`, `position` boş değil.
- DB üstünde graph DAG.
- Duplicate edge yok.

Dağılım:

```text
min_grade:
  DD: 479
  S: 22
  U: 3

edge_type:
  Undergraduate / Lisans: 438
  Undergraduate NCC / Lisans KKK: 55
  Labaratory / Laboratuvar: 9
  Term Project / Dönem Projesi: 1
  Undergraduate Practice / Lisans Staj: 1
```

Sorunlar:

- `position` alanındaki Türkçe kısım encoding bozuk:
  - `Offered Course / A??k Ders`
  - `Closed Course / Kapal? Ders`
- `Labaratory` kaynaktan geldiği haliyle typo içeriyor olabilir.
- 55 edge NCC alternatiflerini temsil ediyor.
- `set_no` mantığı henüz domain service içinde yorumlanmadı.

Yorum:

`set_no` muhtemelen alternatif prerequisite setlerini gösteriyor:

- Aynı `set_no` içindeki dersler birlikte gerekir.
- Farklı `set_no` değerleri alternatif yollar olabilir.

Bu akademik olarak birkaç örnekle doğrulanmadan fulfillment engine yazılırsa
yanlış eligibility kararı verilebilir.

Karar:

- Graph traversal ve unlock analysis için kullanılabilir.
- "Bu öğrenci bu dersi alabilir mi?" kararı için önce set semantics doğrulanmalı.

### `source_documents`

Durum:

- 14 kayıt var.
- 13 METU Academic Catalog snapshot.
- 1 processed prerequisite closure source.
- Tüm content path'ler mevcut.
- Hash mismatch yok.

Karar:

- Provenance açısından iyi durumda.

### Boş Tablolar

Şu tablolar boş:

```text
course_aliases
offerings
student_profiles
student_completed_courses
```

Bu beklenen bir durum ama roadmap açısından anlamı şudur:

- `offerings` boş olduğu için "önümüzdeki dönem açılır mı?" sorusunu şu an DB
  cevaplayamaz.
- `student_profiles` ve `student_completed_courses` boş olduğu için kişisel
  recommendation henüz başlamadı.
- `course_aliases` boş olduğu için eski kod/yeni kod/NCC eşdeğerliği henüz
  modellenmedi.

## Processed Curriculum Dosyaları

Durum:

- 13 `*-latest.curriculum.json` var.
- Her program için `*-latest.curriculum_requirements.csv` var.
- Combined CSV var.

Validation sonucu:

```text
curriculum json count: 13
combined csv rows: 774
empty course rows: 122
missing numeric code for actual courses: 0
```

Her programda actual course option sayısı ve unique course sayısı eşleşiyor.
Bu iyi bir işaret: parser aynı dersi aynı program içinde beklenmedik biçimde
tekrar üretmemiş.

Kullanıma hazırlık:

- Zorunlu ders planlama prototipi için yeterli.
- Production için latest curriculum assumption ve elective category'ler review
  edilmeli.

## Processed Prerequisite Dosyaları

Durum:

- Birleşik engineering graph var.
- 13 programın her biri için ayrı graph var.
- Toplam closure JSON sayısı 14.

Birleşik graph:

```text
nodes: 393
edges: 504
unresolved: 26
is_dag: true
numeric_display_nodes: 35
```

Tüm JSON/CSV kontrolleri:

- Edge endpoint'leri node listesinde mevcut.
- Topological order node sayısıyla aynı.
- Duplicate edge yok.
- JSON ve CSV satır sayıları eşleşiyor.

Program bazlı graph'ların hepsinde `is_dag=true`.

Kullanıma hazırlık:

- Graph analytics için hazır.
- Öğrenci eligibility/recommendation için normalization ve set semantics review
  gerekli.

## Unresolved Kayıtlar

Birleşik graph'ta 26 unresolved course var.

Örnekler:

```text
AEE 202
AEE 266
AEE 301
AEE 302
AEE 338
AEE 345
AEE 346
AEE 364
AEE 371
AEE 385
CHEM 109
CHEM 110
MATH 151
MATH 152
MATH 155
MATH 156
MATH 157
MATH 158
MATH 253
MATH 257
CENG 229
CENG 230
IE 262
AE 122
AE 241
374 216
```

Bunlar "işlenmemiş dosya" anlamına gelmiyor. Closure pipeline bu dersleri
aramış, ama search edilen SAIS dönemlerinde bulamamış.

Öncelik:

- Unresolved kayıtlar manual review queue'ya dönüştürülmeli.
- Bazıları eski ders kodu, bazıları açılmayan ders, bazıları eşdeğer/NCC veya
  curriculum transition dersi olabilir.

## Raw Snapshot Durumu

`data/raw/catalog` altında 56 dosya var. Her program için genellikle 2 snapshot,
CENG için 4 snapshot var. Bunun sebebi scrape'in birkaç kez çalıştırılmış
olması.

Bu kötü değil; raw snapshot saklamak doğru. Ama ileride:

- Hangi snapshot latest processed output'a kaynak oldu?
- Hangi snapshot eski deneme?
- Snapshot retention policy ne?

gibi sorular için bir manifest veya source registry iyi olur.

## Kod Organizasyonu Durumu

İyi taraflar:

- `student_planner/` package yapısı başladı.
- Domain models var.
- METU Catalog source adapter var.
- DB schema ayrılmış.
- CLI script'ler `scripts/` altında.

Eksikler:

- `student_planner/services/` boş.
- `student_planner/repositories/` boş.
- Test klasörü yok.
- `pyproject.toml` veya `requirements.txt` yok.
- Eski root scriptler hâlâ kritik logic içeriyor.
- SAIS client hâlâ `scrape_metu_program_courses.py` içinde.
- Offering scraper sabit değerlerle çalışıyor ve şu an `DEPARTMENT_ABBR="STAT"`
  gibi eski deneme state'i taşıyor.

Karar:

- Kodbase araştırma/prototip aşaması için iyi ilerlemiş.
- Ürünleşme için servis/repository/test ayrımı şart.

## En Büyük Veri Riskleri

### 1. Review status hâlâ `scraped`

Bu en büyük akademik doğruluk riski. Sistem teknik olarak veri üretiyor ama
henüz insan onayından geçmiş değil.

### 2. NCC ve numeric subject code'lar

Graph içinde `355 140`, `357 119`, `374 321` gibi display code'lar var. Bunlar
muhtemelen NCC/eşdeğer/campus-specific dersler.

Ankara kampüsü öğrencisine öneri verirken:

- Bunları doğrudan gösterelim mi?
- Ankara course eşdeğerine map edelim mi?
- Alternatif prerequisite set olarak koruyup default UI'da gizleyelim mi?

Bu karar verilmeden recommendation engine eksik kalır.

### 3. Offering data yok

Bir ders prerequisite açısından alınabilir olsa bile ilgili dönemde açılmıyor
olabilir. Bu yüzden "next semester recommendation" için offerings katmanı
zorunlu.

### 4. Elective pool detayları yok

Zorunlu dersleri planlayabiliriz ama teknik seçmeli önerisi için seçmeli havuz
kuralları gerekli.

### 5. Set semantics doğrulanmadı

Prerequisite `set_no` yanlış yorumlanırsa öğrenciye "alabilirsin" denilen ders
aslında kapalı olabilir.

## Önerilen Öncelikli Yol Haritası

### Phase 2.5A: Data Quality Gate

Amaç:

Veri üretildikten sonra her run'da aynı kalite kontrollerini otomatik yapmak.

Deliverable:

```text
scripts/audit_data_quality.py
data/processed/reports/data_quality_report.md
```

Kontroller:

- DB integrity check
- Foreign key check
- Source hash check
- Curriculum JSON count
- Program coverage
- Missing numeric code
- Duplicate requirements
- Empty course title
- Numeric subject code count
- Unresolved count
- Graph endpoint validation
- DAG validation
- CSV/JSON row consistency
- Review status summary
- Empty expected tables

Exit code politikası:

- Fatal schema/foreign key/hash/cycle hatası varsa non-zero.
- Review gerektiren ama beklenen durumlar warning.

Neden ilk adım bu?

Çünkü bundan sonra yapacağımız her scraper veya normalization değişikliğinde
veriyi bozup bozmadığımızı hızlıca anlayacağız.

### Phase 2.5B: Course Identity Normalization

Amaç:

Course identity'yi ürün mantığına hazır hale getirmek.

Yapılacaklar:

1. Program config'teki Türkçe encoding düzeltilecek.
2. SAIS numeric department mapping merkezi bir config'e taşınacak.
3. NCC numeric department code'ları ayrı şekilde modellenecek.
4. `courses` tablosuna gerekirse şu alanlar eklenecek:
   - `campus`
   - `canonical_subject_code`
   - `canonical_display_code`
   - `source_subject_code`
5. `course_aliases` aktif kullanılacak.
6. Unknown numeric display code'lar için review listesi üretilecek.

Önerilen karar:

- Raw graph'tan NCC edge'leri silmeyelim.
- Ama recommendation engine varsayılan olarak Ankara öğrencisine Ankara
  curriculum course'larını önceliklendirsin.
- NCC alternatifleri "equivalent/alternative prerequisite set" olarak
  tutulabilir, fakat UI'da ayrı etiketlenmeli.

### Phase 2.5C: Manual Review and Correction Workflow

Amaç:

Scraped veriyi "reviewed" hale getirecek mekanizma kurmak.

Önerilen dosyalar:

```text
data/manual/reviews/curricula/<PROGRAM>.review.json
data/manual/reviews/prerequisites/unresolved.review.json
data/manual/corrections/course_aliases.json
data/manual/corrections/prerequisite_overrides.json
data/manual/corrections/curriculum_overrides.json
```

Minimum review alanları:

- Reviewer
- Review date
- Source checked
- Accepted/corrected/deprecated status
- Notes

Öncelikli review queue:

1. 26 unresolved course
2. 35 numeric display node
3. 1 empty title course
4. NCC edges
5. Elective placeholders
6. Her bölüm için latest curriculum assumption

### Phase 2.6: Offerings Layer

Amaç:

`offerings` tablosunu doldurmak ve "bu dönem açılır mı?" sorusunu cevaplamak.

Yapılacaklar:

1. `scrape_metu_program_courses.py` içindeki SAIS client/source logic
   `student_planner/sources/sais.py` altına taşınacak.
2. Offering scraper sabit değerlerden kurtarılacak.
3. CLI örneği:

```powershell
python .\scripts\scrape_offerings.py --programs CENG EEE ME --semesters 20241 20242
```

4. Output yapısı:

```text
data/raw/sais/offerings/<semester>/<program>/...
data/processed/offerings/<semester>/<program>.offerings.json
data/processed/offerings/all_engineering_offerings.csv
```

5. Loader:

```powershell
python .\scripts\load_offerings.py
```

6. DB `offerings` tablosu doldurulacak.

Not:

Root klasördeki eski `CENG-20241.csv` gibi dosyalar bu aşamada archive edilip
istersek seed input olarak normalize edilebilir. Ama yeni source of truth
processed offerings klasörü olmalı.

### Phase 3A: Prerequisite Fulfillment Engine

Amaç:

Öğrencinin tamamladığı derslere göre bir target course'un alınabilir olup
olmadığını hesaplamak.

Önerilen module:

```text
student_planner/services/prerequisite_evaluator.py
```

Temel model:

```text
CompletedCourse(display_code, grade)
PrerequisiteSet(set_no, required_courses)
EligibilityResult(
    course,
    is_eligible,
    satisfied_sets,
    missing_by_set,
    explanation
)
```

Kurallar:

- Aynı `set_no` içindeki edge'ler AND.
- Farklı `set_no` değerleri OR.
- Bu varsayım gerçek örneklerle test edilmeden final kabul edilmemeli.
- Grade ordering tanımlanmalı:
  - AA, BA, BB, CB, CC, DC, DD, FD, FF
  - S/U dersleri ayrıca ele alınmalı.
- `min_grade=U` özel yorumlanmalı; HIST örneklerinde görünüyor.

Minimum test case'ler:

- `MATH 119 -> MATH 120`
- `MATH 120 -> MATH 219`
- `MATH 219 + MATH 260 -> CENG 384`
- `CENG 140 -> CENG 213`
- HIST S/U zinciri
- NCC alternative set içeren bir örnek

### Phase 3B: Curriculum Progress Service

Amaç:

Öğrencinin müfredattaki ilerlemesini hesaplamak.

Önerilen module:

```text
student_planner/services/curriculum_progress.py
```

Çıktılar:

- Completed required courses
- Remaining required courses
- Satisfied course_choice requirements
- Unsatisfied elective placeholders
- Recommended year/semester'a göre geride/ileride olma durumu

İlk versiyonda elective pool'lar sadece "unresolved category" olarak
gösterilebilir. Yani sistem yanlış seçmeli önermesin; eksik olduğunu açıkça
söylesin.

### Phase 3C: Recommendation Engine v1

Amaç:

Öğrenciye ilk faydalı öneriyi üretmek.

Önerilen module:

```text
student_planner/services/recommendation.py
```

v1 algoritması:

1. Programın latest curriculum'ını al.
2. Öğrencinin completed derslerini normalize et.
3. Required course'ları remaining/completed diye ayır.
4. Remaining required course'lar için prerequisite evaluator çalıştır.
5. Eligible dersleri hesapla.
6. Eğer offerings varsa target semester filtresi uygula.
7. Score hesapla:
   - recommended semester yakınlığı
   - unlock count
   - blocking criticality
   - prerequisite chain depth
   - required/elective önceliği
8. En iyi ders sepetini öner.

v1 output:

```text
available_required_courses
blocked_required_courses
top_unlock_courses
recommended_basket
warnings
```

Bu aşamada mükemmel schedule optimizer gerekmez. Önce doğru ve açıklanabilir
recommendation daha değerli.

### Phase 3D: CLI Prototype

Amaç:

UI yazmadan domain servislerini test etmek.

Örnek komut:

```powershell
python .\scripts\recommend_next_semester.py `
  --program CENG `
  --completed "MATH 119:DD,CENG 140:CC,PHYS 105:BB" `
  --target-semester 20252
```

Örnek çıktı:

```text
Eligible required courses:
- MATH 120
- CENG 213

Blocked required courses:
- CENG 384: missing MATH 219 and MATH 260

High unlock value:
- MATH 120 unlocks MATH 219 and EE 281
```

## Önümüzdeki Birkaç Adım İçin Net Plan

### Adım 1: Kalıcı audit script'i yaz

Bu audit sırasında manuel/in-line Python ile yapılan kontroller script'e
dönüştürülmeli.

Deliverable:

```text
scripts/audit_data_quality.py
data/processed/reports/data_quality_report.md
```

Bu, bundan sonraki tüm adımların güvenlik ağı olacak.

### Adım 2: Config ve encoding temizliği

Deliverable:

```text
config/engineering_programs.json
```

Türkçe adlar düzeltilmeli:

- `Havacılık ve Uzay Mühendisliği`
- `İnşaat Mühendisliği`
- `Gıda Mühendisliği`
- `Doğal Gaz`

Sonra:

```powershell
python .\scripts\load_programs.py
```

ile DB güncellenmeli.

### Adım 3: Course identity review report üret

Deliverable:

```text
data/processed/reports/course_identity_review.md
```

İçerik:

- Numeric subject code'lu course listesi
- NCC edge listesi
- Empty title listesi
- Course number > 999 listesi
- Önerilen alias/campus kararları

### Adım 4: Manual correction dosya yapısını kur

Deliverable:

```text
data/manual/corrections/course_aliases.json
data/manual/corrections/course_overrides.json
data/manual/corrections/prerequisite_overrides.json
```

Bu dosyalar başta boş olabilir ama schema'ları net olmalı.

### Adım 5: Offering scraper'ı yeni mimariye taşı

Bu adıma geçmeden önce SAIS client root script'ten ayrılmalı.

Deliverable:

```text
student_planner/sources/sais.py
scripts/scrape_offerings.py
scripts/load_offerings.py
```

### Adım 6: Prerequisite evaluator yaz

Bu, gerçek Phase 3'ün başlangıcı.

Deliverable:

```text
student_planner/services/prerequisite_evaluator.py
tests/test_prerequisite_evaluator.py
```

Testler olmadan bu engine yazılmamalı; çünkü küçük set/no grade hataları öğrenci
önerisini bozar.

## Kullanıma Hazırlık Kararı

Mevcut veri için karar:

| Katman | Teknik Hazır | Ürün Hazır | Not |
| --- | --- | --- | --- |
| Programs | Evet | Kısmen | Türkçe encoding bozuk |
| Courses | Evet | Kısmen | NCC/numeric subject normalization gerekli |
| Curricula | Evet | Kısmen | Review status scraped |
| Requirements | Evet | Kısmen | Elective pools unresolved |
| Prerequisite Graph | Evet | Kısmen | Set semantics/NCC review gerekli |
| Source Documents | Evet | Evet | Path/hash tutarlı |
| Offerings | Hayır | Hayır | Tablo boş |
| Student Data | Hayır | Hayır | Phase 3'te başlayacak |

Sonuç:

Elimizdeki veri graph exploration, internal prototype ve zorunlu ders bazlı ilk
hesaplamalar için iyi bir temel. Fakat öğrenciye güvenilir "önümüzdeki dönem şu
dersleri al" önerisi vermeden önce data hardening, offerings ve prerequisite
fulfillment engine tamamlanmalı.

## Önerilen İlk Implementation Task

Bir sonraki kodlama adımı olarak recommendation engine değil, data quality gate
yazılmalı.

Sebep:

- Mevcut verinin güçlü ve zayıf taraflarını sayısallaştırır.
- Sonraki scraper/refactor değişikliklerinde regression yakalar.
- Manual review sürecinin girdisini üretir.
- Projenin amatör CSV yığınına dönmesini engeller.

İlk task tanımı:

```text
Build scripts/audit_data_quality.py.

The script should inspect data/db/student_planner.sqlite and processed JSON/CSV
outputs, then write data/processed/reports/data_quality_report.md. It should
exit non-zero only for structural corruption and print warnings for review
items.
```

Bu tamamlandıktan sonra encoding/config temizliği ve course identity
normalization'a geçmek en sağlıklı yol olur.
