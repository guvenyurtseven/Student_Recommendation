# METU Student Planner: Retrospective, Product Target, and Technical Roadmap

Son güncelleme: 2026-05-10

Bu doküman, projenin mevcut teknik durumunu ve hedef ürün vizyonunu tek yerde
toplamak için yazıldı. Amaç, sohbet geçmişi kaybolsa bile projenin neden
başladığını, hangi verilerin üretildiğini, hangi modüllerin var olduğunu, hangi
kararların alındığını ve bundan sonra hangi mimari doğrultuda ilerlenmesi
gerektiğini eksiksiz biçimde aktarabilmektir.

## 1. Ürün Vizyonu

Hedef ürün, ODTÜ öğrencisinin dönem başlamadan önce ders seçimini daha bilinçli
yapmasına yardım eden bir öğrenci asistanı / akademik planlayıcıdır.

Öğrenci sisteme temel olarak şunları verecek:

- Bölümü.
- Şimdiye kadar aldığı dersler.
- Bu derslerdeki harf notları.
- Gerekirse transcript PDF'i.
- Planlamak istediği dönem.
- Dönem sonu hedef GPA veya akademik hedef.
- Dönemin kolay, dengeli veya zor geçmesi tercihi.
- İstenirse hedef ECTS / kredi yükü.

Sistem bu inputu kullanarak şunları üretmeli:

- Öğrencinin müfredatta hangi noktada olduğunu.
- Hangi zorunlu dersleri tamamladığını.
- Hangi zorunlu derslerin kaldığını.
- Hangi course choice veya elective requirement'ların tamamlandığını.
- Hangi requirement'ların eksik kaldığını.
- Öğrencinin prerequisite açısından hangi dersleri alabileceğini.
- Hangi dersleri alamadığını ve neden alamadığını.
- Hangi derslerin gelecekte en çok dersi açtığını.
- Öğrencinin hedef zorluk seviyesine göre uygun ders sepetlerini.
- Her ders sepeti için ECTS / kredi yükü ve risk yorumunu.
- Sonuçların öğrenciye anlaşılır bir rapor olarak açıklamasını.

Bu ürünün çekirdeği haftalık ders programı çizmek değildir. Haftalık ders
programı, section saatleri ve robotdegilim.xyz gibi servislerden alınabilecek
schedule görünümü ileride eklenebilir bir özelliktir. Temel hedef, öğrenciye
kişisel akademik durumuna göre bir dönemlik yol haritası sunmaktır.

## 2. Temel Ürün Prensibi

Bu projedeki en önemli akademik ayrım şudur:

Bir bölümün açtığı dersler, o bölüm öğrencisinin müfredatı değildir.

Örneğin:

- CENG bölümü CENG kodlu dersler açar.
- Fakat CENG öğrencisinin müfredatında MATH, PHYS, EE, STAT, ENG, TURK, HIST
  gibi bölüm dışı servis dersleri de bulunur.
- Diğer mühendisliklerde de benzer şekilde CENG 240, MATH 119, MATH 120,
  PHYS 105, CHEM servis dersleri gibi dış bölüm dersleri zorunlu olabilir.

Bu yüzden sistem iki ana akademik katmanı ayrı tutar:

1. Curriculum layer
   - Öğrencinin mezun olmak için tamamlaması gereken requirement'lar.
   - Required course, course choice, technical elective, nontechnical elective,
     free elective, summer practice gibi requirement türleri burada temsil edilir.

2. Prerequisite layer
   - Derslerin birbirine bağımlılık ilişkileri.
   - Edge yönü prerequisite -> course şeklindedir.
   - Örnek: MATH 119 -> MATH 120 -> MATH 219 -> CENG 384.

Recommendation engine bu iki katmanı birlikte kullanmalıdır:

- Curriculum, öğrencinin hangi dersleri önemsemesi gerektiğini söyler.
- Prerequisite graph, öğrencinin hangi dersleri alabileceğini ve hangi derslerin
  gelecekte neyi açacağını söyler.
- Offerings katmanı, dersin hedef dönemde açılıp açılmadığını söyler.
- Student record katmanı, öğrencinin geçmiş akademik durumunu söyler.

## 3. Hedef Kapsam

İlk hedef kapsam ODTÜ Ankara kampüsü mühendislik lisans programlarıdır.

Aktif işlenen 13 program:

| Kod | Program |
| --- | --- |
| AE | Aerospace Engineering |
| CE | Civil Engineering |
| CENG | Computer Engineering |
| CHE | Chemical Engineering |
| EEE | Electrical and Electronics Engineering |
| ENVE | Environmental Engineering |
| FDE | Food Engineering |
| GEOE | Geological Engineering |
| IE | Industrial Engineering |
| ME | Mechanical Engineering |
| METE | Metallurgical and Materials Engineering |
| MINE | Mining Engineering |
| PETE | Petroleum and Natural Gas Engineering |

ES, config içinde pasif program olarak tutulmaktadır; bu aşamada aktif lisans
hedef kapsamına dahil edilmemiştir.

## 4. Mevcut Repository Yapısı

Ana dizin yapısı:

```text
student_planner/
  db/
  domain/
  repositories/
  services/
  sources/
config/
data/
  db/
  manual/
  processed/
  raw/
docs/
scripts/
tests/
```

Eski deneysel script ve bazı JSON çıktılar root dizinde hala durmaktadır.
Kök dizindeki eski deneysel CSV dosyaları 2026-05-10 tarihinde silinmiştir;
güncel source of truth artık `data/raw`, `data/processed` ve SQLite DB
katmanlarıdır.

```text
scrape_metu_program_courses.py
scrape_prerequisite_graph.py
*-20241-20242-prerequisite-*.json
```

Yeni geliştirmeler için ana yön şudur:

- Domain logic: `student_planner/domain/`
- Application services: `student_planner/services/`
- Persistence adapters: `student_planner/repositories/`
- Source adapters: `student_planner/sources/`
- CLI entrypoint'leri: `scripts/`
- Testler: `tests/`

## 5. Veri Katmanları

### 5.1 Raw Data

`data/raw/` altında kaynaklardan alınan ham snapshot'lar saklanır.

METU Academic Catalog snapshot yapısı:

```text
data/raw/catalog/<PROGRAM>/<timestamp>/program.html
data/raw/catalog/<PROGRAM>/<timestamp>/metadata.json
```

Bu yaklaşım önemlidir; çünkü parser değişse bile aynı kaynak HTML üzerinden
yeniden işlem yapılabilir.

### 5.2 Processed Data

`data/processed/` altında normalize edilmiş JSON/CSV çıktılar bulunur.

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
data/processed/prerequisites/engineering-latest-prerequisite-closure-edges.csv
data/processed/prerequisites/engineering-latest-prerequisite-closure-nodes.csv
data/processed/prerequisites/engineering-latest-prerequisite-closure-unresolved.csv

data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure.json
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-edges.csv
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-nodes.csv
data/processed/prerequisites/<PROGRAM>-latest-prerequisite-closure-unresolved.csv
```

Rapor çıktıları:

```text
data/processed/reports/data_quality_report.md
data/processed/reports/course_identity_review.md
```

### 5.3 Manual Data

Generated veri elle değiştirilmez. Düzeltmeler `data/manual/` altında tutulur.

Mevcut correction dosyaları:

```text
data/manual/corrections/course_aliases.json
data/manual/corrections/course_overrides.json
data/manual/corrections/prerequisite_overrides.json
data/manual/corrections/curriculum_overrides.json
```

Şu anda course alias ve course override altyapısı uygulanabilir durumdadır.
Prerequisite ve curriculum override dosyaları ayrılmıştır fakat uygulama mantığı
henüz tamamlanmamıştır.

### 5.4 Database

SQLite veritabanı:

```text
data/db/student_planner.sqlite
```

SQLite ilk aşama için doğru seçimdir:

- Servis kurulumu gerektirmez.
- Local scraping ve analiz için yeterlidir.
- Relational constraint'ler sayesinde veri tutarlılığı sağlar.
- Gerektiğinde ileride PostgreSQL'e taşınabilir.

## 6. Mevcut Database Durumu

Son kontrol edilen tablo sayıları:

| Tablo | Satır |
| --- | ---: |
| programs | 14 |
| courses | 393 |
| curriculum_versions | 13 |
| curriculum_requirements | 696 |
| requirement_options | 652 |
| prerequisite_edges | 504 |
| source_documents | 16 |
| course_aliases | 0 |
| manual_correction_log | 0 |
| offerings | 0 |
| student_profiles | 0 |
| student_completed_courses | 0 |

Önemli yorumlar:

- Aktif lisans programı sayısı 13'tür.
- `programs=14` görünmesinin nedeni ES'in pasif olarak config'te tutulmasıdır.
- `offerings` henüz boş olduğu için sistem şimdilik hedef dönemde ders açılma
  bilgisini DB üzerinden cevaplayamaz.
- `student_profiles` ve `student_completed_courses` boş olduğu için kalıcı
  öğrenci kaydı henüz kullanılmamaktadır.
- Recommendation prototipi ilk etapta DB'ye öğrenci yazmadan, input JSON/CSV
  üzerinden çalışabilir.

## 7. Mevcut Curriculum Verisi

13 aktif mühendislik programı için latest curriculum scrape edilmiştir.

Program bazlı özet:

| Program | Requirement | Option | Placeholder | Unique Course |
| --- | ---: | ---: | ---: | ---: |
| AE | 55 | 50 | 11 | 50 |
| CE | 54 | 49 | 11 | 49 |
| CENG | 50 | 46 | 10 | 46 |
| CHE | 52 | 50 | 8 | 50 |
| EEE | 54 | 47 | 13 | 47 |
| ENVE | 53 | 50 | 9 | 50 |
| FDE | 52 | 49 | 9 | 49 |
| GEOE | 55 | 52 | 9 | 52 |
| IE | 56 | 53 | 9 | 53 |
| ME | 54 | 51 | 9 | 51 |
| METE | 54 | 51 | 9 | 51 |
| MINE | 53 | 52 | 7 | 52 |
| PETE | 54 | 52 | 8 | 52 |

Requirement type dağılımı:

| Requirement Type | Count |
| --- | ---: |
| required_course | 496 |
| technical_elective_pool | 57 |
| course_choice | 52 |
| nontechnical_elective_pool | 31 |
| summer_practice | 26 |
| restricted_elective_pool | 21 |
| free_elective_pool | 13 |

Bu modelleme bilinçli olarak yalnızca düz ders listesi değildir. Elective pool,
course choice ve summer practice gibi requirement türleri korunmuştur. Bu sayede
ileride öğrencinin müfredat ilerlemesi daha doğru hesaplanabilir.

Risk:

- Bütün curriculum kayıtları hala `review_status=scraped` seviyesindedir.
- Production kullanım öncesi insan gözüyle review yapılmalıdır.
- Elective havuzlarının gerçek ders listeleri henüz tam çözümlenmemiştir.

## 8. Mevcut Prerequisite Verisi

Birleşik engineering prerequisite closure:

```text
data/processed/prerequisites/engineering-latest-prerequisite-closure.json
```

Durum:

| Metrik | Değer |
| --- | ---: |
| Program | 13 |
| Node | 393 |
| Edge | 504 |
| Unresolved | 26 |
| DAG | true |

Edge yönü:

```text
prerequisite -> course
```

Örnek:

```text
MATH 119 -> MATH 120
```

Bu, MATH 120 dersini alabilmek için MATH 119 gerektiği anlamına gelir.

Minimum grade dağılımı:

| Min Grade | Edge Count |
| --- | ---: |
| DD | 479 |
| S | 22 |
| U | 3 |

Her bölüm için ayrı prerequisite closure dosyası da vardır ve her biri DAG olarak
doğrulanmıştır.

Riskler:

- 26 unresolved course manuel incelenmelidir.
- 35 numeric subject-code course vardır; örneğin `355 140`, `357 119`.
- 55 NCC prerequisite edge vardır.
- Bu alternatifler ham graph içinde korunmalıdır, fakat öğrenciye gösterilirken
  etiketlenmeli veya Ankara kampüsü için doğru canonical course'a bağlanmalıdır.

## 9. Mevcut Domain Modülleri

### 9.1 `student_planner/domain/models.py`

Mevcut genel domain modelleri:

- `ReviewStatus`
- `RequirementType`
- `Program`
- `Course`
- `CurriculumRequirement`
- `CurriculumVersion`

Bu dosya curriculum ve catalog tarafının saf domain modelini temsil eder.

### 9.2 `student_planner/domain/grades.py`

Desteklenen notlar:

```text
AA BA BB CB CC DC DD FD FF S U W NA EX
```

Ana kararlar:

- `DD` ve üstü letter grade kredi kazandırır.
- `FD`, `FF`, `NA`, `U`, `W` başarısız sayılır.
- `NA`, pratikte `FF` gibi ele alınır.
- `EX`, pratikte `S` gibi ele alınır.
- `W`, prerequisite sağlamaz.
- `S` ve `EX`, DD gibi normal pass-level minimumları sağlar.
- `S` ve `EX`, CC gibi daha sıkı letter minimumları sağlamaz.
- `U`, kredi kazandırmaz; fakat SAIS bazı S/U prerequisite satırlarında minimum
  `U` kullandığı için explicit `U` minimumunu sağlar.

Bu model testlidir.

### 9.3 `student_planner/services/prerequisite_evaluator.py`

Bu servis şu soruyu cevaplar:

```text
Bu öğrenci bu dersi prerequisite açısından alabilir mi?
```

Ana modeller:

- `CompletedCourse`
- `PrerequisiteEdge`
- `RequirementEvaluation`
- `PrerequisiteSetEvaluation`
- `EligibilityResult`

Semantik:

- Aynı `set_no` içindeki edge'ler AND mantığıyla değerlendirilir.
- Farklı `set_no` grupları OR mantığıyla değerlendirilir.
- Sadece target course'un direct prerequisite setleri kontrol edilir.
- Transitive prerequisite zinciri yeniden doğrulanmaz.

Bu son karar özellikle önemlidir:

```text
MATH 119 -> MATH 120 -> MATH 219
```

Öğrenci MATH 119 ve MATH 120'yi geçmiş, sonra MATH 119'u tekrar alıp kalmışsa,
MATH 219 için güncel direct prerequisite MATH 120 olduğu için MATH 219 eligibility
bozulmaz. Fakat target MATH 120 ise MATH 119'un son attempt'i dikkate alınır.

Tekrarlı derslerde latest attempt seçimi:

1. `attempt_order`
2. `completed_semester_no`
3. input sırası

Bu model testlidir.

### 9.4 `student_planner/repositories/sqlite.py`

SQLite repository şu anda şunları yapabilir:

- DB bağlantısı açmak.
- Course alias map üretmek.
- Display code ve numeric code aliaslarını çözmek.
- Manual `course_aliases` kayıtlarını alias map'e eklemek.
- Bir target course için prerequisite edge'leri çekmek.
- DB verisiyle eligibility değerlendirmek.

Bu katman testlidir.

## 10. Mevcut Scriptler

Ana pipeline scriptleri:

```text
scripts/init_db.py
scripts/load_programs.py
scripts/scrape_curricula.py
scripts/load_curricula.py
scripts/build_prerequisite_closure.py
scripts/load_prerequisite_closure.py
scripts/audit_data_quality.py
scripts/generate_course_identity_review.py
scripts/apply_manual_corrections.py
```

Komut akışı:

```powershell
python .\scripts\init_db.py
python .\scripts\load_programs.py
python .\scripts\scrape_curricula.py
python .\scripts\load_curricula.py
python .\scripts\build_prerequisite_closure.py
python .\scripts\load_prerequisite_closure.py --clear-existing
python .\scripts\apply_manual_corrections.py
python .\scripts\audit_data_quality.py
python .\scripts\generate_course_identity_review.py
```

SAIS login gerektiren komutlar `env.local` üzerinden credential okur. Bu dosya
gizlidir, rapora credential yazılmamalıdır ve paylaşılmamalıdır.

## 11. Test Durumu

Mevcut testler:

```text
tests/test_grades.py
tests/test_prerequisite_evaluator.py
tests/test_sqlite_repository.py
```

Test kapsamı:

- Grade normalization.
- Grade ordering.
- NA/EX/W/U davranışları.
- Prerequisite AND/OR set mantığı.
- Alias normalization.
- Repeated course attempt mantığı.
- Failed transitive retake kuralı.
- SQLite repository üzerinden prerequisite eligibility.

Komut:

```powershell
python -m unittest discover -s tests -v
```

## 12. Mevcut Veri Kalitesi

Son audit durumu:

```text
Status: PASS_WITH_WARNINGS
Fatal findings: 0
Warnings: 23
```

Önemli warning grupları:

- Curriculum records hala `scraped`.
- 1 course title boş: `HIST 2202`.
- 35 numeric subject-code course var.
- 55 NCC prerequisite alternative edge var.
- 26 unresolved prerequisite course var.
- `offerings`, `student_profiles`, `student_completed_courses` tabloları boş.

Bu uyarılar sistemi geliştirmeyi engellemez; fakat öğrenciye production seviyede
öneri vermeden önce review ve correction sürecinden geçmelidir.

## 13. Hedef Mimari Modüller

Final ürüne doğru planlanan ana modüller şunlardır.

### 13.1 Student Input Layer

Sorumluluk:

- Öğrenciden manuel ders listesi almak.
- İleride transcript PDF parse etmek.
- Inputu canonical planning modeline çevirmek.

Planlanan dosyalar:

```text
student_planner/domain/planning.py
student_planner/sources/transcript_pdf.py
scripts/parse_transcript.py
```

İlk versiyonda PDF değil, JSON/CSV/manual input hedeflenmelidir.

### 13.2 Curriculum Progress Service

Sorumluluk:

- Öğrencinin bölüm müfredatında nerede olduğunu hesaplamak.
- Tamamlanan required course'ları bulmak.
- Kalan required course'ları bulmak.
- Course choice requirement'ları değerlendirmek.
- Elective placeholder'ları güvenli biçimde raporlamak.

Planlanan dosya:

```text
student_planner/services/curriculum_progress.py
```

Bu, sıradaki en kritik application service'tir.

### 13.3 Candidate Course Generator

Sorumluluk:

- Kalan müfredat derslerini aday havuza almak.
- Her aday ders için prerequisite eligibility çalıştırmak.
- Eligible ve blocked dersleri ayırmak.

Planlanan dosya:

```text
student_planner/services/candidate_courses.py
```

### 13.4 Unlock Analysis

Sorumluluk:

- Bir dersi almanın gelecekte hangi dersleri açacağını hesaplamak.
- Direct unlock count.
- Transitive unlock count.
- Curriculum-relevant unlock count.
- Critical chain contribution.

Planlanan dosya:

```text
student_planner/services/unlock_analysis.py
```

### 13.5 Load and Difficulty Scoring

Sorumluluk:

- Dönem zorluğunu yaklaşık skorlamak.
- ECTS toplamını hesaplamak.
- Course count, course level, prerequisite depth, technical density gibi
  sinyalleri birleştirmek.

Planlanan dosya:

```text
student_planner/services/difficulty.py
```

İlk versiyon heuristic olmalıdır. ML veya LLM kararı gerekli değildir.

### 13.6 Recommendation Engine

Sorumluluk:

- Öğrencinin hedeflerine göre ders sepeti senaryoları üretmek.
- Kolay, dengeli ve agresif alternatifleri karşılaştırmak.
- Her önerinin gerekçesini üretmek.

Planlanan dosya:

```text
student_planner/services/recommendation.py
```

LLM bu engine'in yerine geçmemelidir. Engine deterministic karar üretmeli, LLM
yalnızca açıklama katmanı olarak kullanılmalıdır.

### 13.7 LLM Report Layer

Sorumluluk:

- Deterministic engine çıktısını öğrenciye anlaşılır metne çevirmek.
- Riskleri, tavsiyeleri ve tradeoff'ları doğal dille açıklamak.

Planlanan dosya:

```text
student_planner/services/reporting.py
```

Güvenlik ilkesi:

- Raw transcript veya hassas öğrenci belgesi LLM'e doğrudan gönderilmemelidir.
- LLM'e sadece sanitize edilmiş akademik özet ve deterministic sonuçlar
  verilmelidir.
- LLM akademik kural icat etmemelidir.

### 13.8 Offerings Layer

Sorumluluk:

- Derslerin hangi dönemlerde açıldığını toplamak.
- Hedef dönemde açılma bilgisini recommendation engine'e vermek.
- Geçmiş dönemlerden fall/spring açılma sinyali üretmek.

Planlanan dosyalar:

```text
student_planner/sources/sais.py
scripts/scrape_offerings.py
scripts/load_offerings.py
student_planner/services/offering_availability.py
```

Bu modül recommendation için çok önemlidir, fakat ilk planning contract ve
curriculum progress servisinden sonra uygulanabilir.

### 13.9 Schedule Provider Layer

Sorumluluk:

- Ders stack'i için haftalık program şeması üretmek.
- İleride robotdegilim.xyz gibi dış kaynaklardan schedule almak.

Planlanan arayüz:

```text
ScheduleProvider
RobotDegilimScheduleProvider
MockScheduleProvider
```

Bu modül core ürün hedefi değildir. Recommendation engine schedule olmadan da
çalışmalıdır.

## 14. Yakın Vadeli Teknik Sıra

Şu andan itibaren en doğru sıra:

1. Planning input/output domain sözleşmesini yaz.
2. Repository'ye latest curriculum requirement okuma metodları ekle.
3. CurriculumProgressService yaz.
4. Bu servis için küçük fixture testleri oluştur.
5. CandidateCourseGenerator ekle.
6. Difficulty/load scoring modelini ekle.
7. Recommendation scenario generator v0 yaz.
8. Basit CLI prototip yaz.
9. Offerings pipeline'ı yeni mimariye taşı.
10. Transcript PDF parser'ı adapter olarak ekle.
11. LLM report layer'ı deterministic JSON üstüne kur.
12. UI/API prototipine geç.

## 15. Sıradaki Somut Adım

Bu rapordan hemen sonra başlanacak teknik adım:

```text
student_planner/domain/planning.py
```

Bu dosya öğrenci merkezli planlama için input/output sözleşmesini tanımlamalıdır.

Beklenen ilk modeller:

- `DifficultyPreference`
- `PlanningWarningSeverity`
- `RequirementProgressStatus`
- `CoursePlanningStatus`
- `CompletedCourseAttempt`
- `InProgressCourse`
- `PlanningGoal`
- `StudentPlanningInput`
- `PlanningWarning`
- `RequirementProgress`
- `CourseEligibilitySummary`
- `CourseRecommendation`
- `RecommendationScenario`
- `PlanningReport`

Bu modeller henüz recommendation logic yazmayacak. Ama sonraki tüm servisler aynı
veri sözleşmesi üzerinden konuşacak:

- Curriculum progress service bu modellerle çıktı verecek.
- Candidate course service bu modelleri zenginleştirecek.
- Recommendation engine bu modellerle senaryo üretecek.
- LLM report layer bu modellerden rapor yazacak.
- CLI/API/UI aynı contract'ı kullanacak.

Bu nedenle bu dosya projenin scraper/data-engineering aşamasından öğrenci
merkezli product engine aşamasına geçiş kapısıdır.

## 16. Product Definition of Done v1

İlk gerçekten kullanılabilir v1 için minimum kabul kriterleri:

- Öğrenci bölümünü seçebilir.
- Öğrenci completed course + grade listesini verebilir.
- Sistem latest curriculum üzerinden kalan zorunlu dersleri çıkarabilir.
- Sistem prerequisite açısından eligible/blocked dersleri ayırabilir.
- Sistem blocked derslerde eksik prerequisite'leri açıklayabilir.
- Sistem kolay/dengeli/zor hedefe göre en az 2-3 ders sepeti senaryosu sunabilir.
- Her senaryoda toplam ECTS/kredi ve zorluk yorumu bulunur.
- Sistem emin olmadığı elective/identity/offering durumlarını açık uyarı olarak
  gösterir.
- LLM varsa yalnızca deterministic sonucun açıklamasını yapar; akademik karar
  verici rolünde olmaz.

Bu eşik sağlandığında proje artık yalnızca scraper değil, öğrenciye gerçek
fayda üreten bir akademik planlayıcı haline gelmiş olur.
