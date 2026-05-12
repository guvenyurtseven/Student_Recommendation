# Detailed Next Steps Plan

Last updated: 2026-05-11

Bu plan, mevcut projenin özünü koruyarak ilerlemek için yazıldı:

Öğrenciye bölümünü, aldığı dersleri ve planlamak istediği dönemi girdi olarak
aldırıp; müfredat, prerequisite ağı ve dönem açılma bilgisini birlikte kullanarak
akıllı ve açıklanabilir ders önerisi üretmek.

## Current Baseline

Tamamlanan güçlü temel:

- 13 aktif mühendislik lisans programı için latest curriculum scrape edildi.
- Bölüm dışı servis derslerini de kapsayan recursive prerequisite closure üretildi.
- Birleşik engineering prerequisite graph DAG olarak doğrulandı.
- Her bölüm için ayrı prerequisite graph üretildi.
- SQLite DB kuruldu ve load pipeline çalışıyor.
- Data quality audit scripti eklendi.
- Course identity review raporu eklendi.
- Manual correction dosya yapısı ve apply scripti eklendi.

Mevcut veri durumu:

- DB integrity: iyi.
- Foreign keys: iyi.
- Curriculum/prerequisite processed dosyaları: teknik olarak tutarlı.
- Review status: hâlâ `scraped`.
- Offerings: aktif planner DB hedef donem snapshot modeliyle calisacak sekilde
  guncellendi. Historical offering prediction product v1 icin kullanilmayacak.
  Hedef donem icin SAIS guncellendikten sonra tek seferlik scrape/load yapilacak.
- Student planning logic: deterministic CLI ve ilk recommendation pipeline tamamlandı.
- METU undergraduate registration policy layer eklendi:
  transcript'ten latest `CumGPA/GPA/STAN` okunuyor, probation kisitlari
  uygulanıyor, repeat-priority dersler one aliniyor ve scenario course-count cap
  resmi course-load kurallarina gore enforce ediliyor.

## 2026-05-11 Registration Policy Update

Resmi kaynak:

```text
https://oidb.metu.edu.tr/en/middle-east-technical-university-rules-and-regulations-governing-undergraduate-studies
```

Yeni policy katmani:

```text
student_planner/services/registration_policy.py
docs/registration_policy.md
```

Otomatik uygulananlar:

- Prerequisite minimumu: `DD` veya `S`; `EX`, exemption oldugu icin `S` gibi
  kabul edilir.
- Transcript metadata: son `CumGPA`, donem `GPA`, `STAN` ve ilgili semester no
  okunur.
- Probation: resmi guncel metne gore probation ogrenci yeni ders veya `W`
  aldigi dersi alamaz.
- Repeat priority: latest attempt `FF`, `FD`, `NA`, `U`, `W` ise ders senaryoda
  one alinir.
- Course-load cap: curriculum'daki en yogun donemden normal course load
  hesaplanir; CGPA'ya gore +0/+1/+2 course cap uygulanir.
- Minimum course load: non-probation senaryo 3 credit course altina duserse
  advisor/department approval veya graduation exception gerektigine dair warning
  uretilir.
- Engineering curriculum Turkish language requirement normalization: catalog'daki
  `TURK 105/201/303` ve `TURK 106/202/304` alternatif setleri product
  seviyesinde `Fall: TURK 303` ve `Spring: TURK 304` olarak normalize edilir.
  `TURK 303 -> TURK 304` prerequisite edge'i mevcut graph'tan kullanilir.

Onemli karar:

Kullanicinin bahsettigi "probation ama CGPA 1.70 ustuyse 3 yeni ders" kurali,
2026-05-11 tarihinde kontrol edilen resmi OIDB sayfasinda bulunmuyor. Bu yuzden
product v1 resmi sayfadaki daha kati kurali uygular: probation durumunda yeni
ders onerilmez.

Henuz tam machine-enforced olmayanlar:

- Advisor approval gerektiren exception'lar.
- Department-specific ek kriterler.
- Corequisite'in ayri bir "same-semester" constraint olarak modellenmesi.
- NI course planlamasi.
- Withdrawal planlamasi.
- Graduation exception'in kesin tespiti.

## 2026-05-11 Offering Strategy Update

Yeni urun karari:

- Dersin hedef donemde acilip acilmayacagi tahmin edilmeyecek.
- Her donem ders kayitlarindan 2-3 hafta once METU SAIS course offering listesi
  guncellendiginde manuel bir scrape tetiklenecek.
- Planner DB'deki `offerings` tablosu aktif hedef donemin authoritative snapshot'i
  olarak hazirlanacak.
- Historical processed offering dosyalari debug/provenance amaciyla kalabilir,
  fakat recommendation logic bunlardan fall/spring probability cikarmayacak.

Bu karar recommendation mimarisini sadelestirir:

- `curriculum` mezuniyet gereksinimini soyler.
- `prerequisite` dersin akademik olarak alinabilir olup olmadigini soyler.
- `offerings` sadece hedef donemde gercekten acilan dersleri soyler.
- `student record` ogrencinin bugunku durumunu soyler.

Operasyonel komut akisi:

```powershell
python .\scripts\scrape_offerings.py --semesters <TARGET_SEMESTER>
python .\scripts\load_offerings.py --semesters <TARGET_SEMESTER> --clear-existing --prune-orphan-non-undergraduate-courses
python .\scripts\generate_offering_coverage_report.py --semesters <TARGET_SEMESTER>
python .\scripts\audit_data_quality.py
python -m unittest discover -s tests -v
```

Default offering config artik:

```text
config/offering_departments.json
```

Bu config 13 aktif muhendislik bolumune ek olarak MATH, PHYS, CHEM, HIST,
TURK, ENG, OHS, IS, BA, ES, ECON ve BIOL gibi servis bolumlerini de kapsar.

Bu yüzden sıradaki hedef, recommendation engine yazmadan önce veri anlamını
sertleştirmek ve sonra domain servislerini katmanlı biçimde kurmak olmalı.

## Guiding Principles

### 1. Generated veriyi elle değiştirme

Generated dosyalar:

```text
data/processed/
data/db/student_planner.sqlite
```

Bu dosyalar elle düzeltilmemeli. Düzeltme gerekiyorsa:

```text
data/manual/corrections/
```

üzerinden uygulanmalı.

### 2. Curriculum, prerequisite, offering ayrı katmanlardır

Bu proje için en önemli mimari ayrım hâlâ bu:

- Curriculum: öğrencinin mezun olmak için tamamlaması gerekenler.
- Prerequisite: derslerin birbirine bağımlılığı.
- Offering: dersin hangi dönem açıldığı.
- Student record: öğrencinin neyi tamamladığı.

Recommendation ancak bu dört katman birlikte çalışınca anlamlı olur.

### 3. İlk ürün açıklanabilir olmalı

Sadece "şu dersleri al" demek yetmez. Öğrenci şunu da görebilmeli:

- Bu dersi neden alabiliyorum?
- Bu dersi neden alamıyorum?
- Bu ders hangi derslerin kilidini açıyor?
- Hangi prerequisite zinciri beni engelliyor?

### 4. Yanlış öneri vermemek, eksik öneri vermekten daha önemlidir

Özellikle elective pool, NCC ve unresolved derslerde sistem emin değilse bunu
açıkça söylemeli.

## Phase 2.5: Data Hardening

Bu fazın amacı, otomatik üretilmiş veriyi recommendation engine'e hazır hale
getirmektir.

### Phase 2.5A: Data Quality Gate

Durum: Tamamlandı.

Dosyalar:

```text
scripts/audit_data_quality.py
data/processed/reports/data_quality_report.md
```

Komut:

```powershell
python .\scripts\audit_data_quality.py
```

Bu script artık şu kontrolleri yapıyor:

- DB integrity
- Foreign key check
- Source hash check
- Curriculum JSON coverage
- Curriculum JSON/CSV/DB count consistency
- Prerequisite JSON/CSV/DB consistency
- DAG validation
- Empty title warning
- Numeric subject-code warning
- NCC edge warning
- Empty offerings/student table warning

Kabul kriteri:

- Fatal finding olmamalı.
- Warning'ler review queue olarak ele alınmalı.

### Phase 2.5B: Manual Correction Layer

Durum: İlk altyapı tamamlandı.

Dosyalar:

```text
data/manual/corrections/course_aliases.json
data/manual/corrections/course_overrides.json
data/manual/corrections/prerequisite_overrides.json
data/manual/corrections/curriculum_overrides.json
scripts/apply_manual_corrections.py
docs/manual_corrections.md
```

Komut:

```powershell
python .\scripts\apply_manual_corrections.py
```

Mevcut destek:

- `course_aliases`
- `course_overrides`

Reserved ama henüz uygulanmayan:

- `prerequisite_overrides`
- `curriculum_overrides`

Bir sonraki yapılacaklar:

1. Course identity review raporundaki numeric subject-code dersleri tek tek
   incelemek.
2. Sadece emin olunan alias kararlarını `course_aliases.json` dosyasına eklemek.
3. Boş title gibi metadata düzeltmelerini sadece authoritative kaynakla
   `course_overrides.json` içine eklemek.
4. Correction sonrası audit çalıştırmak.

Kabul kriteri:

- Correction script idempotent çalışmalı.
- Source snapshot/hash bozulmamalı.
- Audit fatal vermemeli.
- Her applied correction `manual_correction_log` içinde görünmeli.

### Phase 2.5C: Course Identity Normalization

Amaç:

Graph içinde görünen numeric subject-code ve NCC alternatiflerini ürün mantığına
uygun hale getirmek.

Sorun:

Şu anda bazı dersler şu şekilde görünüyor:

```text
355 140
357 119
374 321
```

Bunlar kullanıcıya doğrudan gösterildiğinde kafa karıştırır. Bazıları NCC
alternatifi, bazıları eski/eşdeğer ders olabilir.

Önerilen iş:

```text
student_planner/services/course_identity.py
```

Bu servis şunları sağlamalı:

- `resolve_course(input_code)`:
  Kullanıcı `CENG140`, `CENG 140`, `5710140` gibi farklı input girerse canonical
  course bulmalı.

- `display_for_student(course)`:
  Öğrenciye gösterilecek doğru display label üretmeli.

- `is_ncc_alternative(course_or_edge)`:
  NCC alternatifleri işaretlemeli.

- `aliases_for(course)`:
  Manual alias ve numeric code ilişkilerini döndürmeli.

DB tarafında gerekebilecek genişlemeler:

```text
courses.campus
courses.canonical_course_id
courses.identity_status
```

Bu alanları hemen eklemek zorunda değiliz. İlk aşamada `course_aliases` ve
service-level resolver yeterli olabilir.

Kabul kriteri:

- CENG örneğinde `CENG 140` ile ilişkili NCC alternatifleri ayırt edilebilmeli.
- Ankara curriculum course'ları recommendation'da öncelikli görünmeli.
- NCC alternatifleri silinmemeli, fakat etiketlenmeli.

### Phase 2.5D: Review Workflow

Amaç:

`scraped` veriyi program program `reviewed` hale getirecek pratik süreci kurmak.

Önerilen dosyalar:

```text
data/manual/reviews/curricula/CENG.review.md
data/manual/reviews/curricula/CE.review.md
data/manual/reviews/prerequisites/unresolved.review.md
data/manual/reviews/course_identity.review.md
```

Review checklist:

- Catalog curriculum latest mi?
- Zorunlu servis dersleri var mı?
- Course choice grupları doğru mu?
- Elective placeholders doğru sınıflanmış mı?
- Summer practice doğru temsil edilmiş mi?
- Unresolved prerequisite dersler açıklanmış mı?
- NCC alternatifleri yanlışlıkla Ankara zorunlu dersi gibi görünmüyor mu?

Kabul kriteri:

- En az CENG ve CE için pilot review tamamlanmalı.
- Review sonucu correction gerekiyorsa correction dosyasına işlenmeli.
- DB status update mekanizması tasarlanmalı.

## Phase 2.6: Offerings Layer

Amaç:

Next-semester recommendation için dersin hedef dönemde açılıp açılmadığını
bilmek.

Onceki durum:

```text
offerings: 0
```

Guncel durum:

```text
offerings: active target-semester snapshot in SQLite
default target in local smoke tests: 20252
scope: engineering programs plus high-impact service departments
20252 loaded offering rows: 654
20252 curriculum subjects without loaded offering coverage: 0
```

Bu katman personal recommendation için en kritik parçalardan biri olmaya devam
ediyor. Urun v1 icin hedef, historical pattern tahmini degil, her donem SAIS'ten
alinan guncel hedef donem snapshot'ini authoritative kabul etmektir.

### Phase 2.6A: SAIS Source Adapter

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/sources/sais.py
tests/test_sais_source.py
```

Bu adapter eski tek amacli scraper'lardaki login, form parsing, table parsing,
`env.local` okuma ve course-details app acma mantigini yeniden kullanilabilir
bir kaynak katmanina tasidi.

Mevcut durum:

SAIS login/form logic root scriptlerde:

```text
scrape_metu_program_courses.py
scrape_prerequisite_graph.py
```

Yeni hedef:

```text
student_planner/sources/sais.py
```

Taşınacak parçalar:

- `MetuSaisClient`
- form parser
- table parser
- env.local loader
- course details app opener
- department/semester/course list query helperları

Neden?

Prerequisite scraper, offerings scraper ve ileride başka SAIS kaynakları aynı
client'ı kullanmalı.

### Phase 2.6B: Offering Scraper

Durum: Ilk CLI tamamlandi.

Yeni script:

```text
scripts/scrape_offerings.py
```

Örnek komut:

```powershell
python .\scripts\scrape_offerings.py --semesters 20252
```

Çıktı:

```text
data/raw/sais/offerings/<semester>/<program>/...
data/processed/offerings/<semester>/<program>.offerings.json
data/processed/offerings/all_scraped_offerings.csv
```

Kapsam:

- 13 muhendislik programi
- Ortak servis bolumleri: MATH, PHYS, CHEM, HIST, TURK, ENG, OHS, IS, BA, ES,
  ECON, BIOL
- Tek hedef donem snapshot'i
- Course numeric code
- Display code
- Course title
- Department
- Semester
- Level/type

Tamamlanan dosyalar:

```text
scripts/scrape_offerings.py
```

Script `env.local` veya environment variable uzerinden `METU_USERNAME` ve
`METU_PASSWORD` okur. Her program/donem icin raw SAIS HTML snapshot'i,
processed offering JSON'u ve combined CSV uretir.

### Phase 2.6C: Offering Loader

Durum: Ilk CLI tamamlandi.

Yeni script:

```text
scripts/load_offerings.py
```

DB:

```text
offerings(course_id, semester_no, department_program_id, source_document_id)
```

Kabul kriteri:

- `offerings` boş kalmamalı.
- Aynı ders/dönem/program duplicate olmamalı.
- Source document hash kontrolü çalışmalı.
- Audit report offerings sayısını göstermeli.

Tamamlanan dosyalar:

```text
scripts/load_offerings.py
tests/test_load_offerings.py
```

Loader processed offering JSON dosyalarini SQLite `offerings` tablosuna
idempotent olarak yukler. Course eslemesini oncelikle numeric code ile yapar;
bu sayede SAIS display tahminleri mevcut canonical course kayitlarini bozmaz.

Son durum:

```powershell
python .\scripts\scrape_offerings.py --semesters <TARGET_SEMESTER>
python .\scripts\load_offerings.py --semesters <TARGET_SEMESTER> --clear-existing --prune-orphan-non-undergraduate-courses
```

Bu komutlarla aktif planner DB yalnizca hedef donem offering snapshot'i ile
hazirlanir. Processed klasorde eski snapshot'lar kalabilir, fakat loader
`--semesters` filtresiyle product DB'ye sadece hedef donemi alir.

### Phase 2.6C.5: Offering Coverage Report

Durum: Ilk rapor tamamlandi.

Tamamlanan dosyalar:

```text
scripts/generate_offering_coverage_report.py
data/processed/reports/offering_coverage_report.md
data/processed/reports/offering_missing_curriculum_courses.csv
```

Raporun guncel ozeti hedef donem filtresiyle uretilmelidir:

```text
python .\scripts\generate_offering_coverage_report.py --semesters <TARGET_SEMESTER>
```

Bu rapor, recommendation output'undaki `offering_coverage_unknown`
uyarilarinin kaynagini veri seviyesinde gosterir.

### Phase 2.6D: Historical Offering Signal

Durum: Product v1 icin ertelendi / deprecated.

Gerekce:

METU SAIS, donem baslamadan once hedef donemin gercek acilan ders listesini
guncelliyor. Ogrenciye akademik tavsiye verirken pattern tahmini yapmak yerine
bu authoritative snapshot'i kullanmak daha guvenli.

Bu yuzden su sinyaller product v1 icin hesaplanmayacak:

```text
fall_probability
spring_probability
summer_probability
last_offered_semester
```

Bu sinyaller ileride sadece analitik veya uzun vadeli planlama icin geri
getirilebilir; next-semester recommendation icin karar verici olmayacak.

## Phase 3: Student Planning Logic

Bu faz ürünün kalbidir.

Input:

- Program
- Completed courses
- Grades
- Optional in-progress courses
- Target semester

Output:

- Remaining requirements
- Eligible courses
- Blocked courses
- Missing prerequisites
- Unlock value
- Recommendation basket

### Phase 3A: Repository Layer

Amaç:

Domain servisleri doğrudan SQL yazmasın.

Önerilen dosyalar:

```text
student_planner/repositories/sqlite.py
student_planner/repositories/courses.py
student_planner/repositories/curricula.py
student_planner/repositories/prerequisites.py
student_planner/repositories/offerings.py
```

İlk sade yaklaşım:

- Tek `SQLiteRepository` ile başlanabilir.
- Sonra büyüdükçe split edilebilir.

Kabul kriteri:

- Program latest curriculum çekilebilmeli.
- Course lookup yapılabilmeli.
- Prerequisite edges course bazında alınabilmeli.
- Offering lookup yapılabilmeli.

### Phase 3B: Grade Model

Durum: İlk domain modeli ve unit testleri tamamlandı.

Dosyalar:

```text
student_planner/domain/grades.py
tests/test_grades.py
docs/grade_model.md
```

Amaç:

Prerequisite min grade karşılaştırmasını doğru yapmak.

Önerilen dosya:

```text
student_planner/domain/grades.py
```

Desteklenecek notlar:

```text
AA BA BB CB CC DC DD FD FF
S U W NA EX
```

Kararlar:

- `DD` minimum ise `DD` ve üstü geçer.
- `S` başarıdır.
- `U` başarısızdır, ama explicit `U` minimumunu sağlar; SAIS bazı S/U
  prerequisite satırlarında bunu kullanıyor.
- `W` withdraw'dır ve prerequisite sağlamaz.
- `NA` pratikte `FF` gibi ele alınır.
- `EX` pratikte `S` gibi ele alınır.
- In-progress dersleri v1'de tamamlandı saymamak daha güvenli.

Kabul kriteri:

- Grade comparison unit testleri olmalı. Bu kriter ilk versiyon için sağlandı.

### Phase 3C: Prerequisite Evaluator

Durum: İlk saf service ve unit testleri tamamlandı.

Dosyalar:

```text
student_planner/services/prerequisite_evaluator.py
tests/test_prerequisite_evaluator.py
docs/prerequisite_evaluator.md
student_planner/repositories/sqlite.py
tests/test_sqlite_repository.py
```

Önerilen dosya:

```text
student_planner/services/prerequisite_evaluator.py
```

Temel soru:

```text
Bu öğrenci bu dersi alabilir mi?
```

Data modeli:

```text
PrerequisiteSet:
  set_no
  required_courses
  min_grades

EligibilityResult:
  target_course
  is_eligible
  satisfied_sets
  missing_by_set
  explanation
```

Varsayım:

- Aynı `set_no` içindeki dersler AND.
- Farklı `set_no` grupları OR.

Bu varsayım gerçek SAIS örnekleriyle test edilmeli.

Test örnekleri:

- `MATH 119 -> MATH 120`
- `MATH 120 -> MATH 219`
- `MATH 219 + MATH 260 -> CENG 384`
- `CENG 140 -> CENG 213`
- HIST S/U zinciri
- NCC alternatif set örneği

Kabul kriteri:

- Bir target course için neden açık/kapalı olduğu açıklanmalı. İlk versiyonda
  sağlandı.
- Eksik dersler set bazında gösterilmeli. İlk versiyonda sağlandı.
- Alias resolver ile completed course eşleştirmesi yapılmalı. İlk versiyonda
  mapping tabanlı alias desteği sağlandı.

Sonraki iş:

- Bu saf service'i DB/repository katmanından gelen gerçek prerequisite edge'leri
  ile beslemek. İlk SQLite repository bağlantısı tamamlandı.
- Manual `course_aliases` tablosunu alias map olarak kullanmak. İlk destek
  tamamlandı.
- Daha fazla gerçek SAIS örneğiyle set semantics'i review etmek.

Ek retake kuralı:

- Bir ders birden fazla kez alınmışsa latest attempt kullanılır.
- Latest attempt için öncelik sırası `attempt_order`, `completed_semester_no`,
  sonra input sırasıdır.
- Prerequisite evaluator sadece target course'un direct prerequisite setlerini
  kontrol eder; transitive prerequisite zinciri yeniden doğrulanmaz. Örneğin
  `MATH 219` için `MATH 120` sağlanıyorsa, daha sonra başarısız alınan `MATH 119`
  `MATH 219` eligibility sonucunu bozmaz.

### Phase 3D: Curriculum Progress

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/domain/planning.py
student_planner/services/curriculum_progress.py
tests/test_planning_models.py
tests/test_curriculum_progress.py
```

Repository destegi:

```text
SQLiteStudentPlannerRepository.fetch_latest_curriculum(program_abbr)
```

Bu adimda sistem ilk kez ogrencinin completed course listesini latest curriculum
snapshot'i ile karsilastirabiliyor. Servis simdilik bilincli olarak sadece
curriculum progress hesapliyor; prerequisite eligibility, offering availability
ve recommendation scoring bu servise karistirilmadi.

Önerilen dosya:

```text
student_planner/services/curriculum_progress.py
```

Soru:

```text
Öğrenci müfredatta nerede?
```

Çıktılar:

- Completed required courses
- Remaining required courses
- Completed course choice requirements
- Unsatisfied course choice requirements
- Elective placeholder summary
- Recommended semester lag/ahead signal

İlk versiyon:

- Zorunlu dersler ve course choice grupları hesaplansın.
- Elective pool'lar "needs elective pool logic" olarak işaretlensin.

Kabul kriteri:

- CENG için completed listesi verilince kalan zorunlu dersler doğru çıkmalı.

Ilk unit testlerde required course, course choice, latest attempt ve
review-only elective placeholder davranisi dogrulandi.

Candidate course generator durumu: Tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/candidate_courses.py
tests/test_candidate_courses.py
```

Repository destegi:

```text
SQLiteStudentPlannerRepository.fetch_prerequisite_edges_for_courses(course_codes)
```

Bu katman curriculum progress sonucundaki remaining concrete course listesini
prerequisite evaluator ile birlestirir ve aday dersleri `eligible` / `blocked`
olarak ayirir. Henuz ranking, workload optimization veya offering filtresi
yapmaz.

Ek cleanup:

- Kok dizindeki eski deneysel CSV dosyalari silindi. Guncel source of truth
  `data/raw`, `data/processed` ve `data/db/student_planner.sqlite` katmanlaridir.

Sonraki is:

- Candidate sonucuna unlock analysis ve daha sonra difficulty/recommendation
  scoring eklenmeli.

### Phase 3E: Unlock Analysis

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/unlock_analysis.py
tests/test_unlock_analysis.py
```

Repository destegi:

```text
SQLiteStudentPlannerRepository.fetch_all_prerequisite_edges()
```

Bu katman graph yonunu `prerequisite -> course` olarak kullanir ve aday dersler
icin downstream dependency potansiyelini hesaplar. Cikti su metrikleri icerir:

- Direct unlock course listesi/count
- Transitive unlock course listesi/count
- Curriculum-relevant unlock course listesi/count
- Longest unlock chain length
- Basit critical path score

Onemli semantik not:

- Bu servis "ders kesin acilir" karari vermez.
- Bir dependent course baska prerequisite'ler de isteyebilir.
- Kesin eligibility Candidate Course Generator / Prerequisite Evaluator
  tarafindan hesaplanir.

Gercek DB kontrolunde CENG orneginde `MATH 120` yuksek unlock skoruyla one
cikmistir; bu beklenen servis dersi zinciri davranisidir.

Önerilen dosya:

```text
student_planner/services/unlock_analysis.py
```

Soru:

```text
Bu dersi almak gelecekte hangi dersleri açar?
```

Metrikler:

- Direct unlock count
- Transitive unlock count
- Curriculum-relevant unlock count
- Blocking chain depth
- Critical path contribution

Kabul kriteri:

- `MATH 120` gibi servis derslerinin yüksek etkisi görülebilmeli.
- Sadece graph node sayısı değil, öğrencinin curriculum'ına relevant dersler de
  hesaba katılmalı.

Ilk unit testlerde direct/transitive/curriculum-relevant unlock, alias
normalizasyonu ve ranking davranisi dogrulandi.

Sonraki is:

- Unlock skorunu ECTS, recommended semester ve difficulty preference ile
  birlestiren load/difficulty scoring katmani yazilmali.

### Phase 3E.5: Load and Difficulty Scoring

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/difficulty.py
tests/test_difficulty.py
```

Bu katman recommendation engine'den once aday derslere sayisal sinyaller ekler.
Henuz ders sepeti olusturmaz; sadece ders bazli skor uretir.

Urettigi ana modeller:

```text
SemesterLoadTarget
CourseLoadScore
CourseScoringResult
CourseScoringService
```

Hesaplanan sinyaller:

- `difficulty_score`: ECTS, course level ve major-course sinyalinden tureyen
  yaklasik ders yuku.
- `priority_score`: unlock score, recommended semester alignment ve ogrencinin
  `easy` / `balanced` / `hard` tercihini birlestiren oncelik skoru.
- `SemesterLoadTarget`: hedef zorluk tercihine gore min/target/max ECTS araligi.

Varsayilan load target'lari:

```text
easy:     18 / 21 / 24 ECTS
balanced: 26 / 30 / 34 ECTS
hard:     32 / 36 / 42 ECTS
```

Ogrenci input'unda `min_ects`, `target_ects` veya `max_ects` verilirse bu
varsayilanlar override edilir.

Onemli semantik notlar:

- Bu servis tek basina final tavsiye uretmez.
- `priority_score`, recommendation basket builder icin siralama sinyalidir.
- ECTS bilgisi eksikse ders bazinda gecici olarak `5.0` varsayilir ve rationale
  icinde belirtilir.
- METU semester suffix'i ilk versiyonda su sekilde yorumlanir:
  `1 = fall`, `2 = spring`, `3 = summer`.

Gercek DB kontrolunde CENG orneginde:

- `easy` tercihinde dusuk yuklu dersler daha yukari cikti.
- `balanced` ve `hard` tercihlerinde unlock etkisi yuksek dersler daha baskin
  hale geldi.
- `MATH 120`, servis prerequisite zinciri etkisi nedeniyle her modda ust sirada
  kaldi.

Sonraki is:

- Bu ders bazli skorlardan kolay/dengeli/agresif ders sepeti senaryolari ureten
  Recommendation v1 katmani yazilmali.

### Phase 3F: Recommendation v1

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/recommendation.py
tests/test_recommendation.py
```

Bu katman `CourseScoringResult` girdisini alir ve ders bazli skorlardan uc
senaryo uretir:

```text
Easy Load
Balanced Progress
Aggressive Progress
```

Urettigi ana modeller:

```text
ScenarioConfig
RecommendationResult
RecommendationService
```

Senaryo davranisi:

- Easy Load: dusuk zorluk/yuk oncelikli siralama kullanir.
- Balanced Progress: `priority_score` merkezli dengeli siralama kullanir.
- Aggressive Progress: unlock etkisini daha one alan siralama kullanir.
- Her senaryo ECTS cap'e uymaya calisir.
- Eger eligible ders yoksa sessizce bos tavsiye vermek yerine warning uretir.
- Eger senaryo minimum yuk hedefinin altinda kalirsa warning uretir.

Onemli semantik notlar:

- Bu servis DB, scraper, prerequisite evaluation veya unlock calculation yapmaz.
- Input olarak yalnizca daha once hesaplanmis eligible course score'larini alir.
- Bu standalone recommendation servisi tek basina offering sorgusu yapmaz.
  Pipeline seviyesinde Phase 3H ile offering-aware filtre eklenmistir.
- Haftalik ders programi optimizasyonu bu katmanda yoktur ve product v1
  kapsamindan cikarilmistir.
- En yuksek unlock sinyaline sahip kritik baglayici dersler ECTS cap icinde
  kaldiklari surece tum senaryolara once yerlestirilir. Bu sayede kolay/dengeli/
  zor tercihinden bagimsiz olarak bir sonraki ders zincirlerini acan dersler
  geri plana itilmez.

Gercek DB smoke testinde CENG ornegi icin progress -> candidates -> unlock ->
scoring -> recommendation zinciri uc senaryo uretti.

Önerilen dosya:

```text
student_planner/services/recommendation.py
```

İlk algoritma:

1. Program curriculum'ını al.
2. Completed courses normalize et.
3. Remaining required courses bul.
4. Her course için prerequisite eligibility hesapla.
5. Target semester offering filtresi uygula; coverage yoksa uyarı üret ve tahmin
   yapma.
6. Score hesapla:
   - prerequisite eligible
   - recommended semester yakınlığı
   - unlock value
   - required course priority
   - offering availability
   - not overloading same chain
7. Öneri sepeti üret.

v1 kapsam dışı:

- Section/saat planlama
- Öğrencinin kişisel tercihleri
- Mezuniyet optimizasyonu

Kabul kriteri:

- Öneri açıklanabilir olmalı.
- Sistem emin olmadığı elective pool alanlarında yanlış öneri vermemeli.
- Blocked dersler missing prerequisite açıklamasıyla gelmeli.

Ilk unit testlerde uc senaryo uretimi, ECTS cap davranisi, preferred scenario
secimi, bos input warning'i ve rationale tasinmasi dogrulandi.

Sonraki is:

- Bu pipeline'i kullanici input'u ile calistiracak CLI prototype yazilmali.
- CLI, JSON input alip PlanningReport benzeri deterministik cikti uretmeli.
- Target semester icin offering coverage yoksa CLI ciktisinda availability
  uyarisi acikca yer almali.

### Phase 3G: CLI Prototype

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/planning_io.py
student_planner/services/planning_pipeline.py
scripts/recommend_next_semester.py
examples/students/ceng_sample_planning_input.json
tests/test_planning_io.py
tests/test_planning_pipeline.py
```

Bu adimda kullanici input'u ile tum deterministic pipeline'i calistiran ince bir
CLI kabugu eklendi. CLI'nin icine akademik karar mantigi gomulmedi; CLI sadece
JSON input okur, `SemesterPlanningPipeline` servisini cagirir ve JSON report
uretir.

Pipeline sirasi:

```text
StudentPlanningInput JSON
-> latest curriculum
-> curriculum progress
-> candidate course generation
-> unlock analysis
-> load/difficulty scoring
-> recommendation scenarios
-> PlanningReport JSON
```

CLI komutu:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json
```

Opsiyonel dosyaya yazma:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json `
  --output .\data\processed\reports\ceng_sample_recommendation.json
```

Input JSON formati:

```json
{
  "program_abbr": "CENG",
  "completed_courses": [
    {"course_code": "MATH 119", "grade": "DD"}
  ],
  "goal": {
    "target_semester_no": "20252",
    "difficulty_preference": "balanced"
  }
}
```

Output su bolumleri icerir:

- Curriculum progress
- Eligible courses
- Blocked courses
- Easy / Balanced / Aggressive scenarios
- Warnings
- Metadata

Offerings tablosu tamamen bossa CLI output'u `offerings_unavailable` warning'i
uretir. Offering verisi varsa ama target semester kapsanmiyorsa
`target_semester_offerings_unavailable` warning'i uretir.

Smoke test sonucu:

```text
program=CENG scenarios=3 preferred=balanced
easy 26.0 ECTS
balanced 31.5 ECTS
aggressive 33.5 ECTS
```

Önerilen script:

```text
scripts/recommend_next_semester.py
```

Örnek:

```powershell
python .\scripts\recommend_next_semester.py `
  --program CENG `
  --completed "MATH 119:DD,CENG 140:CC,PHYS 105:BB" `
  --target-semester 20252
```

Çıktı:

```text
Eligible required courses
Blocked required courses
Recommended basket
Warnings
```

Bu UI'dan önce domain servislerinin doğru çalıştığını kanıtlayacak.

### Phase 3H: Offering-Aware Recommendation Pool

Durum: Ilk altyapi tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/services/offering_availability.py
student_planner/repositories/sqlite.py
student_planner/services/planning_pipeline.py
tests/test_offering_availability.py
tests/test_planning_pipeline.py
```

Bu adim recommendation pipeline'ina conservative offering filtresi ekledi.
Davranis:

- `offerings` tamamen bossa eski davranis korunur ve `offerings_unavailable`
  warning'i uretir.
- Target semester icin offering kaydi varsa repository offered course code ve
  covered subject code listelerini dondurur.
- Bir subject icin coverage varsa ve ders o donem offering listesinde yoksa,
  ders recommendation scenario havuzundan cikarilir.
- Bir subject icin coverage yoksa ders yanlis negatif uretmemek icin havuzda
  kalir; `offering_coverage_unknown` warning'i uretilebilir.

Bu tasarim su nedenle onemli: henuz MATH/PHYS/CHEM gibi servis bolumlerinin
offering kaynaklari tam yuklenmemis olabilir. Sistem sadece emin oldugu
durumlarda "bu ders hedef donemde acilmiyor" karari verir.

### Phase 3I: Elective Intent and Placeholder Planning

Durum: Ilk product-grade akış tamamlandi.

Tamamlanan dosyalar:

```text
student_planner/domain/electives.py
student_planner/domain/planning.py
student_planner/services/planning_io.py
student_planner/services/elective_candidates.py
student_planner/services/elective_requirements.py
student_planner/services/planning_pipeline.py
student_planner/services/recommendation.py
student_planner/repositories/sqlite.py
tests/test_electives.py
tests/test_elective_candidates.py
tests/test_elective_requirements.py
tests/test_planning_io.py
tests/test_planning_models.py
tests/test_planning_pipeline.py
tests/test_recommendation.py
```

Problem:

Mufredatlarda technical elective, restricted elective, non-technical elective ve
free elective gereksinimleri var; fakat bu gereksinimler tek bir concrete course
gibi davranmiyor. Ogrenci bazen hangi elective dersi alacagini bilir, bazen
sadece "bu donem bir technical elective almak istiyorum" der. Sistem iki durumu
da desteklemeli.

Urun kararlari:

- Elective zorluk sirasi:
  `technical_elective > restricted_elective > nontechnical_elective > free_elective`.
- Varsayilan ECTS tahminleri:
  `technical_elective=6.5`, `restricted_elective=6.0`,
  `nontechnical_elective=5.5`, `free_elective=5.0`.
- Ogrenci explicit course code verirse, ornegin `CENG 495`, sistem once DB'deki
  course/curriculum/offering bilgisinden ECTS bulmaya calismali.
- Explicit course DB'de yoksa veya ECTS bilinmiyorsa kategori varsayilani
  kullanilmali.
- Ogrenci kategori secip course code vermezse, sistem course set onerisi
  uretebilir; fakat exact elective validation icin somut ders secimi gerekir.
  Bu durumda output'ta `needs_course_selection` uyarisi olmalidir.
- Birden fazla elective kategorisi ayni semester hedefinde secilebilir.

Input contract:

```json
{
  "elective_intents": [
    {"category": "technical_elective", "course_code": "CENG 495"},
    {"category": "restricted_elective"},
    {"category": "free_elective"}
  ]
}
```

Alternatif UI mapping'i ileride checkbox temelli olabilir:

```json
{
  "elective_preferences": {
    "technical_elective": {"wants_to_take": true, "course_code": "CENG 495"},
    "nontechnical_elective": {"wants_to_take": true}
  }
}
```

Implementation sirasi:

1. `ElectiveCategory` ve `ElectiveIntent` domain modellerini ekle. Tamamlandi.
2. Planning input JSON parser'ina `elective_intents` desteği ekle. Tamamlandi.
3. Kategori zorluk rank'i ve varsayilan ECTS tahminlerini merkezi bir yerde
   tanimla. Tamamlandi.
4. Recommendation pipeline'a elective placeholder candidate uretecek ayri bir
   servis ekle. Tamamlandi.
5. Explicit course code varsa DB'den course ECTS lookup yap; yoksa kategori
   varsayilanini kullan. Ilk versiyon tamamlandi; DB lookup su an curriculum
   requirement ECTS kayitlarindan besleniyor.
6. Explicit course code hedef donem offering snapshot'inda yoksa known
   not-offered uyarisi uret. Tamamlandi; explicit elective normal offering
   filtresinden gecer.
7. Course code verilmeyen elective intent'ler icin scenario'lara placeholder
   course recommendation ekle:
   `TECHNICAL_ELECTIVE`, `RESTRICTED_ELECTIVE`, `NONTECHNICAL_ELECTIVE`,
   `FREE_ELECTIVE`. Tamamlandi.
8. Scenario rationale icinde elective placeholder'in neden secildigini,
   varsayilan ECTS kullanildigini ve exact validation icin course selection
   gerektigini acikla. Tamamlandi.
9. Elective intent'leri curriculum'daki remaining elective slot'larla sayisal
   olarak eslestir. Tamamlandi.
10. Kategori bazinda remaining/requested/matched/unplanned/extra sayilarini
    report metadata'sina ekle. Tamamlandi.

Mevcut davranis:

- Curriculum progress icindeki elective pool requirement'lari kategori bazinda
  slot olarak okunur.
- Report metadata su alanlari uretir:
  `elective_remaining_slots_by_category`,
  `elective_requested_counts_by_category`,
  `elective_matched_counts_by_category`,
  `elective_unplanned_counts_by_category`,
  `elective_extra_counts_by_category`.
- User-requested elective item'lar ECTS cap'e sigdigi surece her scenario'ya
  oncelikli olarak dahil edilir.
- Explicit elective course, prerequisite kaydi varsa prerequisite evaluator'dan
  gecer.
- Explicit elective course, hedef donemde offering snapshot'inda yoksa normal
  `target_semester_not_offered` mekanizmasi ile scenario havuzundan cikarilir.
- Category-only elective intent placeholder olarak scenario'ya girer ve
  `elective_course_selection_required` uyarisi uretir.
- Placeholder recommendation output'unda `is_placeholder=true` ve
  `requires_explicit_course_selection=true` olarak serilestirilir.
- Explicit elective course selection'lari simdilik ogrencinin sectigi kategoriye
  guvenerek islenir; official elective pool list validation henuz olmadigi icin
  `explicit_elective_category_requires_review` info warning'i uretilebilir.
- Kategori icin curriculum slot yoksa veya istenen elective sayisi gorunen slot
  sayisini asarsa info warning uretir. Kalan ama bu donem planlanmayan elective
  slotlari warning degil, metadata olarak tasinir.

Difficulty model:

- Technical elective en yuksek category difficulty multiplier'i alir.
- Restricted elective technical elective'e yakin ama biraz daha dusuk kabul
  edilir.
- Non-technical elective orta/dusuk yuk kabul edilir.
- Free elective en esnek ve en dusuk varsayilan yuk kabul edilir.
- Bu rank nihai akademik zorluk degildir; sadece ders belli degilken kullanılan
  planlama tahminidir.

Output semantigi:

- Course code bilinen elective, normal course gibi scenario'da gorunur.
- Course code bilinmeyen elective, placeholder olarak gorunur.
- Placeholder'li scenario semester course set olarak gecerlidir.
- Placeholder'li scenario exact elective validation icin incomplete kabul edilir.
- LLM rapor katmani bu farki aciklamali; kesin ders secilmemis placeholder'i
  gercek ders gibi anlatmamalidir.

Kabul kriterleri:

- Input parser elective intent'leri normalize etmeli.
- Bilinmeyen kategori reddedilmeli.
- Course code varsa `CENG495` -> `CENG 495` normalize edilmeli.
- Course code yoksa intent gecersiz sayilmamali.
- Default ECTS ve difficulty rank testlenmeli.
- Planner output'u elective placeholder nedeniyle course selection warning'i
  verebilmeli.
- Elective intent'ler curriculum slotlariyla kategori bazinda eslesmeli.
- Fazla/slot disi elective intent'ler info warning uretmeli.

Hala bilincli olarak ertelenenler:

- Official technical/restricted/nontechnical elective pool list scraping.
- Tamamlanmis elective derslerinin transcript uzerinden kategoriye otomatik
  yazilmasi.
- Bir explicit elective course'un hangi kategoriye kesin sayildigini official
  kaynakla dogrulama.
- Haftalik ders programi entegrasyonu product v1 kapsamindan cikarildi.

### Phase 3J: Student-Readable Deterministic Report

Durum: Ilk Markdown rapor altyapisi tamamlandi.

Amaç:

JSON planning report makine tarafı için iyi, fakat öğrenci ve ileride LLM rapor
katmani icin okunabilir deterministic bir ara çıktı gerekiyor. Bu katman
akademik karar vermez; sadece `PlanningReport` sonucunu okunabilir biçime
dönüştürür.

Tamamlanan dosyalar:

```text
student_planner/services/planning_report_markdown.py
student_planner/services/planning_io.py
scripts/recommend_next_semester.py
tests/test_planning_io.py
data/processed/reports/ceng_sample_recommendation.md
```

CLI:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json `
  --format markdown `
  --output .\data\processed\reports\ceng_sample_recommendation.md
```

Rapor bolumleri:

- Summary
- Elective Fit
- Recommendation Scenarios
- Scenario-level course tables
- Grouped warnings
- Blocked courses
- Curriculum progress snapshot

Onemli semantik:

- Placeholder elective varsa exact elective validation incomplete olur.
- Warning'ler ayni mesaj tekrarlarini sayacla gruplanmis halde gosterilir.
- Markdown rapor, LLM'e verilecek sanitize deterministic input olarak
  kullanilabilir; LLM akademik kural uretmemeli, bu raporu yorumlamalidir.

### Phase 3K: LLM Narrative Report Layer

Durum: Ilk handoff altyapisi tamamlandi, fakat product v1 icin rafa kaldirildi.

Amac:

Deterministic planner ogrencinin akademik durumunu, alinabilir dersleri,
blocked dersleri, elective placeholder durumunu, ECTS yukunu ve onerilen
senaryolari hesaplar. LLM bu kararlari degistirmeden ogrenciye okunabilir,
destekleyici ve kisisellestirilmis bir rapora cevirir.

Bu fazdaki ana mimari karar:

```text
planner karar verir
LLM anlatir
```

LLM'in akademik source of truth olmasina izin verilmemelidir.

2026-05-11 karari:

- Bu ozellik simdilik aktif product roadmap'te zorunlu degil.
- Gelistirilen preprompt, handoff package ve testler silinmeyecek.
- Default urun akisi LLM maliyetine bagli olmayacak.
- Ogrenciye gosterilecek ana rapor deterministik Markdown/template rapor olacak.
- LLM anlatimi ileride opsiyonel, kullanici/API-key destekli veya premium bir
  ozellik olarak geri getirilebilir.

Tamamlanan dosyalar:

```text
prompts/student_planner_report_preprompt.md
student_planner/services/llm_report_package.py
student_planner/services/planning_io.py
scripts/recommend_next_semester.py
tests/test_llm_report_package.py
```

CLI:

```powershell
python .\scripts\recommend_next_semester.py `
  --input .\examples\students\ceng_sample_planning_input.json `
  --format llm-package `
  --output .\data\processed\reports\ceng_sample_llm_package.json
```

Uretilen paket sunlari icerir:

- `system_prompt`: versiyonlanmis preprompt.
- `deterministic_report_markdown`: LLM'in tek bilgi kaynagi.
- `response_contract`: cikti Markdown, Turkce ve belirli bolumlerden olusmali.
- `model_policy`: onerilen model sinifi, reasoning, verbosity, fallback ve cache
  stratejisi.
- `safety_contract`: LLM'in yapabilecekleri ve kesinlikle yapmamasi gerekenler.
- `metadata`: program, target semester, warning count, placeholder elective count
  ve hash alanlari.

Preprompt sozlesmesi:

- LLM yeni ders uyduramaz.
- Prerequisite, grade, ECTS, offering ve scenario kararlarini degistiremez.
- Placeholder elective'i concrete course gibi anlatamaz.
- Offering coverage unknown ise kesinlik iddia edemez.
- Exact elective validation icin concrete elective secimi gerekiyorsa bunu acik
  soyler.
- Kullanici credential'i istemez veya gostermeye calismaz.

Model kullanim stratejisi:

- Product v1 icin default: mini sinif, dusuk gecikmeli ve dusuk maliyetli bir
  model. Mevcut resmi OpenAI dokumanlarinda bu is yuku icin `gpt-5.4-mini`
  baslangic modeli olarak anlamli gorunuyor.
- `gpt-5-mini` daha dusuk maliyetli fallback olabilir.
- `gpt-5.5` gibi daha buyuk model sadece offline eval, kalite kontrol,
  prompt tuning veya premium/manuel review akisi icin kullanilmali.
- Responses API kullanilmali.
- Baslangic ayari: `reasoning_effort=low`, `text_verbosity=medium`,
  `temperature=0.2`, cikti limiti yaklasik 1200-1600 token.
- Model slug'i production'a cikarken config/env uzerinden pinlenmeli; kodun icine
  akademik davranisla birlikte gomulmemeli.

Peak trafik stratejisi:

10.000 kisinin ayni anda kullandigi senaryoda LLM cagrisi synchronous zorunlu bir
adim olmamali.

Onerilen runtime akis:

```text
POST /recommendations
  -> deterministic report hemen uret
  -> deterministic markdown'i kullaniciya hemen goster
  -> llm report job queue'ya ekle
  -> cache key = prompt_version + prompt_hash + report_hash + locale + model
  -> frontend job status poll eder veya webhook/SSE ile sonucu alir
```

Bu sayede:

- LLM gecikirse urun tamamen durmaz.
- Rate limit veya maliyet baskisinda deterministic fallback hazirdir.
- Ayni input/prompt icin cache kullanilabilir.
- Peak donemlerde kuyruk ve concurrency kontrollu sekilde yurutulur.

Batch API:

- Kullanici ekraninda anlik rapor icin uygun degil, cunku 24 saate kadar
  asenkron turnaround kabul ediyor.
- Offline eval setleri, prompt regression testleri ve toplu kalite analizleri
  icin uygundur.

Flex processing:

- Dusuk oncelikli, asenkron ve gecikmeye toleransli rapor/analiz islerinde
  degerlendirilebilir.
- Realtime kullanici istegi icin default olmamali; resource unavailable durumunda
  standart isleme geri donus stratejisi gerekir.

Park edilen gelecek implementation adimlari:

1. `LLMReportGateway` interface'i tasarla.
2. `OpenAIResponsesLLMReportGateway` adapter'ini ekle.
3. API key'i sadece backend environment/secret manager'da tut.
4. LLM response'u cacheleyen tablo veya store ekle:
   `llm_report_cache(report_hash, prompt_version, model, locale, content, created_at)`.
5. Queue worker ekle:
   `llm_report_jobs(id, status, payload_hash, attempts, error, created_at, completed_at)`.
6. Deterministic fallback'i product UX'in birinci sinif vatandasi yap.
7. En az 20-30 representative student report ile LLM eval seti olustur.
8. Evals gecmeden LLM'in uretecegi metni akademik tavsiye olarak guvenilir kabul etme.

### Phase 3L: Transcript PDF Input and Privacy-Preserving Extraction

Durum: Ilk parser/CLI altyapisi tamamlandi.

Amac:

Baslangicta planner input'u JSON olarak tasarlandi. Bu, domain logic'i hizli
gelistirmek icin dogruydu; fakat son urunde ogrenci transcript PDF yukleyebilmeli.
Sistem bu PDF'ten yalnizca planner icin gereken akademik gecmisi cikarmali ve
transcript PDF'i ya da raw transcript text'i database'te, dosya sisteminde veya
loglarda saklamamalidir.

Ana gizlilik karari:

```text
PDF girer -> text memory'de okunur -> minimal planner input cikar -> raw PDF/text yok edilir
```

Kalici olarak tutulabilecek veri:

- course code
- grade
- completed semester
- attempt order
- credits / ECTS varsa
- in-progress course code ve semester
- parse istatistikleri

Kalici olarak tutulmamasi gereken veri:

- transcript PDF dosyasi
- raw extracted transcript text
- ogrenci numarasi, TC/passport, isim-soyisim gibi kimlik alanlari
- transcript line dump'lari
- PDF metadata
- debug loglarda raw transcript icerigi

Tamamlanan dosyalar:

```text
student_planner/services/transcript_ingestion.py
scripts/extract_transcript_planning_input.py
tests/test_transcript_ingestion.py
examples/students/ceng_sample_transcript_text.txt
.gitignore
```

CLI:

```powershell
python .\scripts\extract_transcript_planning_input.py `
  --transcript-text .\examples\students\ceng_sample_transcript_text.txt `
  --program CENG `
  --target-semester 20252 `
  --output .\data\processed\reports\ceng_sample_from_transcript_input.json
```

PDF icin:

```powershell
python .\scripts\extract_transcript_planning_input.py `
  --transcript-pdf .\data\uploads\my_transcript.pdf `
  --program CENG `
  --target-semester 20252 `
  --output .\data\processed\reports\student_planning_input.json
```

PDF extraction optional `pypdf` paketine baglidir. Paket yoksa CLI raw PDF'i
saklamadan acik hata verir. Local testlerde `--transcript-text` kullanilabilir.

Mevcut parser davranisi:

- Transcript PDF icindeki department/program alanindan program abbreviation
  tespit etmeye calisir. Ornek: `Computer Engineering` -> `CENG`.
- Semester header'larini `2024-2025 Fall`, `2024-2025 Spring`, `20251` gibi
  ifadelerden METU semester no formatina cevirir.
- Course line'larini `MATH 119 ... 4.0 7.5 DD` gibi tablolardan okur.
- Tum attempt'leri korur; retake semantigi prerequisite evaluator'daki latest
  attempt kuralina birakilir.
- `IP`, `I`, `IN PROGRESS`, `CONTINUING` gibi durumlari in-progress course olarak
  ayirir.
- Raw transcript line/text saklamaz; sadece count ve warning metadata'si tasir.

Urun akisi hedefi:

```text
Upload transcript PDF
  -> backend memory/temp-stream extraction
  -> TranscriptTextParser
  -> StudentPlanningInput
  -> SemesterPlanningPipeline
  -> deterministic Markdown report
  -> PDF/text bellekten cikartilir, storage yok
```

Kabul kriterleri:

- Parser raw transcript body'yi output JSON'a koymamalidir.
- PDF modunda kullanicidan bolum input'u istenmemelidir; bolum transcript'ten
  okunmalidir.
- PDF upload klasoru git tarafindan ignore edilmelidir.
- Retake attempt'leri kaybolmamalidir.
- In-progress dersler completed gibi sayilmamalidir.
- Parser emin olmadigi satirlarda sessiz akademik karar uretmemeli; warning
  metadata'si uretmelidir.
- Gercek transcript ornekleri geldikce parser fixture'lari anonimlestirilmis
  text uzerinden genisletilmelidir.

Sonraki isler:

1. Gercek METU transcript PDF layout'u ile parser regex'lerini test etmek.
2. `pypdf` dependency kararini netlestirmek ve dependency dosyasi eklemek.
3. Transcript upload endpoint tasariminda raw file storage'u default kapali yapmak.
4. UI'da "transcript dosyaniz saklanmaz" bilgisini urun copy'sine eklemek.
5. Parse confidence raporu uretmek: kac satir okundu, kac ders cikarildi, hangi
   satirlar category olarak anlasilamadi.
6. Tamamlanan elective derslerini transcript'ten kategoriye otomatik yazma
   problemini daha sonra official elective pool bilgisiyle birlikte ele almak.

## Phase 4: Student-Facing Product

UI veya API aşamasına domain logic stabil olduktan sonra geçilmeli.

### Phase 4A: API and Web Prototype

Durum: Ilk local web/API prototype tamamlandi; React + Node.js hedef mimarisi
baslatildi.

Tamamlanan dosyalar:

```text
student_planner/web/api.py
student_planner/web/server.py
student_planner/web/static/index.html
student_planner/web/static/styles.css
student_planner/web/static/app.js
scripts/run_web_app.py
tests/test_web_api.py
requirements.txt
web/package.json
web/server/index.js
web/client/index.html
web/client/src/main.jsx
web/client/src/styles.css
web/README.md
scripts/recommendation_api_bridge.py
```

Ilk local API:

```text
GET /api/health
POST /api/recommendations/from-json
POST /api/recommendations/from-transcript
```

Ilk karar:

- Ek web framework kullanmadan stdlib `ThreadingHTTPServer` ile local prototype
  kuruldu.
- Transcript upload endpoint'i multipart yerine JSON/base64 kabul eder; boylece
  ekstra dependency ve temp file ihtiyaci yoktur.
- Backend PDF'i bellekte decode eder, `pypdf` ile text cikarir, raw PDF/text
  saklamadan `StudentPlanningInput` uretir.
- Response deterministic Markdown report ve parse summary dondurur.
- Bu stdlib prototype production server degildir; React + Node.js hedef
  mimarisine gecis baslatildi.

React + Node hedef mimarisi:

```text
React UI
  -> Node/Express API
  -> scripts/recommendation_api_bridge.py
  -> Python deterministic planner
```

Neden bu ayrim?

- Akademik karar motoru Python'da olgunlasti; tekrar Node'a yazmak riskli olur.
- React/Node urun arayuzu icin daha uygun.
- Node sadece web/API orchestration yapar.
- Python bridge tek JSON contract ile planner'i kullanir.

React UI kapsam:

- PDF modunda program secimi yoktur; bolum transcript'ten okunur.
- Target semester.
- Easy / balanced / hard difficulty preference.
- Transcript PDF veya planner JSON input.
- Technical elective, restricted elective, non-technical elective ve free
  elective checkbox'lari.
- Her elective kategorisi icin opsiyonel concrete course code.
- Deterministik Markdown rapor render.
- Transcript parse summary.

Node/React calistirma:

```powershell
cd .\web
npm install
npm run build
npm run server
```

Not:

- Bu local ortamda Node.js kurulu degilse bu komutlar calismaz.
- Node.js 20+ kurulduktan sonra web prototype `http://127.0.0.1:3000/`
  adresinden acilabilir.

Calistirma:

```powershell
python .\scripts\run_web_app.py --port 8000
```

Sonraki API hedefleri:

```text
GET /programs
GET /programs/{program}/curriculum
GET /courses/{code}/why-blocked
POST /recommendations/session
```

Production'a giderken:

- Upload boyutu, content type ve virus/malware kontrolleri sertlestirilmeli.
- Raw transcript loglanmadigindan emin olmak icin structured logging policy
  yazilmali.
- Static frontend yerine gercek frontend framework secilebilir.
- Recommendation request/response schema version'lanmali.

### Phase 4B: Product UI Direction

Durum: React UI ilk modern tasarimla baslatildi, fakat henuz final urun UI'i
degil.

Urun kararlari:

- Ana kullanici akisi transcript PDF yukleme uzerinden olmali.
- Bolum input'u PDF modunda sorulmamali.
- Target semester input'u gecici olarak kalabilir; uzun vadede aktif offering
  snapshot'ina veya sistemde tanimli hedef doneme baglanmali.
- JSON input sadece developer/debug modu olarak kalmali.
- Elective tercihleri checkbox + opsiyonel concrete course code seklinde
  sorulmali.
- Arayuz teknik alanlari mumkun oldugunca gizlemeli; ogrenciye karar, gerekce
  ve dikkat noktalarini gostermeli.
- LLM olmayan deterministik rapor UI icinde daha okunur kartlara bolunmeli.

### Phase 4B: UI Prototype

Öğrenci için en faydalı ilk ekranlar:

- Bölüm seçimi
- Aldığım dersleri girme
- Kalan müfredat görünümü
- Alabileceğim dersler
- Neden alamıyorum açıklaması
- Sonraki dönem önerisi
- Prerequisite graph görselleştirme

UI'da dikkat:

- NCC/eşdeğer dersleri açık etiketle.
- Emin olunmayan seçmeli havuzları yanlış kesinlikte gösterme.
- Her önerinin gerekçesini göster.

## Testing Strategy

Şu an test klasörü yok. Bu borç büyümeden kapanmalı.

Önerilen yapı:

```text
tests/
  test_grades.py
  test_prerequisite_evaluator.py
  test_curriculum_progress.py
  test_course_identity.py
  test_audit_data_quality.py
```

İlk testler:

- Grade comparison
- Prerequisite set AND/OR semantics
- Alias resolution
- CENG critical prerequisite chains
- DB loader idempotency

## Legacy Cleanup

Root klasördeki eski deneysel CSV dosyaları 2026-05-10 tarihinde silindi.
Güncel source of truth `data/raw`, `data/processed` ve SQLite DB katmanlarıdır.
Root dizinde hala eski deneysel JSON çıktıları ve legacy scriptler bulunabilir;
bunlar ürün pipeline'ının ana girdisi değildir.

Önerilen hedef:

```text
data/legacy/offering_experiments/
data/legacy/prerequisite_experiments/
```

Bu cleanup, offerings layer başlamadan önce yapılmalı. Böylece yeni source of
truth karışmaz.

## Near-Term Execution Order

Guncel kisa vadeli sira:

1. Manual correction layer, grade model, prerequisite evaluator, curriculum
   progress, unlock analysis, recommendation v1 CLI ve offering-aware filter
   ilk versiyonlari tamamlandi.
2. Target-semester offering snapshot modeli benimsendi.
3. `config/offering_departments.json` ile engineering + service department
   scrape kapsami tanimlandi.
4. Offering coverage report hedef donem filtresiyle uretilmeli.
5. `python .\scripts\audit_data_quality.py` ve unit testleri her yuklemeden
   sonra calistir.
6. LLM narrative layer product v1 icin rafa kaldirildi; deterministik Markdown
   ana rapor olarak kalacak.
7. Transcript PDF input destegi gizlilik merkezli extraction katmaniyla
   gelistirilmeli; raw PDF/text kalici olarak tutulmamali.
8. Elective pool logic ve gercek transcript parsing fixture'lari
   entegrasyonu sonraki product katmanlari olarak ele alinmali.

Bu sıra, projenin amacına sadık kalır: önce doğru veri ve doğru anlam, sonra
öğrenciye faydalı tavsiye.

## Definition of Ready for Recommendation Engine

Recommendation engine'e ciddi biçimde başlamadan önce şunlar hazır olmalı:

- Audit fatal: 0
- Course identity resolver: var
- Grade model: var
- Prerequisite set semantics: testli
- At least CENG pilot curriculum review: yapılmış
- Offerings table: hedef donem SAIS snapshot'i ile dolu
- Manual correction layer: çalışıyor

## 2026-05-12 Product Rule Update

Bu adimda planner davranisi ogrenciye gosterilecek gercek arayuze yaklastirildi.

Uygulanan kurallar:

- Engineering mufredatlarinda Turkish gibi History secenekleri de normalize
  edildi: fall icin `HIST 2201`, spring icin `HIST 2202`.
- Transcript'te gecilmis, somut zorunlu curriculum dersi olmayan kredi
  dersleri elective tamamlama adayi olarak sayiliyor. Bu siniflandirma su an
  deterministik heuristic ile calisiyor; official elective pool listeleri
  yuklendiginde ayni servis daha guclu dogrulamaya baglanmali.
- Henuz non-technical/free elective tamamlamamis ve slotu kalan ogrenciler icin
  temel rotaya otomatik bir non-technical, yoksa free elective placeholder'i
  ekleniyor.
- Rota olusturma ECTS cap yerine METU credit tasiyan ders sayisina gore
  calisiyor: temel rota 5, ana rota 5, hizli rota 6 kredili ders hedefliyor.
- `estimated_credits == 0` olan uygun dersler tum rotalara ekleniyor ve kredili
  ders sayisi limitini tuketmiyor.
- Easy rota non-technical/free elective iceriyorsa ana rota ayni kategorileri
  disliyor; boylece ana rota 5 kredili concrete/major-progress dersiyle temiz
  bir alternatif olarak kalabiliyor.
- React arayuzunde JSON input kaldirildi. Kullanici akisi transcript PDF,
  hedef donem, zorluk tercihi ve opsiyonel elective tercihleri ile sinirlandi.
- Arayuz Markdown debug raporu yerine sadece onerilen rotalari ve kisa uyarilari
  gosteriyor; ECTS degerleri kullaniciya gosterilmiyor.
- Engineering summer practice kurali planlama aninda synthetic prerequisite
  edge olarak ekleniyor: curriculum'de `summer_practice` olarak isaretli
  300-level staj varsa `OHS 301 -> XXX 300`, ayni subject altinda 300/400
  cifti varsa `XXX 300 -> XXX 400` uygulanir. Bu sayede planner ayni donemde
  iki staji birden onermez ve OHS tamamlanmadan ilk staji acmaz.
- API response icinde `student_view` kontrati eklendi. Full `PlanningReport`
  debug/makine sozlesmesi olarak kalirken React UI ogrenciye gosterilecek
  sade rota kartlarini, uyari ozetlerini ve elective durumunu bu yeni
  kontrattan okur.

Sonraki dikkat noktasi:

- Elective extraction heuristic, official elective pool/curriculum rule verisi
  geldikten sonra kesin dogrulama katmanina donusturulmeli.

Bu koşullar sağlanmadan recommendation engine yazılırsa sistem çalışır gibi
görünebilir ama öğrenciye akademik olarak hatalı öneri verme riski yüksek olur.
