# Detailed Next Steps Plan

Son güncelleme: 2026-05-08

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
- Offerings: boş.
- Student planning logic: başlamadı.

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

Şu an:

```text
offerings: 0
```

Bu, personal recommendation için en kritik eksiklerden biri.

### Phase 2.6A: SAIS Source Adapter

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

Yeni script:

```text
scripts/scrape_offerings.py
```

Örnek komut:

```powershell
python .\scripts\scrape_offerings.py --programs CENG EEE ME --semesters 20241 20242
```

Çıktı:

```text
data/raw/sais/offerings/<semester>/<program>/...
data/processed/offerings/<semester>/<program>.offerings.json
data/processed/offerings/all_engineering_offerings.csv
```

İlk kapsam:

- 13 mühendislik programı
- Son birkaç dönem
- Course numeric code
- Display code
- Course title
- Department
- Semester
- Level/type

### Phase 2.6C: Offering Loader

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

### Phase 2.6D: Historical Offering Signal

İlk recommendation için kesin gelecek dönem bilgisi olmayabilir. Bu yüzden
historical signal hesaplanabilir:

```text
fall_probability
spring_probability
summer_probability
last_offered_semester
```

Bu ilk versiyonda ayrı tablo olmak zorunda değil; service-level hesaplanabilir.

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

### Phase 3F: Recommendation v1

Önerilen dosya:

```text
student_planner/services/recommendation.py
```

İlk algoritma:

1. Program curriculum'ını al.
2. Completed courses normalize et.
3. Remaining required courses bul.
4. Her course için prerequisite eligibility hesapla.
5. Target semester offering filtresi uygula, yoksa historical signal kullan.
6. Score hesapla:
   - prerequisite eligible
   - recommended semester yakınlığı
   - unlock value
   - required course priority
   - offering availability
   - not overloading same chain
7. Öneri sepeti üret.

v1 kapsam dışı:

- Tam timetable conflict çözümü
- Section/saat planlama
- Öğrencinin kişisel tercihleri
- Mezuniyet optimizasyonu

Kabul kriteri:

- Öneri açıklanabilir olmalı.
- Sistem emin olmadığı elective pool alanlarında yanlış öneri vermemeli.
- Blocked dersler missing prerequisite açıklamasıyla gelmeli.

### Phase 3G: CLI Prototype

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

## Phase 4: Student-Facing Product

UI veya API aşamasına domain logic stabil olduktan sonra geçilmeli.

### Phase 4A: API

Basit bir local API:

```text
GET /programs
GET /programs/{program}/curriculum
POST /recommendations
GET /courses/{code}/why-blocked
```

Framework seçimi daha sonra yapılabilir. İlk hedef domain logic olduğu için API
acil değil.

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

En doğru kısa vadeli sıra:

1. Manual correction layer tamamlandı.
2. Course identity review kararlarını manuel olarak vermeye başla.
3. `course_aliases.json` içine kesin alias kararlarını ekle.
4. `apply_manual_corrections.py` ve audit ile doğrula.
5. `student_planner/services/course_identity.py` yaz.
6. Test altyapısını başlat.
7. SAIS source adapter refactor yap.
8. Offerings pipeline yaz.
9. Prerequisite evaluator yaz.
10. Curriculum progress service yaz.
11. Recommendation v1 CLI yaz.

Bu sıra, projenin amacına sadık kalır: önce doğru veri ve doğru anlam, sonra
öğrenciye faydalı tavsiye.

## Definition of Ready for Recommendation Engine

Recommendation engine'e ciddi biçimde başlamadan önce şunlar hazır olmalı:

- Audit fatal: 0
- Course identity resolver: var
- Grade model: var
- Prerequisite set semantics: testli
- At least CENG pilot curriculum review: yapılmış
- Offerings table: hedef dönem veya historical dönemlerle dolu
- Manual correction layer: çalışıyor

Bu koşullar sağlanmadan recommendation engine yazılırsa sistem çalışır gibi
görünebilir ama öğrenciye akademik olarak hatalı öneri verme riski yüksek olur.
