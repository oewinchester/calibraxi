# CalibraXI — Working Canonical Product Document

**Durum:** CANLI TASLAK / CONSOLIDATION IN PROGRESS  
**Başlangıç:** 2026-09-21  
**Amaç:** Eski Calibra XI dokümanlarının hiçbir değerli kararını kaybetmeden, yeni ürün yönünü merkeze alan temiz ve az sayıda kanonik dokümana geçiş.  
**Bu dosyanın rolü:** Kullanıcının bundan sonra karalama/not şeklinde dahi verdiği tüm ürün kararlarının eksiksiz işlendiği yaşayan ana ürün dokümanı.

> Bu sürüm final değildir. Eski mimari belgeler kaynak arşiv olarak korunur. Yeni kararlarla çakışan eski kararlar sessizce silinmez; `PRESERVED`, `SUPERSEDED`, `REOPENED`, `OPEN` veya `HISTORICAL` olarak sınıflandırılır.

---

## 0. Konsolidasyon Sözleşmesi

1. **Bilgi kaybı yasak.** Eski dokümanlardaki bir karar yalnızca yeni ürün yönüyle çelişiyorsa kaldırılabilir; bu durumda eski kararın ne olduğu ve neyin onu supersede ettiği izlenebilir olmalıdır.
2. **“Bu fazda kapsam dışı” ile “üründe asla olmayacak” aynı şey değildir.** Eski belgelerde Recommendation, coupon, ranking, bankroll, staking, Portfolio ve benzeri konuların bir fazda açılmamış olması, yeni CalibraXI ürününde bunların yasak olduğu anlamına gelmez.
3. **Yeni kullanıcı kararı ürün yönünde önceliklidir.** Yeni karar analitik doğruluk invariants'ını ihlal etmiyorsa ürün/UI kararlarını supersede edebilir.
4. **Analitik gerçek UI tarafından üretilmez.** UI; probability, currentness, reliability, signal, recommendation, ranking veya track record matematiğini kendi içinde icat etmez.
5. **Point-in-time ve lineage korunur.** Tahmin üretildikten sonra yeni veri/odds ile geçmiş tahmin sessizce değiştirilmez.
6. **Forecast, Reliability/Confidence, Signal, Recommendation ve kullanıcı seçimi ayrı katmanlardır.**
7. **Bet Builder ve kombine olasılıkları naif çarpımla oluşturulmaz.** Aynı maç veya ilişkili marketlerde bağımlılık/joint probability açıkça modellenmeden “güvenilir kombine” iddiası yapılamaz.
8. **Performans raporu seçici başarı vitrini değildir.** Population, sample, odds basis, dönem, market, model/release ve publication/surface bağlamı korunur.
9. **Sanal betslip gerçek bahis değildir.** Kullanıcı CalibraXI içinde sanal bakiye ile strateji simülasyonu ve geçmiş takibi yapar; gerçek bookmaker'a bahis gönderimi ayrı bir ürün kararı olmadan yapılmaz.
10. Bu dosya her yeni konuşma turunda büyütülecek; daha sonra nihai 2–3 dokümanlık canonical set'e dönüştürülecek.

---

# 1. Ürün Kimliği ve North Star

CalibraXI yalnızca “maç tahmini veren site” değildir.

Yeni ürün yönü:

**Futbol verisi + probabilistic forecasting + power ratings + günlük decision widgets + market/odds context + bet builder + sanal strateji laboratuvarı + şeffaf performans/ROI takibi** sunan, masaüstünde bir **predictive football analytics** terminali gibi çalışan web ürünü.

İlk açılış deneyimi klasik pazarlama landing page'i değildir. Kullanıcı `calibraxi.com` adresine girdiğinde doğrudan günün futbol verisini ve karar destek araçlarını görmelidir.

CalibraXI gerçek bahis işlemini gerçekleştiren bir bookmaker değildir. Ürün; analiz, tahmin, karşılaştırma, simülasyon ve performans takibi sağlar.

## 1.1 Visual Direction — LIGHT-FIRST / SUPERSEDES LEGACY DARK-FIRST

Yeni CalibraXI'ın **birincil görsel teması light theme** olacaktır.

Bu karar eski `dark-first / near-black / charcoal` UI yönünü **SUPERSEDED** eder. Eski UI/UX ve wireframe belgelerindeki koyu tema artık yeni ürünün görsel otoritesi değildir; yalnızca layout, semantic-state ayrımları, progressive disclosure ve analitik doğruluk gibi tema-bağımsız ilkeler korunur.

Light theme hedefi:
- temiz, premium, veri yoğun ama ferah;
- predictive football analytics terminali hissi;
- beyaz / kırık beyaz / çok açık nötr yüzeyler;
- güçlü tipografik hiyerarşi;
- ince grid/border ayrımları;
- yüksek veri yoğunluğuna rağmen bookmaker/casino hissinden kaçınma;
- brand accent ile analytical semantic colors'ın birbirinden ayrı kalması;
- probability, reliability, positive edge, win/loss ve integrity gibi anlamların yalnızca marka renginden türetilmemesi.

Dark mode gelecekte opsiyonel olarak yeniden açılabilir; **mevcut ürün hedefi light-first'tür.**

## 1.2 Product Category / Terminology — `Football Intelligence` RETIRED

`Football Intelligence` artık CalibraXI'ın ürün kategorisi, tagline'ı veya ana tanımlayıcı terimi olarak kullanılmayacaktır.

**Working replacement:** **Predictive Football Analytics**

Bu ifade şimdilik çalışma terimidir; final brand/copy aşamasında yeniden değerlendirilebilir.

Şimdilik ürün dili:
- **CalibraXI — Predictive Football Analytics**
- public-facing kısa marka cümlesi / tagline: **Football, Calibrated.** — **LOCKED / APPROVED**

`Match Intelligence`, `Daily Intelligence`, `Football Intelligence Terminal` gibi eski ifadeler yeni canonical dokümantasyonda yeni isimlerle değiştirilir. Gerekli yerlerde `analysis`, `analytics`, `projection`, `forecast`, `market`, `match center` gibi daha kesin terimler kullanılır.

## 1.3 Gerçek Futbol Kimlik Varlıkları

CalibraXI sentetik/generic takım ve oyuncu görselleriyle çalışmayacaktır. Ürün genelinde mümkün olan ve lisans/sağlayıcı sözleşmesinin izin verdiği gerçek futbol kimlik varlıkları kullanılacaktır:

- gerçek takım armaları / club crests;
- gerçek oyuncu fotoğrafları / headshots;
- competition / league logoları;
- federasyon / turnuva görselleri uygun olduğunda;
- ülke bayrakları;
- venue/stadium görselleri uygun ve lisanslı veri bulunduğunda.

Kurallar:
- takım armasının yerine AI tarafından üretilmiş benzer bir arma kullanılmaz;
- oyuncu fotoğrafı yoksa sahte/generative yüz kullanılmaz; kontrollü placeholder kullanılır;
- asset kaynağı, provider kimliği, kullanım hakkı/lisans bilgisi ve güncellenme durumu Engineering dokümanında izlenir;
- transfer olduğunda oyuncu-team association güncellenir fakat tarihsel fixture snapshot'ları geçmişteki takım bağlamını korur;
- responsive/high-DPI asset varyantları desteklenir;
- accessibility için anlamlı accessible label/alt text sağlanır.

---

# 2. Ana Sayfa — CalibraXI Daily Analytics Dashboard

## 2.1 Temel karar

**Ana sayfa doğrudan dashboard olacaktır.**

Kullanıcı ilk ekranda ürün açıklaması okumak zorunda bırakılmaz. Ürünün değeri gerçek veri, gerçek maçlar, gerçek model çıktıları ve günün istatistikleriyle gösterilir.

## 2.2 Üst tanıtım bandı

Sayfanın en üst kısmında küçük/yatay bir tanıtım veya context banner'ı bulunur.

Amaçları:
- CalibraXI'ın ne yaptığını birkaç kelimede anlatmak;
- günün veri kapsamını veya önemli bir özelliği göstermek;
- gerektiğinde Premium, yeni model release'i, güncelleme veya metodoloji mesajını duyurmak;
- dashboard alanını domine etmemek.

Bu alan büyük bir SaaS hero'suna dönüşmemelidir.

## 2.3 Dashboard'un ilk katmanı — Günlük karar ve keşif widget'ları

Ana ekranın üst bölümü bir widget sistemi olarak tasarlanacaktır. İlk canonical widget ailesi:

### A. Günün Fikstürü
- Günün maçları.
- Lig/kupa, başlama saati, takımlar, durum.
- Desteklenen ana market forecast'larına hızlı bakış.
- Maç detayına geçiş.
- Kullanıcı seçilebilir bir analiz görüyorsa `+` ile betslip'e ekleyebilme.

### B. Günün Tahmini
CalibraXI'ın gün için öne çıkardığı tek veya sınırlı sayıda güçlü analytical/recommendation proposition.

Gösterilebilecek öğeler:
- maç;
- market/selection;
- model probability;
- uygun olduğunda odds;
- implied market probability;
- edge/value;
- reliability/confidence sunumu;
- kısa gerekçe;
- analiz zamanı / quote zamanı;
- `+` ile sanal betslip'e ekleme.

**Not:** “Günün Tahmini” genuine Recommendation Architecture gerektirir. Signal'ın doğrudan “pick” diye yeniden adlandırılması yeterli değildir.

### C. Günün En Formda / Göze Çarpan Takımları
Günün fikstüründe bulunan takımlardan form ve performans açısından öne çıkanlar.

Örnek göstergeler:
- son N maç performansı;
- recency-weighted form;
- goals for / against;
- xG / xGA (kaynak ve metodoloji uygunsa);
- shots / SOT;
- home/away split;
- streak;
- opponent-adjusted strength;
- güncel takım state'i;
- ilgili maç ve kickoff.

“Form” ile kalıcı takım gücü birbirine karıştırılmayacaktır.

### D. League Power Rankings
Lig bazında ayrı ranking tabloları.

Örnek görünüm:

| Rank | Team | ATT | DEF | OVR | Δ |
|---:|---|---:|---:|---:|---:|
| 1 | Team A | 2.13 | 1.07 | +1.07 | ↑ |
| 2 | Team B | … | … | … | ↓ |

Gereksinimler:
- Premier League, La Liga vb. lig lig gezilebilir;
- mevcut sıralama;
- ATT rating;
- DEF rating;
- OVR / overall rating;
- önceki ranking/snapshot'a göre yükseliş-düşüş;
- mümkünse trend sparkline;
- rating'in hangi dönem ve bilgi cutoff'una ait olduğu;
- rating tanımı metodoloji ekranında açıklanmalı.

**OPEN:** ATT, DEF ve OVR'ın kesin matematiksel tanımı daha sonra Power Rating Architecture içinde dondurulacak. Görsel format ürün kararıdır; matematik henüz icat edilmemelidir.

### E. CalibraXI Studio — Daily Builder Preview

Ana sayfada ayrı ayrı birden fazla Bet Builder sistemi bulunmayacaktır.

Bunun yerine **tek canonical builder ürünü `CalibraXI Studio` olacaktır.** Ana sayfa yalnızca Studio'nun o gün için ürettiği bir veya birkaç preview/preset'i gösterebilir ve kullanıcıyı Studio'ya taşır.

Studio içinde en az şu builder varyasyonları desteklenir:

**Daily Cross-Match**
- farklı maçlardan güçlü/eligible selections;
- combined odds;
- dependency/compatibility kontrolü;
- recommendation/reliability context.

**Daily Same-Match**
- tek fixture içinde birden fazla selection;
- joint probability / dependency-aware hesap;
- uyumsuz veya desteklenmeyen kombinasyonların açıkça engellenmesi.

**Manual Builder**
- kullanıcı selections'ı kendisi seçer;
- CalibraXI olasılık, dependency, availability ve market context'i desteklenen ölçüde gösterir;
- kullanıcı seçimi CalibraXI Recommendation olarak yeniden etiketlenmez.

Homepage'deki builder modülü bir **entry/preview surface**'dür; ayrı bir builder engine değildir.

### F. Günün En Güçlü İstatistik / Trend Kartları
Bugünkü maçlardan istatistiksel olarak en dikkat çekici pattern'ler.

Kullanıcının verdiği örnek:
- “Brezilya son 5 maçın 4'ünü kazandı”
- ilgili maç;
- oran;
- güven/reliability derecesi;
- kısa istatistik;
- `+` ile betslip'e ekleme.

Bu kartlarda raw historical stat ile model forecast açıkça ayrılmalıdır.

## 2.4 Global Date / Time Scope Selector

Prediction-oriented ve tarih/zaman filtresi anlamlı olan diğer CalibraXI yüzeylerinde ortak bir **Date / Time Scope Selector** bulunacaktır.

### Preset date scopes
Minimum preset set:
- **Today**
- **Tomorrow**
- **This Weekend**
- **Next 7 Days**
- **Custom Date Span** — kullanıcı başlangıç ve bitiş tarihini kendisi seçebilir.

### Rolling kickoff windows
Kullanıcı ayrıca takvim günü yerine, bulunduğu andan itibaren başlayacak maçları filtreleyebilir:
- **Starting within 3 hours**
- **Starting within 6 hours**
- **Starting within 12 hours**

Buradaki anlam: “3 saat sonra başlayan maçlar” değil, **şu andan itibaren önümüzdeki 3 / 6 / 12 saat içinde kickoff yapacak maçlar**.

### Uygulanacağı yüzeyler
Bu kontrol, semantik olarak uygun olduğu ölçüde:
- Predictions;
- Projections;
- Fixtures;
- Value / market opportunity yüzeyleri;
- günlük statistics/streak discovery;
- date-scoped player/team prop yüzeyleri;
- ilgili ranking/leaderboard görünümleri
üzerinde tekrar kullanılabilir.

Her sayfada zorunlu değildir. Zaman filtresinin anlam taşımadığı season-long veya competition-long bir tabloya yapay olarak eklenmez.

### Davranış kuralları
- Kullanıcının timezone'u görünür ve tutarlı şekilde uygulanır.
- Custom range inclusive/exclusive sınırları teknik sözleşmede kesinleştirilir.
- Bir overview kartından `View All` ile alt sayfaya geçildiğinde aktif date/time scope mümkün olduğunca korunur.
- Filter state URL/shareable state olarak taşınabilecek şekilde tasarlanmalıdır.
- Sayfa `Today` seçiliyken midnight/timezone değişimlerinde sessiz semantic drift oluşmamalıdır.
- Rolling 3/6/12-hour scopes gerçek kickoff zamanına dayanır; `Today` ile aynı şey değildir.

## 2.5 Collapsible Live Match Tracker

Kullanıcının sağladığı xGuara referansındaki gibi, **ana navigasyonun hemen altında yatay ilerleyen bir Live Match Tracker şeridi** bulunacaktır.

Referanstan alınan davranış fikri:
- tek satırlık yatay ticker;
- eşzamanlı live maçların art arda gösterilmesi;
- maçlar arasında league/competition context;
- score/status bilgisinin hızlı taranabilmesi;
- viewport genişliğinden fazla içerikte yatay hareket/scroll.

Referansın koyu renkleri yeni CalibraXI tasarım yönü değildir. Tracker **CalibraXI light theme** içinde yeniden tasarlanacaktır.

### Tracker içeriği
Her live item en az:
- competition / league;
- home team;
- away team;
- current score;
- live status / minute veya period;
- mümkün olduğunda event state
gösterebilir.

Bir item'a tıklamak ilgili fixture/live match detail yüzeyine götürebilir.

### Aç / kapa
Tracker:
- kullanıcı tarafından **collapse / expand** edilebilir;
- kapatıldığında dashboard'un dikey alanını tüketmez;
- kullanıcı tercihinin session/local profile seviyesinde hatırlanması desteklenebilir;
- hiç live maç yoksa boş bir ticker göstermek yerine gizlenebilir veya kompakt `No live matches` state'i kullanılabilir.

### Hareket ve erişilebilirlik
- Otomatik kayan içerik kullanıcı tarafından pause edilebilir.
- Hover/focus sırasında hareket durdurulabilir.
- Keyboard ve touch ile manuel yatay gezinme desteklenir.
- Motion-reduction tercihine saygı duyulur.
- Score değişimleri görsel olarak belirtilebilir fakat gereksiz flashing kullanılmaz.

### Analitik sınır
Live Tracker operasyonel/live fixture state gösterir. Bir live score update:
- mevcut PRE_MATCH Forecast'ı mutate etmez;
- PRE_MATCH ve LIVE Run Context'lerini birleştirmez;
- live analytical output varsa yalnızca ayrı LIVE context üzerinden gösterilir.

## 2.6 Homepage Composition — İlk 30 Saniye / LOCKED WORKING ORDER

Ana sayfanın görevi bütün CalibraXI'ı tek ekrana sıkıştırmak değildir. İlk 30 saniyede kullanıcıya beş sorunun cevabını vermelidir:

1. **Bugün / seçtiğim zaman aralığında ne oynanıyor?**
2. **CalibraXI bugün ne öngörüyor?**
3. **En dikkat çekici takım / form / güç değişimleri neler?**
4. **Piyasa nerede farklı fiyatlıyor veya hareket ediyor?**
5. **İlgilendiğim seçimi nasıl inceleyip Studio/Betslip'e taşıyabilirim?**

Bu nedenle default public homepage aşağıdaki sırayı kullanır.

### Layer 0 — Optional Micro Announcement Strip

Sayfanın en üstündeki eski “ufak yatay tanıtım banner'ı” requirement'ı korunur fakat bu alan büyük marketing hero'ya dönüşmez.

Örnek kullanım:
- `Football, Calibrated.`
- yeni feature duyurusu;
- önemli methodology/model release notu;
- Premium veya Track Record entry;
- data/product announcement.

Kurallar:
- yaklaşık tek satırlık micro strip;
- dismissible olabilir;
- kritik günlük data burada taşınmaz;
- Today's Brief ile aynı işi yapmaz.

### Layer 1 — Primary Header

```text
CALIBRA XI

Matches | Projections | Stats | Markets | Studio | Track Record

Search | Brief | Notifications | My CalibraXI | Betslip
```

Logo `/` dashboard'a döner.

Header sticky olabilir; scroll sırasında vertical footprint minimum tutulur.

### Layer 2 — Collapsible Live Match Tracker

Primary header'ın hemen altında:

```text
LIVE  ●
Premier League  ARS 2–1 LIV  67'
La Liga         BET 0–0 RMA  31'
...
```

Tracker tüm homepage içeriğinden semantik olarak ayrıdır ve collapse edilebilir.

### Layer 3 — Today's Brief / Conditional First-Hour Surface

Kullanıcının gün içindeki ilk ziyaretinden sonra yaklaşık 60 dakika boyunca görünür.

Recommended compact form:

```text
TODAY'S BRIEF
84 fixtures today
27 full fixture projections
5 notable power movers
8 significant market movements
3 new high-quality Recommendations
```

Altında 2–4 kısa deep-link bulunabilir.

Örnek:
- `Largest Power Move →`
- `Top Fixture Projection →`
- `Biggest Odds Move →`

Bu alan 60 dakika sonra ana layout'tan kalkar. Kalktığında aşağıdaki içerik yukarı taşınır; boş alan bırakılmaz.

### Layer 4 — Daily Scope Bar

Bugünün günlük karar yüzeyleri için ortak context:

```text
Today | Tomorrow | Weekend | Next 7 Days | Custom
Starting: 3H | 6H | 12H
Competition ▼
Timezone
```

Bu scope homepage'teki:
- Fixtures;
- Top Projections;
- Daily Angles;
- Markets;
- Studio daily presets
gibi date-driven alanları etkiler.

**Power Rankings ve season-level leaderboards bu scope'a körlemesine bağlanmaz.** Kendi timeframe/season kontrollerini kullanır.

### Layer 5 — Daily Pulse / Above-the-Fold Core

Desktop'ta ana daily area 12-column grid olarak düşünülür.

#### A. Today's Fixtures — dominant module

Yaklaşık grid'in en büyük parçası.

Gösterim:
- kickoff;
- competition;
- gerçek team crests;
- teams;
- match state;
- compact supported projection hints;
- Watch;
- Match Center entry.

Default görünümde bütün 80–100 maçı göstermeye çalışmaz.

Önce:
- takip edilen / önemli competition'lar;
- yakın kickoff;
- projection availability;
- ürün curation policy
ile scan-friendly subset gösterilir.

Alt CTA:

`View all matches →`

#### B. Today's Top Projection

Fixture panelinin yanında daha küçük fakat görsel olarak güçlü panel.

İçerik:
- fixture;
- real team identity;
- market / selection;
- Forecast probability;
- Reliability presentation;
- odds / edge context uygun olduğunda;
- `Why this projection?`;
- `Open Match Center`;
- `+` / Studio action.

Bu kart “kazandıracak seçim” dili kullanmaz.

#### C. Form & Power Movers

Aynı first-screen cluster içinde compact panel.

Örnek:
- biggest Power Ranking riser;
- strongest ATT improvement;
- notable DEF decline;
- in-form team;
- relevant upcoming fixture.

Böylece kullanıcı daha ilk viewport'ta:
**fixture + model + form/power** üçlüsünü görür.

### Layer 6 — Top Projections Board

Daily Pulse sonrası daha analitik tarama alanı.

Önerilen görünüm:
- Top Fixture Projections;
- Form Edges;
- Player Props;
- gerektiğinde tabs/chips.

Her kategori sınırlı sayıda item gösterir.

CTA:
- `View all projections`
- `Open Projection Explorer`

Bu alan `/projections` hub'ın homepage preview'üdür; aynı sistemi tekrar implement etmez.

### Layer 7 — Today's Angles

Kullanıcının ilk tarifindeki “günün en iyi istatistiğine sahip olanlar + oran + güven derecesi” burada yaşar.

Kart tipleri açıkça etiketlenir:

- `STAT TREND`
- `MODEL FORECAST`
- `MARKET EDGE`
- `FORM EDGE`

Örnek:

```text
BRAZIL
Won 4 of last 5
vs Australia

Historical trend: 4/5
Model context: ...
Best current odds: ...
Reliability: ...
```

Raw historical stat hiçbir zaman model Forecast ile aynı alanmış gibi gösterilmez.

### Layer 8 — Markets Snapshot

Homepage Markets preview:

Sol:
**Value / Model-vs-Market**

Sağ:
**Odds Movers**

Örnek metrics:
- opening → current;
- best available odds;
- price move;
- model probability;
- market implied probability;
- edge state.

CTA:
- `View Markets`
- `View Odds Movement`

### Layer 9 — Power Rankings

League-tabbed büyük widget.

Örnek:

```text
Premier League ▼

#  TEAM       ATT   DEF   OVR    Δ
1  Arsenal    ...
2  Liverpool  ...
3  City       ...
```

Yanında veya alt bölümde:
- Biggest Risers;
- Biggest Fallers;
- OVR movement;
- sparkline.

`View full rankings → /stats/power-rankings`

### Layer 10 — CalibraXI Studio Preview

Homepage'de tek Studio preview bulunur.

Mode tabs:

```text
Daily Cross-Match | Daily Same-Match
```

Gösterim:
- legs;
- fixture/selection;
- individual odds;
- combined odds;
- dependency/reliability context;
- `Open in Studio`;
- `Add all to Betslip`.

Manual Builder homepage'e gömülmez; tam Studio'da açılır.

### Layer 11 — Transparency Snapshot

Studio sonrasında küçük fakat görünür bir Track Record preview önerilir.

Bu alan satış banner'ı değildir.

Örnek:

```text
TRACK RECORD — Published Recommendations — Last 30 Days
N=184 | Hit Rate ... | Avg Odds ... | ROI ... | Yield ...
```

Kurallar:
- population açık;
- period açık;
- sample açık;
- cherry-picked “best streak” default olarak kullanılmaz;
- `View full Track Record →`.

Bu yüzey kullanıcıya Studio kullanmadan önce veya kullandıktan hemen sonra CalibraXI'ın tarihsel performansını doğrulama yolu verir.

### Layer 12 — Statistics Discovery

Bu noktadan sonra homepage günlük karar dashboard'undan daha geniş statistical discovery alanına geçer.

#### Row A
- Player Leaders
- Team Leaders

#### Row B
- Streaks
- Over / Under Radar

#### Row C
- BTTS Radar
- Corners / Cards / diğer supported trends

Her widget:
- sınırlı top entries;
- relevant period;
- competition context;
- `View All`
kullanır.

Bu bölüm kullanıcıyı:
- Player Page;
- Team Page;
- Competition Page;
- Stats subpages
yüzeylerine dağıtır.

### Layer 13 — Personalized Continuation / Logged-in Only

Login olmuş kullanıcı için alt bölümde küçük bir **Your CalibraXI** continuation alanı bulunabilir.

Örnek:
- watched fixtures;
- open simulation bets;
- strategy alerts;
- saved projection filters;
- recently viewed Match Centers.

Bu, `/my` terminalinin yerine geçmez.

Anonymous kullanıcıya bu section gösterilmez.

### Layer 14 — Footer / Trust Layer

Footer:
- Methodology;
- Track Record;
- Responsible Use;
- Pricing;
- About;
- Terms;
- Privacy;
- data/legal information
gibi trust/support entry'lerini taşır.

## 2.7 Homepage Visual Rhythm

Ana sayfada her widget aynı büyüklükte “dashboard card” görünümüne sokulmayacaktır.

Önerilen ritim:

```text
FULL / DOMINANT
Daily Pulse

WIDE
Top Projections

2-COLUMN
Today's Angles + Markets

WIDE TABLE
Power Rankings

FEATURE MODULE
Studio

THIN PROOF STRIP
Track Record

2x2 / 3x2 DISCOVERY GRID
Stats
```

Bu yapı admin paneli hissini azaltır.

Her bölüm:
- farklı bilgi yoğunluğu;
- farklı visual hierarchy;
- kontrollü whitespace;
- gerçek futbol kimlik varlıkları
kullanabilir.

## 2.8 Betslip ile Homepage Layout Davranışı

Large desktop:
- Betslip pinned açıkken ana content daralabilir;
- çok geniş ekranlarda dedicated right column kullanılır.

Medium desktop:
- Betslip overlay/drawer olabilir;
- homepage grid kalıcı olarak ezilmez.

Mobile:
- Betslip bottom/full-height sheet.

Betslip açık olduğu için Today's Fixtures veya Power Rankings okunamaz hale gelmemelidir.

## 2.9 Üç Olası Homepage Yaklaşımı ve Karar

CalibraXI için üç mantıklı yaklaşım vardır.

### Option A — Command Center / RECOMMENDED

Önce:
- Fixtures;
- Top Projection;
- Form/Power;
- Projections;
- Markets;
- Studio;
- Stats.

Avantaj:
- ürünün bütün değer zincirini ilk ziyarette anlaşılır kılar;
- scan-friendly;
- profesyonel;
- homepage'in “sadece tahmin listesi” olmasını engeller.

**Canonical default olarak bu yaklaşım seçilmiştir.**

### Option B — Match-First Stream

Ana sayfanın büyük çoğunluğu fixture listesi olur; projections ve stats maçların içine gömülür.

Avantaj:
- futbol fikstürü kullanan genel kullanıcı için çok sezgiseldir.

Dezavantaj:
- CalibraXI'ın farklılaştırıcı projection/market/analytics yüzeyleri aşağı gömülür;
- generic livescore/fixture sitesi hissine yaklaşır.

Bu fikir reddedilmez; **`/matches` sayfasının davranış modeli olarak kullanılır.**

### Option C — Personalized Terminal

Ana sayfa kullanıcının:
- favori ligleri;
- watchlist'i;
- strategy alerts;
- bankroll;
- saved filters
üzerinden tamamen kişiselleşir.

Avantaj:
- yüksek retention;
- returning user için çok güçlü.

Dezavantaj:
- anonymous/yeni kullanıcıya ürünü anlatamaz;
- erken dönemde cold-start sorunu yaratır;
- public homepage'i parçalayabilir.

Bu fikir **My CalibraXI + future logged-in personalization layer** olarak korunur; launch default homepage olmaz.

### Sonuç

CalibraXI tek homepage üzerinde üç ayrı mode oluşturmaz.

- **Home = Command Center**
- **Matches = Match-First**
- **My CalibraXI = Personalized Terminal**

Böylece üç iyi fikri birbirine karıştırmak yerine her birini en doğru surface'e yerleştiririz.

## 2.10 İlk Viewport İçin Working Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ optional micro announcement / Football, Calibrated.                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ CALIBRA XI   Matches Projections Stats Markets Studio Track Record   ● ● ◎ │
├──────────────────────────────────────────────────────────────────────────────┤
│ LIVE  Arsenal 2–1 Liverpool 67'  |  Milan 0–0 Roma 31'  | ...          ˄   │
├──────────────────────────────────────────────────────────────────────────────┤
│ TODAY'S BRIEF — first-hour only                              Dismiss          │
│ 84 fixtures · 27 projections · 5 power movers · 8 market moves              │
├──────────────────────────────────────────────────────────────────────────────┤
│ Today Tomorrow Weekend Next 7D Custom | Next 3H 6H 12H | Competition ▼      │
├───────────────────────────────────────────────┬──────────────────────────────┤
│ TODAY'S FIXTURES                              │ TOP PROJECTION               │
│                                               │                              │
│ 18:00 Arsenal  vs Liverpool                   │ Arsenal vs Liverpool         │
│ 19:30 Milan    vs Roma                        │ Over 2.5                     │
│ 20:00 ...                                     │ Probability ...              │
│                                               │ Reliability ...              │
│ View all matches →                            │ Why?  Open Match  +          │
├───────────────────────────────────────────────┼──────────────────────────────┤
│                                               │ FORM / POWER MOVERS          │
│                                               │ 1. ...                       │
│                                               │ 2. ...                       │
└───────────────────────────────────────────────┴──────────────────────────────┘
```

Today's Brief 60 dakika sonra kalkınca `Daily Scope Bar + Daily Pulse` yukarı taşınır.

---

# 3. Projections Information Architecture — FULL WORKING ARCHITECTURE

CalibraXI'ın **Projections** alanı ürünün model-output araştırma merkezidir.

Kullanıcı-facing dilde `Projection`, modelin bir fixture/team/player/competition hakkında ürettiği olasılık çıktılarının ürün sunum terimidir.

**Canonical analytical domain'de asıl otorite `Forecast` olarak kalır.**

Bu ayrım önemlidir:

```text
Forecast
= canonical analytical artifact

Projection
= kullanıcının Forecast'ı gördüğü product/read presentation
```

UI'da `Projection` dememiz yeni probability üretme veya Forecast semantics'ini değiştirme yetkisi vermez.

## 3.1 Projections Product Map

Canonical projection surface seti:

```text
/projections
├── /fixtures
├── /form-edges
├── /player-props
├── /team-outrights
├── /top-10
└── /explore
```

Kullanıcıya sunulan isimler:

- **Fixture Projections**
- **Form Edges**
- **Player Props**
- **Team Outrights**
- **Top 10**
- **Projection Explorer**

`/projections` bunların overview/discovery hub'ıdır.

`/projections/explore` ise power-user filtering/screening yüzeyidir.

## 3.2 `/projections` — Hub'ın Görevi

Projections Hub tek bir dev sonuç tablosu değildir.

İlk 20–30 saniyede kullanıcı şu sorulara cevap almalıdır:

1. Seçtiğim zaman aralığında kaç fixture için projection var?
2. Bugün hangi fixture projection'ları öne çıkıyor?
3. Form/state açısından en dikkat çekici eşleşmeler hangileri?
4. Hangi oyuncu props'ları mevcut?
5. Hangi projection'larda piyasa ile anlamlı fark var?
6. Daha spesifik bir şey arıyorsam nasıl filtreleyeceğim?

Hub'ın görevi **discovery + routing**'dir.

Derin filtering Explorer'a, fixture-specific araştırma Match Center'a gider.

## 3.3 Projections Hub — Vertical Composition

Default desktop sırası:

```text
Primary Header
Live Match Tracker
Projection Header
Date / Time Scope
Projection Family Navigation
Top 10 Preview
Fixture Projections
Form Edges
Player Props
Team Outrights
Model vs Market Preview
Projection Explorer CTA / compact query
Saved Views (logged-in)
Footer / methodology
```

Her modül aynı card template'e zorlanmaz.

### 3.3.1 Projection Header

```text
PROJECTIONS
Model outputs across fixtures, players and competitions.

[ Open Projection Explorer ]
```

Yanında yalnızca gerçek read state'ten hesaplanmış compact summary counts bulunabilir:

```text
Fixtures with projections: ...
Available projection targets: ...
Competitions covered: ...
```

`High Confidence` gibi kullanıcı-facing counts yalnızca Confidence specification gerçekten dondurulduğunda kullanılabilir.

### 3.3.2 Date / Time Scope

Fixture-driven projection aileleri için:

```text
Today
Tomorrow
This Weekend
Next 7 Days
Custom

Starting within:
3H
6H
12H
```

Ek compact filters:
- competition;
- country;
- projection family.

Bu context aşağıdaki date-driven hub modüllerine aktarılır.

### 3.3.3 Projection Family Navigation

Hub'ın üst kısmında secondary chips/tabs:

```text
Overview
Fixtures
Form Edges
Player Props
Team Outrights
Top 10
Explore
```

Bu component primary site navigation değildir; yalnızca Projections product-local navigation'dır.

## 3.4 Top 10 Projections — Hub Preview

Hub'ın ilk güçlü model-output yüzeyi **Top 10** preview olabilir.

Ama `Top 10 = en yüksek probability` değildir.

Ayrıca `Top 10 = Best Bets` de değildir.

Top 10 sıralaması ayrı versioned **Projection Curation Policy** tarafından belirlenmelidir.

Policy gelecekte şu tür governed girdileri kullanabilir:
- Forecast Availability;
- probability;
- Reliability evidence/summary;
- projection family;
- competition/product scope;
- duplicate/diversity controls;
- price/edge context yalnızca ilgili Top 10 mode'unda;
- publication eligibility;
- freshness/currentness state.

**Kesin ranking formülü bu ürün dokümanında seçilmez.**

`TOP PROJECTION` bir **Curation** label'ıdır; Recommendation, Daily Pick veya `Best Bet` değildir. Curation ve Recommendation ayrımı, Candidate Population, policy/version, currentness, publication ve historical lineage semantics'i `CalibraXI-Analytics-Architecture.md` içinde canonical olarak tanımlanmıştır. Bir item ancak ayrı immutable Recommendation Decision + Publication Fact varsa açık `RECOMMENDATION` label'ı taşıyabilir.

### Top 10 Card

Her item:

```text
#1

Premier League · 20:00
[ARS] Arsenal vs Liverpool [LIV]

OVER 2.5
Model Probability  64%
Reliability        ...
Best Odds          1.78      (if market context exists)
Market             56.2%     (if compatible)
Edge               +7.8pp    (if governed Signal/valuation exists)

Why?
Open Match
+
```

Ranking numarası probability score değildir.

### Top 10 View All

`View Top 10 → /projections/top-10`

Dedicated page:
- selected date scope;
- exact curation population;
- rank reason/context;
- methodology link
gösterebilir.

## 3.5 Fixture Projections — Hub Preview

Route:
`/projections/fixtures`

Hub preview 4–8 fixture gösterebilir.

Amaç tek bir market listesi göstermek yerine **fixture-level projection overview** sağlamaktır.

### Fixture Projection Card

```text
Premier League · 20:00

[ARS] Arsenal
      vs
[LIV] Liverpool

1        X        2
48%      27%      25%

O2.5     61%
BTTS     58%

Reliability ...
[Open Match Center] [Why?] [+]
```

Compact card:
- team crests;
- kickoff;
- competition;
- key coherent market summaries;
- availability;
- Reliability presentation;
- optional market context.

### Dedicated Fixture Projections Page

`/projections/fixtures` default olarak fixtures'ı:
1. date;
2. competition;
3. kickoff
mantığıyla gruplar.

Views:

```text
Cards
Compact Table
```

Desktop power-user için Compact Table desteklenebilir.

Örnek columns:

```text
Time
Fixture
1
X
2
O2.5
BTTS
Reliability
Market Context
Actions
```

Bir market probability yoksa `—`, `Unsupported`, `Unavailable` veya uygun explicit state gösterilir; sahte `0%` kullanılmaz.

## 3.6 Form Edges

Route:
`/projections/form-edges`

**Form Edge Forecast değildir.**
**Form Edge Market Edge değildir.**

Form Edge:
> current/recent team state, opponent-adjusted form veya matchup evidence içinde ürün açısından anlamlı bir fark/pattern'in keşif objesi.

Örnek:

```text
FORM EDGE

Arsenal attacking state ↑
Liverpool away defensive state ↓

Recent window: ...
Opponent-adjusted: ...
Relevant fixture: Arsenal vs Liverpool

Linked projection:
O2.5 64%

[Open Match] [Explain]
```

### Form Edge classifications

Potansiyel:
- attack form edge;
- defence form edge;
- home/away split edge;
- power momentum;
- scoring/conceding state;
- shot/SOT process;
- rest/schedule state;
- player availability impact
gibi semantic classes.

Bir Form Edge modelin gerçekten kullandığı evidence ile ilişkiliyse bunu açıklayabilir.

Sadece keşif/trend ise:
`DATA TREND`

olarak etiketlenir.

### Form Edge Dedicated Page

Filters:
- date/time;
- competition;
- team;
- edge class;
- direction;
- recent window;
- linked projection family;
- Reliability relation varsa.

Sort:
- default curated;
- kickoff;
- magnitude yalnızca metric semantic olarak karşılaştırılabilir ise.

## 3.7 Player Props

Route:
`/projections/player-props`

Player Props, player stat leaderboards'dan ayrıdır.

**Leaderboard = observed historical performance.**
**Player Prop Projection = future event probability / distribution.**

### Player Prop Card

```text
[PLAYER PHOTO]
Bukayo Saka
Arsenal · vs Liverpool · 20:00

SHOTS ON TARGET
Line: 1.5

Over 1.5     57%
Under 1.5    43%

Expected/confirmed starter: ...
Minutes context: ...
Reliability: ...
Best Odds: ...

[Why?] [Player Page] [Match Center] [+]
```

### Prop families

Data/model coverage sağlandıkça:
- shots;
- shots on target;
- goals;
- assists;
- goal involvement;
- cards;
- tackles;
- passes;
- chances created
ve başka player-event families.

UI yalnızca desteklenen family'leri gösterir.

### Lineup dependency

Player prop özellikle lineup/minutes information'a duyarlı olabilir.

Kullanıcıya:
- expected starter;
- confirmed starter;
- bench;
- minutes uncertainty
uygun evidence varsa gösterilebilir.

Lineup değişimi yeni Forecast/Run yaratırsa eski prop silently update edilmez.

### Dedicated Player Props Page

Grouping options:
- by fixture;
- by player;
- by prop type.

Filters:
- date/time;
- competition;
- team;
- player;
- position;
- prop family;
- line;
- probability;
- Reliability;
- odds;
- market edge.

## 3.8 Team Outright Projections

Route:
`/projections/team-outrights`

Bu family fixture-horizon değil, competition/season-horizon projection'ları için ayrılmıştır.

Potential examples:
- competition winner;
- top-N finish;
- qualification;
- relegation;
- group progression
gibi team-level longer-horizon outcomes.

**Bu örneklerin production support'u ayrı model/Forecast Target coverage'ına bağlıdır.**

### Date filter exception

`Today / Tomorrow / Next 3H` gibi kickoff scope'ları Team Outrights için anlamsızdır.

Bunun yerine:
- competition;
- season;
- as-of date;
- projection target
filters kullanılır.

Bu istisna global date filter'ın körlemesine bütün product'a uygulanmaması prensibini korur.

### Outright card

```text
Premier League 2026/27

[ARSENAL CREST]
Arsenal

TITLE
Probability 31%

TOP 4
Probability 72%

As of: ...
Reliability: ...

[Competition] [Team] [History]
```

Market outright prices varsa ayrı market context olarak gösterilebilir.

## 3.9 Model vs Market Preview

Hub içinde küçük bir **Model vs Market** preview bulunabilir.

Bu bölüm `/markets/value` sayfasının kopyası değildir.

Ama projection araştırması sırasında:
- model probability;
- current compatible market probability;
- difference;
- Signal state
varsa gösterilebilir.

CTA:

`Explore Market Edges → /markets/value`

Bu separation korunur:

```text
Projections
= Forecast-first

Markets
= price-first
```

## 3.10 Projection Explorer — Canonical Dedicated Surface

Canonical route:
**`/projections/explore`**

Explorer CalibraXI'ın **projection screener**'ıdır.

Kullanıcı hazır editorial/curated listeler yerine supported projection universe içinde kendi araştırmasını yapar.

### 3.10.1 Explorer Layout

Desktop:

```text
┌───────────────────────┬──────────────────────────────────────────────┐
│ FILTERS               │ RESULTS                                      │
│                       │                                              │
│ Date                  │ 128 matching projections                    │
│ Competition           │ Sort: Curated ▼                             │
│ Family                │ View: Compact / Cards                       │
│ Market                │                                              │
│ Probability           │ [result]                                     │
│ Reliability           │ [result]                                     │
│ Odds                  │ [result]                                     │
│ Edge                  │ ...                                          │
│ ...                   │                                              │
└───────────────────────┴──────────────────────────────────────────────┘
```

Large desktop filter rail sticky olabilir.

Tablet/mobile:
- filters button;
- full-height filter sheet;
- active filter chips results'ın üstünde.

## 3.11 Explorer Filter Taxonomy

Filtreler tek dev liste yerine semantic groups halinde düzenlenir.

### A. Time & Fixture Context

- Today;
- Tomorrow;
- Weekend;
- Next 7 Days;
- Custom Date Span;
- Next 3H / 6H / 12H;
- kickoff time range;
- pre-match only.

### B. Competition

- country;
- competition;
- followed competitions;
- competition type.

### C. Entity

- team;
- opponent;
- player;
- position;
- home/away.

### D. Projection

- projection family;
- market;
- selection;
- line;
- period;
- player prop type;
- Forecast Availability.

### E. Probability

- minimum;
- maximum;
- range presets.

Probability bir quality score değildir; sadece model likelihood filtresidir.

### F. Reliability

Yalnızca governed user-facing Reliability/Confidence representation ile:
- allowed bands/classes;
- minimum required evidence class
gibi filters.

UI kendi scalar Reliability score'unu üretmez.

### G. Market Context

Market evidence available olduğunda:
- min odds;
- max odds;
- bookmaker/source availability;
- min edge;
- max edge;
- Signal eligibility/state.

`Market Edge` olmayan Forecast Explorer'dan kaybolmak zorunda değildir.

### H. Product State

- published projection;
- Signal available;
- Recommendation available;
- watched only;
- saved entities.

## 3.12 Explorer Filter Dependency Rules

Bütün filters her projection family için anlamlı değildir.

Örnek:
- `Player Position` fixture 1X2 için gösterilmez.
- `Line 1.5` yalnızca line-based markette anlamlıdır.
- `Next 3H` Team Outright için kullanılmaz.
- `Odds 1.50–2.00` market observation olmayan Forecast'ı otomatik yanlış/zero olarak değerlendirmez.

Explorer seçilen family'ye göre filters'ı contextual olarak açıp kapatır.

Bu davranış complexity'yi ciddi şekilde azaltır.

## 3.13 Explorer Query State

Explorer state URL'de temsil edilir.

Örnek conceptual URL:

```text
/projections/explore
?range=next-12h
&competition=premier-league
&market=over-2-5
&pmin=0.65
&reliability=high
&oddsMin=1.50
&oddsMax=2.20
```

Exact parameter contract Engineering aşamasında tanımlanır.

Ama ürün requirement'ı:
- bookmarkable;
- shareable;
- browser back/forward compatible
olmasıdır.

## 3.14 Explorer Result Views

İki ana görünüm önerilir.

### Compact Table

Power user / desktop.

Possible columns:
- kickoff;
- fixture/entity;
- market;
- selection;
- probability;
- Reliability;
- odds;
- edge;
- state;
- actions.

### Cards

Visual / responsive.

Gerçek team crests ve player photos daha görünür.

User preference hatırlanabilir.

## 3.15 Explorer Sorting

Allowed working sort modes:

- **Curated / Relevance** — default;
- kickoff soonest;
- probability high → low;
- probability low → high;
- odds high → low;
- edge high → low, yalnızca compatible market/Signal population'da;
- recent/currently updated read order ancak currentness authority yerine geçmez.

`Reliability high → low` ancak bands/classes order'ı governed ve comparable olduğunda eklenebilir.

### Sorting ≠ Recommendation

Bir sonucu probability veya edge'e göre sıralamak:
- Recommendation üretmez;
- `Best Bet` anlamına gelmez;
- curation/ranking authority'yi bypass etmez.

`Today's Top Projection` ve `Top 10` governed Curation output'larıdır. User sorting veya rank sonucu public Recommendation/Track Record population'a giremez; Recommendation language için ayrı Recommendation Decision gerekir.

## 3.16 Result Card Semantic Labels

Her Explorer result type açıkça işaretlenir:

```text
FORECAST
FORM EDGE
MARKET EDGE
SIGNAL
RECOMMENDATION
PLAYER PROP
OUTRIGHT
```

Bir object aynı anda birden fazla upstream/downstream context içerebilir fakat primary label net olmalıdır.

Örnek:
- Forecast card üzerinde `Signal available` secondary badge;
- Recommendation card'ın altında linked Forecast.

## 3.17 Projection Detail Interaction

Kullanıcı sonucu iki seviyede inceleyebilir.

### Quick Expand / Drawer

Page'den çıkmadan:
- probability;
- Reliability;
- key drivers;
- current market context;
- Forecast cutoff;
- actions.

### Open Canonical Context

Fixture projection:
→ Match Center `#projections`

Player prop:
→ Match Center Player Props context veya Player Page.

Team outright:
→ Competition/Team entity.

Market Edge:
→ Match Center `#markets` veya `/markets/value`.

Quick detail canonical deep page'in yerine geçmez.

## 3.18 Why This Projection? — Explorer Integration

Her Forecast-supported result için `Why?` action.

Compact explanation:
- 3–5 top evidence drivers;
- relevant caveat;
- Forecast cutoff;
- Reliability context.

`View full analysis`:
→ Match Center / relevant entity deep page.

Explainability modelin kullanmadığı stat'leri pazarlama gerekçesi olarak ekleyemez.

## 3.19 Multi-Select Research Mode

Explorer'da optional **Select** mode bulunabilir.

Kullanıcı birkaç compatible projection seçebilir.

Actions:
- Compare;
- Watch;
- Open selected in Studio.

### Studio safety

`Open selected in Studio`:
- selections'ı taslak olarak taşır;
- Studio compatibility/dependency validation yapar;
- Explorer combined probability hesaplamaz.

Search result'taki bütün projections'ı tek tıkla kupona dolduran `Add All` davranışı default olmayacaktır.

## 3.20 Saved Views

Login olan kullanıcı Explorer query'sini kaydedebilir.

Örnek:

```text
Name:
Premier League O2.5 High Probability

Filters:
Next 12H
Premier League
O2.5
P >= 65%
Odds 1.50–2.20
```

Saved View:
- `/my/saved`;
- My CalibraXI overview;
- Explorer quick access
alanlarında görünür.

Saved View analytical artifact değildir; user preference/query definition'dır.

## 3.21 Saved View → Smart Alert

Kullanıcı saved view için alert açabilir.

Örnek:

> Yeni bir projection bu filtrelere uyarsa haber ver.

Alert evaluation:
- mevcut governed projections üzerinde çalışır;
- yeni Forecast üretmez;
- stale/historical item'ı new candidate gibi bildirmez.

Kullanıcı:
- instant/in-app;
- digest;
- mute
gibi notification preferences seçebilir.

## 3.22 Empty / Unsupported / No-Current States

Explorer ve projection pages üç farklı durumu ayırır.

### No Results

Filters geçerli fakat eşleşme yok.

```text
No projections match these filters.
```

### Unsupported

Requested projection target/model coverage mevcut değil.

```text
This projection family is not supported for the selected scope.
```

### No Current Projection

Family supported fakat current valid output yok.

```text
No current projection is available.
```

Historical Forecast sessizce current yerine konmaz.

## 3.23 Projection Availability Presentation

Prominent generic `Data Freshness Badge` istemiyoruz.

Ama projection'ın kullanıcıya yanlış görünmemesi için explicit state gerektiğinde gösterilir:

- Available;
- Unsupported;
- Unavailable;
- Withheld;
- Historical;
- Research/Provisional uygun olduğunda.

Bu state product correctness içindir; ayrı “data health dashboard badge” değildir.

## 3.24 Projection Family Dedicated Page Template

`/projections/fixtures`, `/form-edges`, `/player-props`, `/top-10` aynı temel shell'i paylaşabilir:

```text
Title + context
Date/time scope if relevant
Family-specific filters
View mode
Results
Pagination / load-more
Methodology note
```

Ama family semantics korunur; tek generic schema yüzünden anlamsız filters gösterilmez.

## 3.25 Pagination / Large Result Sets

Projection Explorer sonsuz yüzlerce card render etmez.

Recommended:
- cursor-based result continuation;
- explicit `Load more` veya controlled infinite loading;
- result count/approximate count semantics API'ye göre.

Filter değiştiğinde scroll/result state predictable olmalıdır.

## 3.26 Projection Watch Behavior

User:
- fixture;
- specific projection target;
- player prop;
- saved query
takip edebilir.

Specific projection watch örneği:

```text
Arsenal vs Liverpool
Over 2.5
```

Future alert:
- new current run;
- probability threshold crossed;
- Signal state changed
gibi event'lere bağlanabilir.

## 3.27 Projection History

Current projection card'ta optional:

`View history`

kullanıcıyı Match Center History veya target-specific historical view'a götürür.

Ama current list üzerinde old run probability'leri sparkline haline getirilecekse:
- exact immutable runs;
- time axis;
- semantic comparability
korunmalıdır.

“Probability movement” odds movement ile aynı chart üzerinde anlamı karışacak şekilde çizilmemelidir.

## 3.28 Projection vs Odds Visual Separation

CalibraXI kullanıcıya iki hareketi farklı şekilde gösterir:

```text
MODEL
58% → 61%

MARKET
1.92 → 1.72
```

Bu ikisi ayrı timelines'dır.

New odds quote:
- model probability'yi değiştirmez.

New Forecast Run:
- market history'yi değiştirmez.

## 3.29 Top 10 Dedicated Page

`/projections/top-10`

Recommended structure:
- active scope;
- curation class;
- ranking methodology link;
- ranked list;
- projection family labels;
- exact probabilities;
- Reliability;
- optional market context;
- reasons.

User rank listesinde:
`#1` görür ama bunun “kesinlikle en iyi bahis” olmadığını copy/semantic design açık tutar.

Gelecekte farklı Top 10 modes:
- Overall;
- Fixture;
- Player Props;
- Model vs Market
eklenebilir.

Her mode ayrı curation population specification gerektirir.

## 3.30 Projection Explorer İlk Viewport Working Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ PROJECTIONS                                               [Saved] [Explore] │
│ Forecasts across fixtures, players and competitions                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Today Tomorrow Weekend Next 7D Custom | 3H 6H 12H | Competition ▼         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Overview | Fixtures | Form Edges | Player Props | Outrights | Top 10       │
├───────────────────────┬──────────────────────────────────────────────────────┤
│ FILTERS               │ 128 RESULTS                  Sort: Curated ▼        │
│                       │                              Cards | Compact         │
│ Time                  │                                                     │
│ Competition           │ Arsenal vs Liverpool                                │
│ Projection Family     │ O2.5                                                │
│ Market                │ Probability 64%                                     │
│ Probability           │ Reliability ...                                     │
│ Reliability           │ Odds 1.78 · Edge ...                               │
│ Odds                  │ Why?   Open Match   +                              │
│ Edge                  │ ─────────────────────────────────────────────       │
│                       │ Saka vs Liverpool                                   │
│ [Save View]           │ SOT O1.5 · 57%                                     │
│                       │ Why?   Player   Open Match   +                      │
└───────────────────────┴──────────────────────────────────────────────────────┘
```

Bu wireframe `/projections/explore` içindir.

Hub daha editorial/modüler görünür.

## 3.31 Mobile Projections

Mobile bottom nav'daki `Projections` direkt `/projections` hub'a gider.

Hub:
- horizontal family chips;
- date scope compact;
- vertically stacked modules.

Explorer:
- persistent `Filters (N)` action;
- active filter chips;
- sort;
- result cards;
- full-screen filter sheet.

Card action:
- Why;
- Watch;
- `+`;
- More.

Complex table mobile'a küçültülmez; card representation kullanılır.

## 3.32 Projection Methodology Links

Hub ve Explorer footer/context areas:
- How projections work;
- Reliability methodology;
- Market comparison methodology;
- Track Record
link'leri taşıyabilir.

Bu trust links kullanıcıyı analytical jargon ile ilk viewport'ta boğmaz.

## 3.33 Projections Non-Goals

Projections UI:
- model çalıştırmaz;
- model seçmez;
- Forecast recalibrate etmez;
- market odds'a göre Forecast değiştirmez;
- unsupported probability uydurmaz;
- historical Forecast'ı current yapmaz;
- Reliability'yi probability multiplier gibi kullanmaz;
- sorted result'ı Recommendation diye yeniden adlandırmaz;
- Form Edge'i Market Edge diye sunmaz;
- raw stat trend'i Forecast diye göstermez;
- multiple selected projections için Explorer içinde joint probability hesaplamaz;
- Studio'yu duplicate etmez.

## 3.34 Working Decision

**Canonical division:**

```text
/projections
= curated discovery hub

/projections/{family}
= focused family listing

/projections/explore
= user-driven screener

/h2h/.../{fixtureId}
= full fixture research context

/markets
= price-first market research

/studio
= combination / builder work
```

Bu bölünme CalibraXI'ın Projections alanını güçlü tutarken her işi tek sayfaya doldurmamızı engeller.

---

# 4. Persistent Right-Side Betslip

Desktop deneyiminde sağ tarafta kalıcı/persistent bir **Betslip paneli** bulunur.

## 4.1 Seçim ekleme
Analiz, recommendation veya desteklenen widget üzerindeki `+` kontrolüyle seçim eklenir.

Kullanıcı:
- seçim ekler;
- seçim çıkarır;
- oran değişimini görür;
- tekli/kombine yapı oluşturur;
- builder setini tek hareketle ekleyebilir;
- kendi manuel seçimlerini CalibraXI önerileriyle karıştırabilir.

## 4.2 Sanal bakiye

Her kullanıcı için CalibraXI içinde gerçek para olmayan bir **virtual balance / simulation bankroll** bulunur.

Amaç:
- kullanıcı kendi stratejisini test edebilsin;
- “bu sistemi 30 gün uygulasaydım ne olurdu?” sorusuna gerçek geçmiş ledger ile cevap verebilsin;
- gerçek bahis yapmadan stake davranışını simüle edebilsin;
- performansını takip edebilsin.

## 4.3 Sanal kupon

Kullanıcı sanal bakiyesinden stake girerek kuponu “place” eder.

Kaydedilecek minimum bilgiler:
- coupon/simulation id;
- creation/placement time;
- selections;
- exact odds snapshot;
- stake;
- combined odds;
- potential return;
- source/type: user-created / CalibraXI Recommendation / Daily Builder / Same-Match Builder / mixed;
- strategy tag;
- settlement result;
- realized return;
- P/L;
- bankroll before/after.

Odds daha sonra değişse bile yerleştirilmiş sanal kuponun tarihi oranı değiştirilmez.

## 4.4 Strategy Lab

Strategy Lab yalnızca kuponlara etiket koyan basit bir geçmiş ekranı olmayacaktır. Kullanıcının kendi hipotezlerini **backtest + forward simulation** ile sınayabildiği kontrollü bir araştırma alanı olacaktır.

### Strategy Rule Builder
Kullanıcı bir strategy definition oluşturabilir.

Örnek koşullar:
- Forecast probability `>= X`;
- Reliability band;
- market/selection family;
- odds min/max;
- edge/value min/max;
- competition/league;
- home/away;
- date/time horizon;
- team power differential;
- form/state conditions;
- minimum sample/data eligibility;
- CalibraXI Signal / Recommendation eligibility;
- single vs builder;
- stake rule.

### Point-in-time backtest
Backtest yalnızca ilgili tarih ve Forecast Cutoff anında gerçekten bilinen/eligible veriyi kullanır.

Yasak:
- sonradan düzeltilmiş line-up bilgisini geçmişe taşımak;
- kapanış oranını strategy o anda bunu bilmiyorsa giriş filtresi gibi kullanmak;
- bugün hesaplanan team strength'i geçmiş maçlara sanki o zaman biliniyormuş gibi uygulamak;
- yalnızca kazanan örnekleri seçmek.

### Backtest ve Forward Test ayrımı
Her strategy için performans en az iki ayrı sınıfta tutulur:
1. **Historical Backtest** — point-in-time replay üzerinden;
2. **Forward / Paper Test** — strategy oluşturulduktan sonra gerçek zamanda gelen yeni fırsatlar üzerinden.

Forward sonuç, backtest sonucuyla aynı seriymiş gibi birleştirilmez.

### Strategy Versioning
Bir strategy'nin koşulları değiştirildiğinde yeni version oluşur. Eski sonuçlar yeni kuralla yeniden etiketlenmez.

### Strategy Performance
Her version için:
- opportunities;
- executed simulations;
- hit rate;
- average odds;
- ROI/yield;
- P/L;
- max drawdown;
- bankroll curve;
- odds buckets;
- league/market breakdown;
- rolling performance;
- sample size;
- uncertainty;
- backtest vs forward gap
raporlanabilir.

### Saved Strategy ve Automation yönü
Gelecekte kullanıcı bir strategy'yi kaydedip:
- yeni eşleşme bulunduğunda alert alma;
- otomatik olarak simulation betslip'e taslak ekleme;
- yalnızca manuel onay sonrası paper bet oluşturma
seçeneklerine sahip olabilir.

Bu, gerçek bookmaker'a otomatik bahis gönderimi anlamına gelmez.

## 4.5 CalibraXI Studio — FULL WORKING ARCHITECTURE

**Canonical route:** `/studio`

CalibraXI içinde bütün combination / builder deneyimi **tek bir ürün yüzeyinde** birleşir.

Studio:
- ayrı bir Forecast engine değildir;
- ayrı bir Signal engine değildir;
- Recommendation authority değildir;
- bookmaker checkout değildir.

Studio'nun görevi:
> Canonical selections'ı, exact contract semantics'ini, dependency bilgisini, market price context'ini ve combination support'u tek çalışma alanında birleştirmek.

Bu bölüm product/UX davranışını tanımlar. Recommendation/Curation governance canonical olarak `CalibraXI-Analytics-Architecture.md` içinde tanımlanmıştır. Joint probability, dependency policy, combination settlement ve combination-level Reliability'nin target-family mathematics'i yalnızca separately validated/versioned capability olarak production'a açılabilir.

### 4.5.1 Studio'nun ürün içindeki yeri

Canonical flow:

```text
Matches / Match Center
Projections
Markets
Strategy Lab
Saved Views
Recommendations
        ↓
      STUDIO
        ↓
Combination validation
Dependency / compatibility
Probability support
Price basis
Settlement support
        ↓
Virtual Betslip
        ↓
Simulation placement
        ↓
Settlement / Performance / Track Record
```

Stats'taki raw historical metric doğrudan Studio leg'i değildir.

Örneğin:
`Arsenal son 8 maçın 7'sinde gol attı`

bir **STAT TREND**'dir.

Studio'ya eklenebilir exact selection ancak:
`Arsenal Team Total Over 0.5`
gibi exact Betting Contract / Selection context'i varsa oluşur.

### 4.5.2 Studio'daki dört farklı object birbirine karıştırılmaz

Studio product domain'de en az şu dört kavram ayrılır:

#### Selection / Leg
Bir exact Betting Contract içindeki exact selection.

#### Composition Draft
Kullanıcının Studio'da şu anda oluşturduğu mutable çalışma kompozisyonu.

#### Published Studio Composition
CalibraXI tarafından belirli zaman, policy ve price basis ile publish edilen immutable Daily Cross-Match / Daily Same-Match composition.

#### Simulation Bet
Kullanıcının Betslip üzerinden sanal stake girerek place ettiği immutable ledger object.

Ayrıca:

#### Saved Template
Yeniden kullanılabilecek yapı/rule/configuration.

Saved Template:
- placed bet değildir;
- historical quote snapshot değildir;
- Track Record sonucu değildir.

### 4.5.3 Studio Local Information Architecture

Studio içinde dört ayrı top-level ürün yaratmak yerine local navigation sade tutulur:

```text
DAILY
BUILD
SAVED
```

#### DAILY
CalibraXI'ın published Studio compositions'ı.

İçinde:
- **Cross-Match**
- **Same-Match**

switch edilir.

#### BUILD
Manual Studio workspace.

User:
- seçim ekler;
- çıkarır;
- compatibility görür;
- dependency/joint support görür;
- price basis seçer;
- composition'ı Betslip'e yollar.

#### SAVED
- saved drafts;
- templates;
- recent compositions;
- Strategy-assisted candidates
gibi user-owned material.

Strategy Lab'ın asıl yönetim merkezi yine `/my/strategies`'dir.

Bu sayede:

```text
Daily Cross-Match
Daily Same-Match
Manual Builder
Strategy Builder
```

diye dört ayrı builder page yaratılmaz.

### 4.5.4 Studio Entry Points

Studio'ya şu yüzeylerden context taşınabilir:

#### Match Center

```text
Selection
→ Open in Studio
```

Same fixture context korunur.

#### Projection Explorer

```text
Selected projections
→ Open selected in Studio
```

Explorer combined probability hesaplamaz.

#### Markets

```text
Exact market selection
→ Open in Studio
```

Market source / price context taşınabilir.

#### Recommendation

```text
Recommendation
→ Add to Studio
```

Recommendation identity korunur.

#### Strategy Lab

```text
Strategy candidate set
→ Open in Studio
```

Bunlar Studio'da user-owned draft haline gelir; Strategy candidate otomatik CalibraXI Recommendation olmaz.

### 4.5.5 Deep-Link Input Güvenliği

URL veya client state Studio'ya:

- selection ID;
- fixture ID;
- contract ID;
- market context ID;
- Recommendation/Signal reference

taşıyabilir.

Ancak Studio:
- URL'deki probability'ye;
- URL'deki odds'a;
- client tarafından gönderilen Reliability değerine
analytical truth olarak güvenmez.

Canonical read layer üzerinden identity re-resolve edilir.

Stale/deleted/incompatible input:
explicit state'e düşer.

### 4.5.6 Studio Workspace — Desktop

Large desktop working layout:

```text
┌─────────────────────┬──────────────────────────────────────┬──────────────────┐
│ SELECTION LIBRARY   │ COMPOSITION                          │ INSPECTOR        │
│                     │                                      │                  │
│ Search              │ Leg 1                                │ Compatibility    │
│ Fixtures            │ Leg 2                                │ Probability      │
│ Projections         │ Leg 3                                │ Price Basis      │
│ Markets             │                                      │ Dependency       │
│ Watchlist           │ + Add selection                      │ Settlement       │
│ Strategy Candidates │                                      │ Warnings         │
│                     │                                      │                  │
│                     │                                      │ Send to Betslip  │
└─────────────────────┴──────────────────────────────────────┴──────────────────┘
```

Global Betslip ile Inspector aynı anda iki sağ rail yaratmamalıdır.

Studio'da default:
- global Betslip collapsed olabilir;
- `Send to Betslip` sonrasında Betslip açılır.

Medium desktop:
- Selection Library drawer;
- Inspector side sheet
olarak adapte olabilir.

### 4.5.7 Selection Library

BUILD mode'da candidate discovery için:

```text
Search
Today's Matches
Projections
Signals
Recommendations
Markets
Watchlist
Recently Viewed
Strategy Candidates
```

kullanılabilir.

Library'nin görevi selection bulmaktır.

Library kendi:
- ranking;
- Forecast;
- Recommendation
otoritesini üretmez.

### 4.5.8 Leg Anatomy

Her Studio leg minimum olarak:

- fixture/event;
- competition;
- kickoff;
- exact market;
- exact line/operator;
- exact selection;
- period;
- settlement context;
- current Forecast probability varsa;
- Reliability presentation varsa;
- Signal state varsa;
- Recommendation state varsa;
- selected price;
- price source/basis;
- quote timestamp;
- source entry context
gösterebilir.

Örnek:

```text
Arsenal vs Liverpool
TOTAL GOALS — OVER 2.5

Model        61%
Reliability  ...
Signal       Eligible
Price        1.82
Source       ...
Quoted       19:42

[Why?] [Market] [Remove]
```

### 4.5.9 Entry Source ≠ Analytical Class

Studio bir leg'in nereden geldiğini de korur:

```text
Added from Match Center
Added from Projection Explorer
Added from Markets
Added from Recommendation
Added from Strategy Candidate
Manual search
```

Bu provenance:

`Added from Recommendation`

demekle

`Recommendation`

analytical status'unu birbirine karıştırmaz.

Örneğin user bir Recommendation'ı daha sonra değiştirilmiş line ile eklerse yeni leg artık original Recommendation'ın exact contract'ı olmayabilir.

### 4.5.10 Studio'ya Doğrudan Eklenemeyecek Şeyler

Aşağıdakiler exact contract'a resolve edilmeden leg olmaz:

- raw form stat;
- Power Ranking;
- streak;
- team percentile;
- generic “Arsenal güçlü” statement;
- Form Edge object;
- player leaderboard row;
- odds movement event;
- generic fixture.

Bunlar Studio'da candidate discovery context olabilir fakat leg değildir.

### 4.5.11 Combination Validation Pipeline

Her composition değişikliğinde canonical sequence:

```text
1. Resolve exact leg identities
2. Check leg availability/currentness
3. Check contract compatibility
4. Detect contradiction
5. Detect redundancy / deterministic implication
6. Resolve same-fixture grouping
7. Resolve dependency coverage
8. Resolve combination probability support
9. Resolve price basis
10. Resolve settlement support
11. Resolve composition integrity
12. Determine allowed actions
```

UI bu kontrollerin sonucunu gösterir; kontrolleri browser içinde keyfi matematikle icat etmez.

### 4.5.12 Compatibility States

Working user-facing states:

```text
Compatible
Compatible — dependent
Compatible — limited model coverage
Price-only
Research-only
Redundant
Conflicting
Unavailable
Unsupported
Needs review
```

Internal enum'lar final architecture'da farklı olabilir.

Bu states:
Probability veya Confidence score değildir.

### 4.5.13 Deterministic Contradictions

Studio bazı kombinasyonları model gerektirmeden logical olarak engelleyebilir.

Örnek:

```text
Home Win
+
Away Win
```

aynı full-time 1X2 contract'ta:
**conflicting**.

```text
BTTS Yes
+
Under 1.5
```

standard full-time goals semantics altında:
**impossible intersection**.

```text
Over 2.5
+
Under 2.5
```

same exact period:
**conflicting**.

Bu validation exact contract semantics'e bağlıdır; label string karşılaştırmasıyla yapılmaz.

### 4.5.14 Redundancy / Deterministic Implication

Bazı legs logical olarak redundant veya nested olabilir.

Örnek conceptual:

```text
Home Win
+
1X Double Chance
```

Home Win gerçekleşirse 1X zaten gerçekleşir.

Başka örnek:

```text
Over 3.5
+
Over 2.5
```

aynı period ve settlement family'de Over 3.5, Over 2.5'i imply edebilir.

Studio:
- bunun dependency olduğunu gösterir;
- bookmaker rules izin vermiyorsa block eder;
- naïve independent combination yapmaz.

### 4.5.15 Same-Match Builder — Canonical Rule

Aynı fixture'dan iki veya daha fazla leg varsa composition:

**Same-Match dependency analysis**

gerektirir.

Same-match legs için:

```text
p(A ∩ B)
```

genel olarak:

```text
p(A) × p(B)
```

değildir.

Bu nedenle component probabilities **naïf çarpılmaz**.

### 4.5.16 Same Coherence Family — Exact Joint Derivation

Bazı same-match combinations tek canonical parent distribution üzerinden exact veya deterministic biçimde türetilebilir.

Örnek Match Goals / Scoreline family:

```text
Home Win
AND
Over 2.5
```

joint home/away scoreline distribution üzerinden:

```text
sum P(home_score, away_score)
for states satisfying both selections
```

şeklinde türetilebilir.

Benzer şekilde desteklenebilecek örnekler:
- 1X2 + totals;
- BTTS + totals;
- team total + result;
- exact score derived intersections
parent semantics izin verdiğinde.

Bu:
- yeni bağımsız model değildir;
- canonical parent distribution'ın legal joint derivation'ıdır.

### 4.5.17 Cross-Family Same-Match Dependency

Örnek:

```text
Home Win
+
Over 8.5 Corners
```

Goals/Scoreline family ile Corners family farklı stochastic processes olabilir.

Başka örnek:

```text
BTTS Yes
+
Over 3.5 Cards
```

Bu durumda combined model probability yalnızca:
- validated joint model;
- validated simulation model;
- explicit dependency architecture
varsa gösterilir.

Yoksa:

```text
Combined Model Probability: Unavailable
Reason: Cross-family dependency not modeled
```

denir.

Marginals çarpılmaz.

### 4.5.18 Player Event Dependencies

Player props özellikle dependency-sensitive'dir.

Örnek:

```text
Player to Score
+
Player Shots Over 2.5
```

yüksek dependency olabilir.

```text
Player to Score
+
Team to Win
```

player event ile team score/result process arasında dependency vardır.

Lineup/minutes uncertainty de eklenir.

Bu combinations:
- player-event joint support yoksa combined probability alamaz;
- yalnızca iki individual probability var diye çarpılmaz.

### 4.5.19 Same-Match Market Price

Bir bookmaker/source exact same-game builder quote sunuyorsa:

```text
Exact Offered Combination Price
```

ayrı Market Observation / combination-price context olarak kullanılabilir.

Ancak exact combined quote yoksa:

**same-match individual leg odds çarpılıp bookmaker combined odds diye gösterilmez.**

Bu çok önemli canonical rule'dur.

Studio joint model probability biliyor olabilir fakat market combined price bilmiyor olabilir.

Bu durumda:

```text
Model joint probability: Available
Market combination price: Unavailable
```

mümkündür.

### 4.5.20 Same-Match Research-Only Composition

Joint probability var fakat compatible offered/simulation price yoksa:

```text
RESEARCH-ONLY
```

composition oluşturulabilir.

User:
- save;
- compare;
- inspect
yapabilir.

Ama price-dependent:
- EV;
- ROI projection;
- place simulation
yapılamaz.

### 4.5.21 Cross-Match Builder

Different fixture legs:

```text
Fixture A — Selection 1
Fixture B — Selection 2
Fixture C — Selection 3
```

Cross-Match mode'a girer.

Different fixtures olmak dependency'nin otomatik sıfır olduğu anlamına gelmez.

Ancak same-fixture correlation'a göre daha çok combination independence policy kapsamında değerlendirilebilir.

### 4.5.22 Cross-Match Probability

Combined probability yalnızca aşağıdaki support class'lardan biri varsa gösterilir:

1. **Exact Joint**
2. **Validated Joint / Dependency Model**
3. **Independence-Qualified**
4. **Unavailable**

`Independence-Qualified`:

> Bu exact combination scope için separate leg probabilities'in product kullanımının Combination Policy tarafından validate edilmiş olması.

Bu policy olmadan:

```text
combined_probability = ∏ p_i
```

UI'da yapılmaz.

### 4.5.23 Shared / Latent Dependency Risk

Different fixtures arasında bile potential dependency olabilir.

Örnek classes:
- same competition state;
- multi-leg tournament qualification chain;
- same team across sequential dates;
- weather/event cluster;
- season-outcome legs linked to fixture results;
- mutually conditional outright/fixture events.

Bu nedenle “different fixture = guaranteed independent” canonical rule değildir.

### 4.5.24 Combination Probability Support Classes

Working user-facing presentation:

#### FULL MODEL COVERAGE
Combined probability canonical support'a sahip.

#### PARTIAL MODEL COVERAGE
Individual legs supported fakat full joint combination probability yok.

#### PRICE-ONLY
A valid exact market/combination price mevcut olabilir fakat model joint probability yok.

#### RESEARCH-ONLY
Model joint probability olabilir fakat usable price basis yok.

#### UNSUPPORTED
Combination semantic/settlement/dependency olarak desteklenmiyor.

Bu labels exact internal enum olarak dondurulmuş sayılmaz; product semantics'tir.

### 4.5.25 Combined Probability ≠ Reliability

Örneğin:

```text
Combined probability = 34%
```

composition'ın Reliability'si değildir.

Combination-level Reliability gelecekte:
- leg evidence;
- dependency model evidence;
- joint calibration;
- applicability;
- market/price integrity
gibi faktörlerin governed değerlendirmesini gerektirir.

Bu değer:

```text
p_combined × reliability
```

gibi üretilmez.

### 4.5.26 Composition Diagnostics

Inspector transparent diagnostics gösterir:

```text
Model Coverage       Full / Partial / None
Dependency Support   Exact / Modeled / Qualified / Unresolved
Price Basis          Single Source / Exact Combo / Synthetic
Quote State          Current / Changed / Unavailable
Settlement Support   Supported / Limited / Unsupported
Recommendation       Published / None
```

Bunları tek gizli “Studio Score = 87” değerine sıkıştırmak şimdilik yasaktır.

### 4.5.27 Cross-Match Price Basis

Cross-match composition için birkaç farklı price basis olabilir.

#### Single-Source Basis

Bir source bütün legs için compatible price sunuyorsa:

```text
Source A:
Leg 1 1.80
Leg 2 1.65
Leg 3 1.72
```

simple accumulator convention altında combined quoted simulation price hesaplanabilir.

#### Best-Observed Per-Leg Basis

Her leg için farklı source'dan best observed quote seçilebilir.

Bu:

```text
SYNTHETIC BEST-PRICE SIMULATION
```

olarak açıkça işaretlenir.

Bu composition:
- tek bookmaker'da executable olduğunu iddia etmez;
- market consensus değildir.

### 4.5.28 Cross-Match Combined Price

Simple accumulator payout convention'da:

```text
combined_decimal_price = ∏ leg_decimal_prices
```

price-side payout calculation olabilir.

Ama bu:
- combined model probability değildir;
- independence kanıtı değildir;
- Recommendation değildir.

Ayrıca:
- bonus;
- boost;
- exchange commission;
- source-specific accumulator rules;
- incompatible markets
varsa formula farklı olabilir veya unsupported olur.

### 4.5.29 Exact Same-Match Quote vs Synthetic Cross-Match Price

UI bunları ayırır:

```text
EXACT COMBINATION PRICE
```

ve

```text
SYNTHETIC ACCUMULATOR PRICE
```

aynı badge değildir.

Same-match exact combined quote yokken individual odds product:
**Exact Combination Price olarak gösterilmez.**

### 4.5.30 Fair Combination Value

Combination-level fair value ancak:
- valid combined settlement semantics;
- supported combined event probability/distribution;
- compatible price convention
varsa hesaplanabilir.

Simple all-win binary event için:
`1 / p_joint`
gibi fair odds representation uygun olabilir.

Push/half-win/void/multi-state combinations:
full settlement distribution ister.

### 4.5.31 Combination EV

EV yalnızca:
- combined probability/settlement;
- exact price basis;
- valid payoff convention
varsa gösterilir.

No combined model probability:
→ EV unavailable.

No price:
→ EV unavailable.

Reliability:
→ EV'ye multiplier değildir.

### 4.5.32 Combination Settlement

Final simulation settlement leg results'ı basit win/loss'a indirgemek zorunda değildir.

Potential leg settlement:
- win;
- loss;
- push;
- void;
- half win;
- half loss;
- dead heat;
- abandoned/postponed policy result.

Combination settlement:
source/declared simulation payout rules üzerinden deterministic olmalıdır.

Same-game offered combo'nun provider settlement semantics'i cross-match accumulator'dan farklı olabilir.

### 4.5.33 Daily Studio — Cross-Match

`DAILY > Cross-Match`

CalibraXI'ın published daily cross-fixture composition alanıdır.

Bir Daily Cross-Match composition:
- exact publication identity;
- legs;
- leg Forecast lineage;
- Signal/Recommendation references where applicable;
- combination probability support class;
- dependency policy;
- price basis;
- quote timestamps;
- combination price;
- publication time;
- settlement rules;
- eventual evaluation
taşır.

### 4.5.34 Daily Studio — Same-Match

`DAILY > Same-Match`

Tek fixture içinde published composition.

Minimum publication requirements product-level olarak:
- all legs semantically compatible;
- no deterministic contradiction;
- dependency/joint method declared;
- combined probability support class visible;
- price basis visible;
- exact fixture/run references;
- publication timestamp;
- settlement support.

Eğer product bunu betting-like daily composition olarak Track Record'da ROI ile gösterecekse usable governed price basis de zorunludur.

### 4.5.35 Daily Composition Recommendation Boundary

CalibraXI tarafından:

```text
Today's Cross-Match
Today's Same-Match
```

olarak publish edilen composition arbitrary UI sort sonucu değildir.

Genuine Daily Studio publication için:
- immutable Studio Candidate Population;
- Studio Curation Decision;
- immutable Composition Recommendation Decision;
- Recommendation/Studio policy version;
- exact price, currentness, dependency/support ve publication facts
gerekir.

Individual legs'in sadece yüksek probability olması yeterli değildir.

Ayrıca:
- en yüksek edge legs;
- en yüksek Confidence legs;
- en düşük odds legs
otomatik builder oluşturmaz.

### 4.5.36 Daily Composition Diversity

Curation/Recommendation policy:
- duplicate exposure;
- same competition concentration;
- repeated team exposure;
- market-family concentration;
- dependency;
- coverage quality
gibi faktörleri explicit cap/constraint veya declared objective olarak değerlendirir.

Bu document exact optimization objective seçmez.

Studio “en çeşitli = en iyi” veya “en çok leg = en iyi” diye varsaymaz.

### 4.5.37 Manual Build

`BUILD`

User kendi leg'lerini seçer.

Manual composition:
- CalibraXI Recommendation değildir;
- Studio support diagnostics alır;
- compatible olduğunda joint/combined probability görebilir;
- market price context görebilir;
- virtual Betslip'e aktarılabilir.

User selection özgürlüğü ile CalibraXI analytical claim'i ayrıdır.

### 4.5.38 Manual Build — Unsupported Probability

User iki valid leg ekleyebilir fakat combination probability model coverage dışında olabilir.

Studio:

```text
Individual projections available.
Combined model probability is not supported.
```

der.

Buna rağmen exact combined market quote varsa:
price-only research/simulation mümkün olabilir; UI bunun model-backed bir builder olmadığını açıkça gösterir.

### 4.5.39 Strategy-Assisted Studio

Strategy Lab candidate'ları Studio'ya taşınabilir.

Flow:

```text
Saved Strategy
→ current candidates
→ select candidates
→ Open in Studio
→ compatibility/dependency validation
→ user review
→ Betslip
```

Strategy'nın rule match'i:
Recommendation değildir.

Strategy-generated candidate:
- source strategy/version;
- match time;
- rule evidence
taşır.

### 4.5.40 Saved Draft

User current composition'ı save edebilir.

Draft:
- specific legs;
- source references;
- last reviewed state
taşır.

Ancak future reopen'da:
- odds değişmiş;
- Forecast superseded;
- line closed;
- player unavailable
olabilir.

Studio saved values'i current truth gibi göstermez.

### 4.5.41 Draft Revalidation

Saved draft açıldığında:

```text
3 updates available
1 price changed
1 Forecast superseded
1 market unavailable
```

gibi diff summary gösterilebilir.

User:
`Refresh draft`

derse yeni Draft Revision oluşabilir.

Historical revision korunabilir.

### 4.5.42 Saved Template

Template:
specific historical quote'ları freeze etmek yerine reusable construction intent taşır.

Örnek:

```text
3-leg Cross-Match
1 Result
1 Goals
1 Player Prop
```

veya Strategy reference.

Template'den yeni composition açıldığında current candidates canonical read layer'dan resolve edilir.

Template historical performance claim değildir.

### 4.5.43 Composition Revision Identity

Composition leg ekleme/çıkarma:
- mutable workspace state olabilir.

Ama:
- published Daily Composition;
- placed Simulation Bet
immutable snapshot'tır.

Published composition sonradan “daha iyi odds geldi” diye değiştirilmez.

Gerekirse successor publication/version oluşturulur.

### 4.5.44 Forecast Update Behavior

Studio açıkken yeni Current Canonical Run geldiğinde old displayed Forecast silently rewrite edilmemelidir.

UI:

```text
New projection available
46% → 51%
[Review update]
```

gösterebilir.

User refresh ettiğinde working draft current version'a geçebilir.

Published/placed artifact değişmez.

### 4.5.45 Quote Update Behavior

Same exact contract için yeni quote geldiğinde:

```text
Price changed
1.82 → 1.76
```

gösterilebilir.

User Betslip'e göndermeden önce latest eligible price revalidated edilir.

Line değişmişse:

```text
O2.5 → O3.0
```

otomatik replacement yapılmaz.

Bu yeni contract'tır ve user review gerektirir.

### 4.5.46 Composition Integrity Status

Before `Send to Betslip` Studio checks:

- all leg identities resolved;
- no contradictions;
- availability;
- price basis;
- dependency support;
- probability support if claimed;
- settlement support;
- quote state;
- kickoff/market state;
- source policy.

Possible final actions:

```text
Ready for simulation
Ready — limited model coverage
Research only
Blocked
```

`Ready` “good bet” demek değildir.

Sadece composition teknik olarak simulation placement'a hazırdır.

### 4.5.47 Studio → Betslip Boundary

Studio stake yönetmez.

Studio:
- composition oluşturur;
- validates;
- explains;
- sends to Betslip.

Betslip:
- stake;
- bankroll;
- potential return;
- final quote review;
- simulation placement
yönetir.

Bu ayrım Studio'yu bankroll/portfolio engine'e çevirmemizi engeller.

### 4.5.48 Final Review Before Simulation

Betslip final review'da:

- exact legs;
- exact contracts;
- source/price basis;
- price timestamps;
- combined price;
- combined probability if supported;
- model coverage;
- dependency support;
- stake;
- potential return;
- settlement caveats
görülür.

Quote materially changed:
user confirmation gerekebilir.

### 4.5.49 Placement Snapshot

User `Place Simulation` dediğinde immutable record freeze edilir:

- Simulation Bet ID;
- Composition ID/revision;
- placement timestamp;
- each leg exact identity;
- Prediction Run / Forecast refs;
- Signal/Recommendation refs;
- market observation refs;
- each leg odds;
- combination price;
- price basis;
- combination probability;
- joint/dependency method/version;
- Reliability/coverage context;
- stake;
- bankroll before;
- potential return;
- source classification;
- strategy reference varsa;
- settlement policy version.

Future changes placed snapshot'ı mutate etmez.

### 4.5.50 Studio Track Record Population

Public CalibraXI Studio Track Record:
- only explicitly Published Studio Compositions;
- exact publication policy;
- exact price basis;
- exact population definition
üzerinden hesaplanır.

User Manual compositions:
public CalibraXI Track Record'a girmez.

Strategy-assisted user compositions:
user performance'a girer.

### 4.5.51 Daily Builder Historical Integrity

Daily Cross-Match / Same-Match için historical page:

```text
Published 18:00
Legs at publication
Price at publication
Combined model probability
Coverage class
Result
Return / ROI basis
```

gösterebilir.

Later better odds:
historical return'u rewrite etmez.

Later Forecast:
published composition'ı rewrite etmez.

### 4.5.52 Failure Attribution

Builder kaybettiğinde product yalnızca:

```text
Lost
```

deyip geçmek zorunda değildir.

Track Record aggregate'ta:
- losing leg count;
- first losing leg;
- market family;
- dependency class;
- same-match/cross-match;
- price basis
analiz edilebilir.

Ancak post-hoc causal “neden kaybetti” storytelling yapılmaz.

### 4.5.53 Studio Inspector

Right-side Inspector possible sections:

#### Composition
- legs;
- fixtures;
- mode.

#### Model
- combined probability;
- coverage.

#### Dependency
- support class;
- same-fixture groups;
- unresolved pairs.

#### Market
- price basis;
- source coverage;
- quote times.

#### Integrity
- warnings/blockers.

#### History
- current draft revision;
- updates available.

### 4.5.54 Compatibility Matrix View

Advanced/power-user optional view:

```text
             Leg A   Leg B   Leg C
Leg A          —      ✓       !
Leg B          ✓      —       ×
Leg C          !      ×       —
```

Legend:
- ✓ compatible / supported;
- ! dependency or limited coverage;
- × conflict/unsupported.

Bu matrix probability değildir.

Default novice UI'da gizli/advanced olabilir.

### 4.5.55 Same-Match Dependency Explanation

User warning example:

```text
DEPENDENT LEGS

Home Win and Over 2.5 are not independent.
Combined probability is derived from the Match Goals/Scoreline parent.
```

Unsupported example:

```text
DEPENDENCY NOT MODELED

BTTS Yes + Over 3.5 Cards span separate model families.
Individual projections are available, but a combined model probability is not.
```

Bu transparency CalibraXI'ın önemli differentiator'larından biri olabilir.

### 4.5.56 Price Basis Selector

Manual Cross-Match mode'da available olduğunda:

```text
Price Basis
◉ Single Source
○ Best Observed Per Leg — Simulation
```

Same-Match:
- exact combination source quote available ise selectable;
- individual prices product'u option değildir.

Daily published compositions user tarafından price basis değiştirilince artık original published composition olmaz; user-created variant olur.

### 4.5.57 Source Consistency Indicator

Cross-Match:

```text
Source Coverage
3/3 legs available at Source A
```

veya:

```text
Mixed sources
A / B / C
Synthetic simulation price
```

gösterilebilir.

### 4.5.58 Leg Removal / Replacement

Unavailable leg için:

```text
Remove
Find alternatives
```

olabilir.

`Find alternatives`:
- same fixture/market family candidates gösterir;
- user explicit seçim yapar.

Studio leg'i otomatik değiştirip historical intent'i bozmaz.

### 4.5.59 Candidate Alternative Ranking

Alternative list:
- highest probability;
- current odds;
- Signal state
gibi sortable olabilir.

Ama default alternative choice gizli Recommendation olmamalıdır.

If recommendation-backed:
explicit `Recommended` label + Recommendation identity gerekir.

### 4.5.60 Studio Search

Search:
- fixture;
- team;
- player;
- market
bulabilir.

Example:

`Galatasaray`

→ upcoming eligible fixtures/selections.

`Osimhen shots`

→ supported player props.

Search query raw statistic'i selection'a uydurmaz.

### 4.5.61 Daily Studio First Viewport

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ STUDIO                                                   Daily | Build | Saved│
│ Compose, validate and simulate supported selections                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ DAILY                                                                      │
│ Cross-Match | Same-Match                                                   │
├────────────────────────────────────────────────┬─────────────────────────────┤
│ TODAY'S CROSS-MATCH                           │ COMPOSITION STATUS          │
│                                               │                             │
│ 1 Arsenal vs Liverpool — O2.5                │ 3 Legs                      │
│   Model 61% · Price 1.82                      │ Model coverage: Full        │
│                                               │ Dependency: Qualified       │
│ 2 Milan vs Roma — ...                         │ Price basis: Single Source  │
│                                               │ Combined probability ...    │
│ 3 ...                                         │ Combined price ...          │
│                                               │                             │
│ [Why these?] [Open details]                   │ [Send to Betslip]           │
└────────────────────────────────────────────────┴─────────────────────────────┘
```

Daily screen curation surface'tir.

BUILD workspace ise 3-pane araştırma UI kullanır.

### 4.5.62 Manual Build First Viewport

```text
┌────────────────────┬──────────────────────────────────┬──────────────────────┐
│ ADD SELECTION      │ YOUR COMPOSITION                 │ ANALYSIS             │
│                    │                                  │                      │
│ Search...          │ Arsenal-Liverpool O2.5           │ Legs: 3              │
│ Today's fixtures   │ Milan-Roma 1X                    │ Coverage: Partial    │
│ Projections        │ Saka SOT O1.5                    │ Dependency: Review   │
│ Markets            │                                  │ Price basis: Mixed   │
│ Watchlist          │ + Add another                    │ Quote state: Current │
│                    │                                  │                      │
│                    │                                  │ Research only        │
└────────────────────┴──────────────────────────────────┴──────────────────────┘
```

### 4.5.63 Mobile Studio

Mobile local nav:

```text
Daily
Build
Saved
```

BUILD:

```text
Composition list
↓
Analysis summary
↓
Add selection
↓
Review
```

Candidate Library:
bottom/full-screen sheet.

Inspector:
`Analysis` sheet.

Sticky bottom action:

```text
3 legs · Review
```

Betslip ayrı final sheet.

Compatibility warnings fold altında kaybolmamalıdır.

### 4.5.64 Studio Accessibility

- compatibility yalnızca color ile anlatılmaz;
- probability/price değişimi icon + text kullanır;
- drag-and-drop varsa keyboard alternative sağlanır;
- remove/reorder actions accessible;
- table/matrix screen reader semantics;
- quote update flashing kullanılmaz;
- motion preference respect edilir.

### 4.5.65 Leg Count Policy — OPEN

Minimum/maximum leg count launch policy henüz dondurulmamıştır.

Sınırlar:
- source rules;
- model coverage;
- UI usability;
- settlement complexity;
- performance validation
ile belirlenmelidir.

“Daha fazla leg = daha iyi builder” assumption yoktur.

### 4.5.66 Combination-Level Reliability — OPEN ANALYTICAL SPEC

Product UI composition support/diagnostics gösterebilir.

Ancak final:

```text
Studio Reliability
Builder Confidence
```

score/band henüz keyfi formülle üretilmeyecektir.

Analytical architecture şunları tanımlamalıdır:
- leg Reliability aggregation semantics;
- joint model validation;
- dependency evidence;
- price integrity;
- settlement support;
- calibration;
- historical builder performance'in rolü.

### 4.5.67 Combination Recommendation — GOVERNANCE SPECIFIED / TARGET-FAMILY MATH OPEN

Daily compositions genuine Recommendation/Curation katmanı gerektirir. Immutable candidate population, leg/composition eligibility, Recommendation/Curation Policy version, dependency/support, exact price, diversity/concentration, currentness, reasons/non-recommend reasons, publication, withdrawal, evaluation ve no-backfill semantics'i `CalibraXI-Analytics-Architecture.md` içinde tanımlıdır.

Manual Studio çalışabilir. Ancak target family için joint probability, combination calibration ve combination-level Reliability/support validated/versioned değilse Daily Studio Recommendation publication withheld olur; unsupported state product tarafından açık gösterilir.

### 4.5.68 Studio Non-Goals

Studio:
- component probabilities'i körlemesine çarpmaz;
- same-match individual odds'u combined bookmaker quote diye çarpmaz;
- cross-match different fixtures'ı otomatik independent saymaz;
- highest probability legs'i otomatik daily builder yapmaz;
- highest edge legs'i otomatik daily builder yapmaz;
- user composition'ı Recommendation diye yeniden etiketlemez;
- stale quote'u current diye kullanmaz;
- line değişimini otomatik kabul etmez;
- raw stats'i leg yapmaz;
- unsupported joint probability uydurmaz;
- Reliability'yi probability multiplier yapmaz;
- actual bookmaker'a bet göndermez;
- user stake'i Forecast/Signal computation'a sokmaz;
- historical published/placed composition'ı mutate etmez.

### 4.5.69 Canonical Studio Division

```text
DAILY
= CalibraXI published compositions
  ├── Cross-Match
  └── Same-Match

BUILD
= user manual composition workspace

SAVED
= drafts / templates / strategy-assisted material

BETSLIP
= stake + virtual placement

TRACK RECORD
= published CalibraXI composition performance

MY PERFORMANCE
= user-created simulation performance
```

### 4.5.70 Canonical Studio Flow

```text
Canonical Legs
      ↓
Contract Resolution
      ↓
Compatibility
      ↓
Contradiction / Redundancy
      ↓
Dependency Resolution
      ↓
Combination Probability Support
      ↓
Price Basis
      ↓
Settlement Support
      ↓
Composition Integrity
      ↓
Studio Draft / Published Composition
      ↓
Virtual Betslip
      ↓
Immutable Simulation Placement
      ↓
Settlement
      ↓
User Performance / Public Studio Track Record
```

Bu, bütün builder türlerinin tek Studio altında kalmasını ve analytical truth'un UI tarafından icat edilmemesini sağlar.

---

# 5. Track Record — FULL WORKING PRODUCT ARCHITECTURE

**Canonical route:** `/track-record`

Track Record CalibraXI'ın public proof / accountability layer'ıdır.

Temel analytical boundary:

```text
Forecast
!= Outcome
!= Atomic Evaluation
!= Evaluation Population
!= Track Record Projection
!= Publication
```

Track Record:
- yeni Forecast üretmez;
- sonucu adjudicate etmez;
- geçmiş Recommendation yaratmaz;
- yalnızca kazananları seçmez;
- mutable win/loss counter değildir.

Track Record, versioned bir population specification ve reporting policy üzerinden immutable Evaluation gerçeklerinden türetilen reproducible report surface'tir.

Frozen Track Record architecture'ın temel ilkesi korunur: Production analytical, publication-qualified, Signal, Recommendation, research/replay gibi farklı population classes sessizce aynı raporda birleştirilemez.

## 5.1 Public Track Record'ın ana sorusu

Kullanıcı şu sorulara cevap alabilmelidir:

1. CalibraXI'ın Forecast'ları probability quality açısından geçmişte nasıl performans gösterdi?
2. Forecast coverage ne kadardı?
3. Signal'ların eligible olduğu durumlarda realized settlement / price-basis performansı neydi?
4. Gerçekten yayınlanan Recommendation'lar nasıl performans gösterdi?
5. Gerçekten yayınlanan Studio compositions nasıl performans gösterdi?
6. Bu metrikler hangi population, dönem, odds/price basis ve model release'e ait?
7. Örneklem yeterli mi?
8. Sonuçlar ne kadar belirsiz / stabil?
9. Her aggregate sayı hangi historical artifact'lara kadar izlenebilir?
10. Bir outcome correction veya report-policy değişikliği sonrası rapor nasıl değişti?

## 5.2 Canonical Routes

```text
/track-record
├── /forecasts
├── /signals
├── /recommendations
└── /studio
```

Optional future deep routes:

```text
/track-record/report/{projectionId}
/track-record/artifact/{evaluationId}
/track-record/releases
```

Report/artifact route naming Engineering aşamasında değişebilir; requirement stable drill-down identity'dir.

## 5.3 Product-local Navigation

```text
Overview
Forecasts
Signals
Recommendations
Studio
```

`My Performance` burada yer almaz.

Kullanıcının kendi simulation geçmişi:

```text
/my/performance
```

altında kalır.

Bu ayrım zorunludur:

```text
PUBLIC TRACK RECORD
= CalibraXI production/published product outputs

MY PERFORMANCE
= user-created simulations / strategies
```

## 5.4 Default Public Population Policy

Public Track Record tek bir belirsiz “All Results” population'ı kullanmaz.

Recommended default behavior:

### Forecasts
Default public scientific view:
**Production Analytical — Final Canonical Pre-Match**

Ama:
- `Published Forecasts` ayrı view olarak seçilebilir;
- production analytical ile publication-qualified aynı population gibi gösterilmez.

### Signals
Default:
**Publication-Qualified Signals** eğer Signal Publication product policy'si aktifse.

Aksi durumda:
**Production Signals** açık label ile gösterilir.

### Recommendations
Default:
**Publication-Qualified Recommendations only.**

Recommendation gerçekten immutable olarak publish edilmediyse Track Record'a girmez.

Historical Signals'tan geriye dönük “Recommendation” türetilmez.

### Studio
Default:
**Published Studio Compositions only.**

Manual user compositions public Studio Track Record'a girmez.

## 5.5 Publication Proof

Public-facing Recommendation/Studio performansı için UI/API visibility publication proof değildir.

Publication-qualified member için exact immutable publication fact gerekir.

Publication şu şeylerden infer edilmez:
- Signal ELIGIBLE olması;
- Forecast'ın var olması;
- current olması;
- API response içinde görünmesi;
- user'ın Betslip'e eklemesi;
- UI ranking'de görünmesi;
- cache/log kaydı.

Track Record row:
`Published`
diyorsa exact publication lineage'a sahip olmalıdır.

## 5.6 Track Record Hub — Vertical Composition

Default `/track-record`:

```text
Track Record Header
Population / Period Controls
Public Performance Snapshot
Forecast Quality
Signal Performance
Recommendation Performance
Studio Performance
Coverage & Exclusions
Rolling Performance
Breakdowns
Report Integrity / As-of
Recent Historical Artifacts
Methodology
```

Hub her aile için aynı metrikleri zorla göstermez.

Forecast kalite report'u ile betting-like settlement report'u farklı metric semantics kullanır.

## 5.7 Track Record Header

```text
TRACK RECORD
Transparent performance from reproducible historical evaluations.
```

Header yanında:

```text
As of: ...
Report version: ...
Population: ...
```

yer alabilir.

Optional action:

`View methodology`

## 5.8 Global Track Record Controls

Applicable olduğunda:

### Period

```text
7 Days
30 Days
90 Days
YTD
Season
All Time
Custom
```

### Competition
- all supported;
- country;
- specific competition.

### Product Family
- Forecast;
- Signal;
- Recommendation;
- Studio.

### Market / Target
- 1X2;
- totals;
- BTTS;
- player prop;
- etc.

### Model / Capability Release
- current release;
- historical release.

### Forecast Horizon
- final pre-match;
- governed T-24h/T-6h/T-1h bins if later specified.

### Reliability strata
Only point-in-time historical Reliability that genuinely existed at evaluated boundary.

### Price basis
Signal/Recommendation/Studio only:
- publication-time;
- signal-time;
- source-specific;
- governed reference;
- other declared basis.

Filters semantically invalid olan sections'ta gösterilmez.

## 5.9 Outcome-Conditioned Filter Guardrail

Performance headline'ı yalnızca **ex-ante selectable dimensions** üzerinden filtrelenebilir.

Valid aggregate filter examples:
- competition;
- date range;
- market;
- model release;
- Forecast horizon;
- probability bucket;
- point-in-time Reliability bucket;
- signal-time odds bucket;
- publication class.

Post-outcome dimensions:
- won/lost;
- realized P/L;
- final score;
- “only winning bets”
aggregate headline population filter'ı olarak kullanılmaz.

User rows üzerinde wins/losses görebilir veya outcome diagnostics açabilir.

Ama:

```text
Filter: Winners Only
ROI: +100%
```

gibi outcome-conditioned pseudo-performance report oluşturulmaz.

Bu selection bias/cherry-picking korumasıdır.

## 5.10 Overview — Public Performance Snapshot

Overview first viewport'ta 4 family cards/panels:

### Forecast Quality
- evaluated Forecasts;
- primary proper score appropriate to probability space;
- calibration summary;
- coverage.

### Signals
- eligible published/production population label;
- settled count;
- unit-return/ROI where valid;
- average odds/price;
- coverage / cannot-evaluate context.

### Recommendations
- published count;
- settled;
- hit rate;
- average odds;
- unit-stake ROI/yield;
- sample uncertainty.

Only if genuine Recommendation history exists.

### Studio
- published compositions;
- Cross-Match / Same-Match split;
- average legs;
- average combined odds;
- hit rate;
- unit-stake ROI/yield;
- model coverage class.

No single universal:

```text
CalibraXI Accuracy = 82%
```

headline is allowed.

## 5.11 Track Record First Viewport

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ TRACK RECORD                                                                 │
│ Transparent, reproducible historical performance                            │
│ As of ... · Report v...                                    Methodology →    │
├──────────────────────────────────────────────────────────────────────────────┤
│ 30D  90D  YTD  All Time | Competition ▼ | Population ▼                    │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ FORECAST QUALITY     │ RECOMMENDATIONS      │ STUDIO                        │
│                      │                      │                               │
│ N ...                │ Published N ...      │ Published N ...               │
│ Log Loss ...         │ Hit Rate ...         │ Hit Rate ...                  │
│ Brier ...            │ Avg Odds ...         │ Avg Combined Odds ...         │
│ Calibration ...      │ Unit ROI ...         │ Unit ROI ...                  │
│ Coverage ...         │                      │                               │
├──────────────────────┴──────────────────────┴───────────────────────────────┤
│ COVERAGE & POPULATION                                                       │
│ Eligible ... · Evaluated ... · Pending ... · Unsupported ... · Excluded ... │
└──────────────────────────────────────────────────────────────────────────────┘
```

If Recommendation population does not yet exist:
empty-state explains that genuine published Recommendation history is not available.

It does not substitute Signals.

## 5.12 Forecast Track Record — `/track-record/forecasts`

Forecast Track Record's main objective probability forecast quality'dir.

It is not primarily ROI page.

Canonical views:

```text
Quality
Calibration
Coverage
Breakdowns
Releases
Artifacts
```

## 5.13 Forecast Quality Metrics

Probability-space appropriate metrics used.

Possible/report-family examples:

### Result-categorical
- multiclass log loss;
- multiclass Brier;
- RPS only if declared ordered semantics valid;
- classwise diagnostics.

### Joint scoreline/count
- joint log score;
- joint quadratic/Brier-like measures;
- compatible marginal diagnostics;
- derived-event diagnostics.

Exact primary metric sets remain governed analytical policy.

UI metric selection:
“hangisi güzel görünüyorsa onu göster” şeklinde yapılmaz.

## 5.14 Hit Rate Is Not Forecast Quality

Hit rate may be a secondary declared classification view.

Example:

```text
1X2 Winner Pick Accuracy
Rule: argmax 1X2
N: ...
```

But:

```text
Model Accuracy 78%
```

generic headline prohibited.

Because:
- 0.51 and 0.95 probabilities may both produce same discrete hit;
- proper scores preserve probability quality difference.

## 5.15 Calibration View

Forecast page can show:
- predicted probability buckets;
- observed frequency;
- sample per bucket;
- calibration curve;
- calibration error diagnostics if governed;
- sharpness/distribution context.

Track Record calibration chart:
- evaluates historical probabilities;
- does not recalibrate them;
- does not alter historical Forecast.

Point-in-time exact probability is scored as originally produced.

## 5.16 Forecast Coverage View

At minimum:

```text
Declared fixture population
Forecast AVAILABLE
Forecast evaluated
Pending outcome
Unsupported
Unavailable
Integrity excluded
Publication-qualified
```

Coverage:
quality score değildir.

A model:
- high quality;
- low coverage
olabilir.

Another:
- broad coverage;
- lower quality
olabilir.

Bu iki boyut tek arbitrary composite score'a sıkıştırılmaz.

## 5.17 Final Canonical Pre-Match Population

Default production Forecast view için preferred population:

**one Final Canonical Pre-Match Run per Fixture**

with explicit:
- Run Context;
- cutoff/kickoff boundary;
- current/canonical selection policy;
- missing-run behavior;
- integrity policy.

Family Forecast başka historical run'dan backfill edilmez.

“All runs” separate research/history population'dır.

## 5.18 Horizon Performance

Forecast performance information regime'e göre değişebilir.

Potential bins:

```text
T-24h
T-6h
T-1h
Final Pre-Match
```

Final bins later policy tarafından dondurulur.

UI:
- horizon sample;
- information state;
- quality metric
birlikte gösterir.

T-24 performance “all pre-match performance” diye genellenmez.

## 5.19 Model / Capability Release View

User release history'yi görebilir:

```text
Release A
Period ...
N ...
Quality ...
Coverage ...

Release B
...
```

Different release comparison:
- common/paired population;
- same outcome/metric semantics;
- paired difference;
- uncertainty
available when valid.

Raw averages from different populations:
“B daha iyi”
claim'i için tek başına kullanılmaz.

## 5.20 Baseline Comparison

Forecast Track Record appropriate baseline/reference'larla compare edebilir.

Potential:
- simple baseline;
- parent-native competence floor;
- declared market benchmark.

Market benchmark uses:
- exact compatible market;
- source/consensus;
- normalization;
- market Knowledge Time;
- Forecast horizon.

T-24 Forecast vs closing market comparison:
allowed only if later-information advantage explicit.

Same-information comparison gibi sunulmaz.

## 5.21 Signals Track Record — `/track-record/signals`

Signals page three questions'ı ayırır:

### Eligibility Performance
ELIGIBLE population nasıl settlement oldu?

### Selection / Discrimination
ELIGIBLE vs NOT_ELIGIBLE under a declared analytical comparison.

### Support / Coverage
CANNOT_EVALUATE ne kadar oluştu ve neden?

`CANNOT_EVALUATE`:
- loss değildir;
- negative Signal değildir.

## 5.22 Signal Metrics

Where mathematically valid:

- eligible count;
- settled count;
- wins/losses;
- pushes/voids/half states;
- hit rate;
- average/median price;
- model probability;
- probability edge;
- estimated EV;
- realized unit return;
- unit ROI/yield;
- temporal stability;
- max drawdown under declared unit-stake sequence if policy supports;
- Reliability strata;
- edge buckets;
- odds buckets;
- coverage;
- uncertainty.

Realized return:
Forecast quality veya Calibration değildir.

## 5.23 Signal Price Basis

Every Signal performance report declares price basis.

Examples:

```text
Signal-time observed price
Signal-time reference price
Source-specific price
Governed consensus/reference price
```

Closing price:
only retrospective CLV benchmark.

These bases never silently mix.

## 5.24 CLV View

CLV only if governed Closing Price Policy exists.

Requires:
- same exact Betting Contract;
- same line;
- same period;
- same selection;
- compatible price convention;
- closing benchmark identity;
- chronology.

Example prohibited:

```text
Signal: Over 2.5
Closing: Over 3.0
→ CLV
```

Line changed, so direct same-contract CLV comparison invalid.

## 5.25 Recommendation Track Record — `/track-record/recommendations`

This page becomes active only after genuine immutable Recommendation architecture exists.

No historical backfill from:
- positive edge;
- ELIGIBLE Signal;
- top-ranked projection;
- user bet;
- old UI pick.

### Recommendation Population

Default:
**actually published Recommendations**.

Required:
- exact Recommendation Decision;
- applicable Signal lineage;
- exact publication fact;
- exact betting contract;
- price basis;
- settlement/evaluation.

## 5.26 Recommendation Metrics

Possible:
- published recommendations;
- settled;
- wins/losses/push/void/half outcomes;
- hit rate;
- avg/median odds;
- average Forecast probability;
- average edge where applicable;
- unit-stake return;
- ROI/yield;
- rolling performance;
- drawdown;
- market/league breakdown;
- probability/odds/reliability buckets;
- sample size;
- uncertainty;
- coverage from eligible candidate pool to published population.

Recommended/not-recommended comparison is separate research question.

## 5.27 Daily Pick

If `Today's Pick` / `Daily Pick` becomes genuine Recommendation publication subtype:

Track Record can expose:
- published Daily Picks;
- settled;
- hit rate;
- avg price;
- unit-return/ROI;
- streaks;
- sample.

But no “Daily Pick history” is retroactively constructed from highest-ranked old Forecasts.

## 5.28 Studio Track Record — `/track-record/studio`

Only **Published Studio Compositions** are public CalibraXI Studio population.

Views:

```text
Overall
Cross-Match
Same-Match
Coverage
Artifacts
```

Manual user builds excluded.

## 5.29 Studio Metrics

- published compositions;
- settled compositions;
- hit rate;
- avg/median combined odds;
- avg leg count;
- leg-count distribution;
- unit-stake return;
- ROI/yield;
- P/L under declared unit basis;
- max drawdown where sequence definition valid;
- coverage class;
- combination probability support;
- source/price basis;
- same-match vs cross-match;
- league/market family distribution;
- losing-leg distribution;
- settlement-state distribution;
- rolling performance;
- sample/uncertainty.

## 5.30 Studio Coverage Breakdown

Example:

```text
Full Model Coverage        ...
Partial Model Coverage     ...
Price-Only                 ...
Research-Only              ...
Unsupported                ...
```

Public ROI headline:
only population in which required publication + price + settlement semantics exist.

Research-only compositions ROI denominator'a sokulmaz.

## 5.31 Unit-Stake Reporting

Public ROI comparison için user stake kullanılmaz.

If valid:
- standardized unit stake;
- declared payout convention.

This:
- staking advice değildir;
- Kelly değildir;
- bankroll strategy değildir.

Actual user bankroll belongs to `/my/performance`.

## 5.32 Complex Settlement

Track Record settlement states preserve:
- WIN;
- LOSS;
- PUSH;
- VOID;
- HALF_WIN;
- HALF_LOSS;
- split settlement;
- dead heat;
- other governed states.

UI:
`Push = Loss`
yapmaz.

Quarter/Asian/commission semantics correct payoff method ile aggregate edilir.

## 5.33 Coverage & Exclusions Panel

Every major Track Record page has a population transparency panel.

At minimum:

```text
Eligible candidates
Selected population
Evaluated / settled
Pending
Unsupported / incompatible
CANNOT_EVALUATE
Integrity / quarantine exclusions
Publication exclusions
Other excluded
```

User can open:

`Why were these excluded?`

and reason distribution see.

This panel prevents denominator hiding.

## 5.34 Population Inspector

Advanced drawer:

```text
Population name
Specification version
As-of
Run-selection rule
Publication requirement
Outcome finality requirement
Price basis
Market source policy
Integrity policy
Statistical unit
Dependency treatment
Aggregation policy
```

This is public reproducibility metadata—not internal admin-only information.

Sensitive provider/licensing implementation details may remain appropriately abstracted.

## 5.35 Metric Definition Drawer

Every substantive metric can open:

```text
Metric
Definition
Population
Numerator
Denominator
N
Effective N
Price basis
Outcome scope
Uncertainty method
As-of
```

No universal unlabeled `Win Rate`.

## 5.36 N vs Effective Sample

Raw row count:
`N`

Statistically effective sample:
`Effective N`
may differ due:
- multiple markets per fixture;
- repeated runs;
- same parent distribution;
- repeated market observations;
- competition/time clustering.

When applicable both shown.

Correlated child markets are not blindly treated as independent samples.

## 5.37 Uncertainty

Where scientifically meaningful:
- confidence/uncertainty interval;
- method;
- cluster/block unit;
- limitations
shown.

Potential methods remain analytical-policy decisions:
- cluster-aware bootstrap;
- temporal block;
- paired difference interval;
- binomial interval;
- return uncertainty.

Small N:
explicit warning.

Example:

```text
Small sample — interpret cautiously
```

It does not hide the metric; it contextualizes it.

## 5.38 Rolling Performance

Supported:

```text
7D
30D
90D
YTD
Season
All Time
```

Charts:
- rolling hit rate appropriate population;
- rolling unit ROI;
- rolling proper score;
- cumulative unit return;
- cumulative sample;
- coverage.

Metric mixing avoided:
Forecast quality line and ROI line do not share meaningless same y-axis.

## 5.39 Equity / Drawdown Curve

Recommendation/Studio/Signal unit-return reports may include:

- cumulative unit return;
- drawdown;
- high-water mark;
- max drawdown.

This is analytical standardized unit-return curve.

It is not user's bankroll.

User bankroll:
`/my/performance`.

## 5.40 Probability Buckets

Forecast/Recommendation analysis can show:

```text
50–55%
55–60%
60–65%
...
```

only predeclared/governed bucket policy.

For each:
- N;
- observed frequency;
- expected probability;
- calibration gap;
- outcome/return where relevant.

Buckets are evaluation views, not Recommendation thresholds.

Repeatedly tuning bucket boundaries to look good is prohibited.

## 5.41 Reliability Buckets

Only historical point-in-time Reliability used.

Views may test:

```text
High
Medium
Low
```

or later governed bands.

Goal:
Reliability gerçekten performance/support ile ilişkili mi?

Today recomputed Reliability old Forecast'a pasted edilmez.

## 5.42 Odds / Edge Buckets

Signal/Recommendation pages may show:
- odds buckets;
- probability-edge buckets;
- EV ranges;
- price advantage groups.

Need:
- predeclared bucket boundaries;
- exact price basis;
- N;
- uncertainty.

Highest historical ROI bucket automatic future Recommendation rule değildir.

## 5.43 League / Market Breakdowns

Breakdowns:
- competition;
- market family;
- target;
- home/away where valid;
- player prop family;
- Studio mode.

Each row:
- N;
- key metric;
- coverage;
- uncertainty/small-sample state.

Default sorting:
sample/relevance or metric-specific governed sort.

Not:
“best league” label.

## 5.44 Public Artifact Ledger

Every aggregate report drills down to atomic artifact rows.

Example Recommendation row:

```text
2026-09-20
Arsenal vs Liverpool

Recommendation: Over 2.5
Published: 18:05

Forecast: 61%
Price: 1.82
Price basis: Source A
Result: WIN
Unit return: +0.82

[Open historical artifact]
```

Forecast row:
- fixture;
- target;
- Forecast probability;
- cutoff;
- run;
- outcome;
- score contribution.

Signal row:
- decision;
- contract;
- market Knowledge Time;
- price basis;
- settlement;
- return.

Studio row:
- composition;
- legs;
- publication;
- combined price;
- support class;
- settlement.

## 5.45 Historical Artifact Drill-Down

`Open historical artifact`:
→ Match Center `#history`
or dedicated Track Record artifact detail.

Shows exact:
- Prediction Run;
- Forecast Target;
- Forecast probability;
- Forecast Cutoff;
- Reliability evidence if genuine;
- Signal Evaluation;
- Recommendation Decision if genuine;
- publication fact;
- Market Observation/price;
- Settlement Evaluation;
- Outcome Adjudication;
- Evaluation identity;
- report inclusion reason.

This is the direct UI realization of:

> “CalibraXI o anda ne biliyordu ve ne yayınladı?”

## 5.46 Why Included?

Artifact can expose:

```text
Included in:
Published Recommendations — 30D

Why:
- publication fact exists
- PRE_MATCH
- outcome final
- settlement resolved
- integrity passed
- period in range
```

Likewise exclusion:

```text
Excluded:
Outcome pending
```

or:

```text
Excluded:
No publication fact
```

## 5.47 Corrections & Report Versioning

Outcome/source correction:
old report silently rewrite edilmez.

Conceptual sequence:

```text
Report v12
Outcome correction
New adjudication/evaluation
Report v13
```

Both reports queryable.

Current page may show:

```text
Report updated after outcome correction
Previous version available
```

Historical report retains:
- as-of;
- population;
- selected evaluations;
- metric calculation.

## 5.48 Official Current vs Historical Report

`Current report`
means latest applicable projection for declared policy/as-of.

It is a selection question.

No mutable:

```text
isCurrent = true
```

row becomes historical truth authority.

User can open:
`Report history`.

## 5.49 As-Of / Projection Watermark

Every report version has:
- as-of boundary;
- build time;
- projection watermark;
- population version;
- reporting policy version.

This matters if:
- pending matches settle;
- corrections arrive;
- integrity changes;
- publication facts arrive.

## 5.50 Pending Outcomes

Pending fixture:
- not loss;
- not void unless settlement semantics say so;
- not silently excluded without count.

Panel:

```text
Settled       184
Pending         6
Unresolved      2
```

Headline denominator definition visible.

## 5.51 Integrity / Quarantine

Artifact with integrity problem can be:
- excluded;
- quarantined;
- pending review
under declared report policy.

Count/reason visible.

Do not silently remove a losing row because data is inconvenient.

Likewise do not keep a known-invalid winning row because it improves ROI.

## 5.52 Research / Backtest Separation

Production Track Record does not silently include:
- Shadow;
- Challenger;
- offline candidates;
- Synthetic PIT;
- Corrected-Data Replay;
- research scenario.

Advanced research surfaces may report them with unmistakable labels.

They do not appear in default public production headline.

## 5.53 Backtest Is Not Track Record

Historical backtest answers:
> Bir strategy/model declared PIT reconstruction altında geçmişte ne yapardı?

Track Record answers:
> Hangi genuine production/published artifacts gerçekten oluştu ve governed outcomes karşısında ne yaptı?

These can both be valuable but are not interchangeable.

## 5.54 Recommendation Backfill Prohibition

If Recommendation Architecture starts today:
old Signals cannot be retroactively labelled:

```text
Recommendation
```

to create impressive history.

Historical Recommendation Track Record begins from genuine decision/publication facts.

Synthetic retrospective Recommendation research:
separate research class.

## 5.55 Studio Backfill Prohibition

Likewise old arbitrary coupons/combinations:
published Studio history olarak relabel edilmez.

Public Studio Track Record begins from governed Published Studio Composition lineage.

Legacy/reconstructed research:
separate.

## 5.56 Comparison With Market

Forecast quality and market benchmark separate.

Potential comparison:
- model proper score;
- reference market score
on matched population.

But:
- same contract;
- declared market basis;
- information-time difference;
- normalization method
must be explicit.

“Beat the market” generic marketing badge prohibited without exact benchmark semantics.

## 5.57 Comparison With Baseline

Model release vs baseline:
- same fixtures/origins;
- paired contributions;
- same probability space;
- same outcome basis.

Coverage difference reported separately.

This avoids a model appearing better because it evaluated an easier subset.

## 5.58 Performance Timeline Events

Charts may annotate:
- model release;
- calibration release;
- major policy version;
- Recommendation policy activation;
- Studio publication activation.

But timeline annotation does not claim causality.

Example:
`Release v3 deployed`

not:
`ROI improved because v3 is smarter`
unless supported by analysis.

## 5.59 Model Release Boundary

When new production Capability Release starts:
old historical artifacts remain attributed to old release.

All-time Track Record:
may aggregate releases under explicit production population.

Release-specific view:
keeps them separate.

No today-model rescoring old production probabilities as if historical production.

## 5.60 Track Record Search / Artifact Navigation

Search:
- fixture;
- team;
- player;
- competition;
- artifact ID;
- date.

Useful for:
> “20 Eylül’deki Arsenal tahmini nerede?”

Search result:
exact artifact.

## 5.61 Export / Share

Future:
- share filtered report;
- export CSV;
- export methodology summary.

Shared report retains:
- filter state;
- population ID;
- as-of/report version.

A screenshot-style “ROI +23%” share without population/sample context should not be the primary share mechanism.

## 5.62 Track Record Visual Direction

Light-first.

Visual hierarchy:
- report metadata;
- key metrics;
- uncertainty;
- coverage;
- charts;
- breakdown tables;
- artifact ledger.

Avoid:
- sportsbook green win confetti;
- oversized “87% SUCCESS” hero;
- cherry-picked streak as primary proof;
- animation celebrating financial return.

Win/loss colors are semantic and restrained.

## 5.63 Track Record Mobile

Mobile local nav:

```text
Overview
Forecasts
Signals
Recommendations
Studio
```

Filters:
full-screen sheet.

Metric cards:
- metric;
- N;
- interval;
- population label.

Breakdown tables:
stacked rows.

Artifact ledger:
compact cards.

Population/Methodology:
drawer/sheet.

Charts horizontally scroll only when necessary; default responsive.

## 5.64 Track Record Empty States

### No genuine Recommendations yet

```text
No published Recommendation history is available for this population.
```

Do not fill with Signals.

### No settled outcomes

```text
Evaluations exist, but outcomes are not sufficiently final yet.
```

### Unsupported metric

```text
This metric is not defined for the selected probability/settlement space.
```

### Small sample

Metric shown with:
`Small sample`
context, if method supports calculation.

## 5.65 Track Record Homepage Preview

Homepage Transparency Snapshot:
Track Record full system'in mini read view'ıdır.

Example:

```text
Published Recommendations — Last 30 Days
N ...
Settled ...
Hit Rate ...
Avg Odds ...
Unit ROI ...
```

Click:
→ `/track-record/recommendations?period=30d`

If published Recommendations do not yet exist:
homepage uses a valid existing family, e.g. Forecast Quality or Published Studio, with exact label.

It does not invent Recommendation history.

## 5.66 Track Record ↔ Competition Page

Competition Page:
`CalibraXI performance in Premier League`

preview olabilir.

Click:
→ Track Record exact competition filter.

Population semantics preserved.

## 5.67 Track Record ↔ Team / Player

Team/player entity pages may deep-link relevant historical artifact lists.

But:
team-specific small N ROI card default profile headline olmaz.

It may live under:
`CalibraXI History`
with sample context.

## 5.68 Track Record ↔ Match Center

Artifact click:
→ Match Center History.

Finished Match Center:
`View evaluation in Track Record`

backlink.

This creates bidirectional audit graph.

## 5.69 Track Record ↔ Methodology

Every family has methodology links:

Forecast:
- proper scoring;
- calibration;
- run selection;
- horizon.

Signal:
- price basis;
- edge;
- settlement;
- unit-return.

Recommendation:
- publication population;
- price basis;
- settlement.

Studio:
- published composition;
- dependency/model coverage;
- price basis;
- settlement.

## 5.70 User Simulation Performance Boundary

`/my/performance` may reuse visualization components.

But source population:
user Simulation Bet ledger.

Public Track Record source:
CalibraXI immutable production/publication evaluations.

Components reusable.
Authority not reusable.

## 5.71 Recommended Track Record Headline Strategy

CalibraXI should prefer:

```text
Published Recommendations
Last 90 Days
N 184
Hit Rate ...
Avg Odds ...
Unit ROI ...
95% interval ...
```

over:

```text
WE WIN 78% OF BETS
```

Likewise Forecast:

```text
Final Pre-Match Forecast Quality
N ...
Log Loss ...
Brier ...
Calibration ...
Coverage ...
```

rather than generic accuracy score.

## 5.72 Sample Size Always Visible

Headline metrics:
N omitted edilemez.

Where relevant:
- raw N;
- settled N;
- effective N.

No ROI/hit-rate card without sample context.

## 5.73 Denominator Always Defined

Example:

```text
Hit Rate
Wins / (Wins + Losses)
Push/Void excluded under policy X
```

or another exact declared denominator.

Push/void treatment report policy tarafından explicit.

## 5.74 Update Cadence

Track Record is not required to mutate second-by-second.

Possible:
- settlement-driven rebuild;
- scheduled report projection;
- material correction rebuild.

Exact cadence Engineering/Publication policy later selects.

Each visible report:
as-of timestamp shows.

## 5.75 Performance Alerts — Not Default

Track Record is primarily research/proof surface.

User-specific alert such as:
`notify when 30D strategy ROI...`
belongs to My CalibraXI/Strategy scope, not public Track Record core.

## 5.76 Public Report Integrity Badge

A generic data freshness badge deferred olsa da report correctness için compact metadata allowed:

```text
As of ...
Population v...
Report v...
```

Optional:

`Methodology`

This is not a promotional confidence badge.

## 5.77 Track Record Non-Goals

Track Record:
- outcome'u değiştirmaz;
- old Evaluation'ı mutate etmez;
- Recommendation backfill etmez;
- published olmayan artifact'ı published diye saymaz;
- research'i production diye karıştırmaz;
- pending'i loss saymaz;
- push/void'u loss saymaz;
- Forecast quality'yi hit rate'e indirgemez;
- ROI'yi Forecast quality veya Calibration diye sunmaz;
- today's Reliability'yi old artifact'a yapıştırmaz;
- closing price'ı Signal-time input gibi göstermez;
- result-conditioned filter ile performance headline üretmez;
- small samples'ı gizlemez;
- correlated child markets'i independent N gibi saymaz;
- report correction'ını history rewrite olarak yapmaz;
- public Track Record'a user simulations karıştırmaz;
- generic marketing “accuracy” skoru üretmez.

## 5.78 Canonical Track Record Flow

```text
Historical analytical artifact
              \
               +→ Atomic Evaluation
              /
Governed Outcome Truth
       ↓
Evaluation Population Specification
       ↓
Aggregation / Reporting Policy
       ↓
Track Record Projection
       ↓
Public Track Record
       ↓
Artifact Drill-Down
       ↓
Historical Snapshot / Match Center
```

For settlement-based outputs:

```text
Published Signal / Recommendation / Studio Composition
        ↓
Exact Betting Contract
        ↓
Settlement Evaluation
        ↓
Performance Evaluation
        ↓
Publication-qualified Population
        ↓
Track Record Projection
```

## 5.79 Working Decision

Canonical division:

```text
/track-record
= public overview and proof layer

/track-record/forecasts
= scientific Forecast quality / calibration / coverage

/track-record/signals
= governed Signal analytical performance

/track-record/recommendations
= genuine published Recommendation performance

/track-record/studio
= genuine published Studio Composition performance

/my/performance
= user simulation / Strategy performance
```

Track Record'ın amacı CalibraXI'ı “iyi göstermek” değil, **geçmişte gerçekten ne üretildiğini, ne yayınlandığını, hangi population üzerinde nasıl performans gösterdiğini yeniden üretilebilir şekilde göstermek**tir.

---

# 6. Stats & Entity Discovery — FULL WORKING ARCHITECTURE

CalibraXI'ın **Stats** alanı model Forecast dünyasından bilinçli olarak ayrıdır.

Temel ayrım:

```text
STATS
= gözlemlenmiş / historical / aggregated football data

PROJECTIONS
= geleceğe dönük model Forecast outputs

MARKETS
= bookmaker / market price observations
```

Stats alanının görevi:
- veriyi araştırmak;
- takım/oyuncu/competition keşfetmek;
- pattern ve streak görmek;
- Power Ratings'i incelemek;
- historical performance context sağlamak;
- kullanıcıyı doğru entity page veya Match Center'a taşımaktır.

Stats bir raw-data dump olmayacaktır.

## 6.1 Canonical Stats Routes

Working route family:

```text
/stats
├── /power-rankings
├── /teams
├── /players
├── /streaks
├── /goals
├── /shots
├── /corners
└── /cards
```

İlk launch için minimum required dedicated pages:

```text
/stats
/stats/power-rankings
/stats/teams
/stats/players
/stats/streaks
```

`goals`, `shots`, `corners`, `cards` gibi metric-family routes ihtiyaç büyüdükçe ayrılabilir.

Canonical entity directories ayrıca:

```text
/competitions
/teams
/players
```

Entity detail:

```text
/competition/{slug}
/team/{slug}
/player/{slug}
```

## 6.2 `/stats` — Stats Hub

Stats Hub'ın ilk görevi kullanıcıya “veride bugün / bu sezon ne dikkat çekiyor?” sorusunun cevabını vermektir.

Vertical composition:

```text
Stats Header
Competition / Season / Timeframe Controls
Power Rankings Preview
Team Leaders
Player Leaders
Streaks
Goals / O-U Trends
BTTS Trends
Shots / SOT
Corners
Cards
Entity Discovery
Methodology
```

Bütün bölümler aynı metric dönemini kullanmak zorunda değildir. Her metric group kendi valid timeframe'ini açıkça gösterir.

## 6.3 Stats Header

```text
STATS
Teams, players, rankings and trends.

[Competition ▼] [Season ▼] [Timeframe ▼]
```

Optional compact entry points:

```text
Power Rankings
Teams
Players
Streaks
```

Stats Header'da:
- betting recommendation copy;
- probability;
- edge
varsayılan olarak kullanılmaz.

Stats, data-first alandır.

## 6.4 Global Stats Controls

### Competition

- All Supported;
- selected competition;
- country;
- followed competitions.

### Season

- current season;
- prior supported seasons.

### Timeframe

Metric semantic'e göre:

```text
Season
Last 5
Last 10
Last 20
Last 30 Days
Home
Away
Custom supported range
```

Ama `Last 5` her metric için zorunlu değildir.

### Minimum Sample

Özellikle per-90/player ranking için:
- minimum minutes;
- minimum appearances;
- minimum starts
gibi sample controls kullanılabilir.

### Context

- home;
- away;
- overall;
- competition-only;
- all competitions supported ise.

## 6.5 Metric Definition & Denominator Rule

Her statistic'in denominator'ı görünür veya ulaşılabilir olmalıdır.

Örnek:

```text
Goals
= total

Goals / 90
= rate normalized by minutes

BTTS %
= eligible matches with both teams scoring / eligible matches

Over 2.5 %
= eligible matches over 2.5 / eligible matches
```

Aynı label altında farklı denominator'lar sessizce karıştırılmaz.

Metric detail tooltip / methodology:
- definition;
- unit;
- eligible population;
- provider/source family uygun olduğunda;
- timeframe.

## 6.6 Power Rankings — Canonical Stats Product

Route:
**`/stats/power-rankings`**

Power Rankings Stats'in flagship section'larından biridir.

### Table

```text
Rank
Team
ATT
DEF
OVR
Δ Rank
Δ OVR
Form
Last Update / Snapshot
```

Gerçek takım crest'leri kullanılır.

### Ranking views

Tabs/filters:

```text
Overall
Attack
Defense
Biggest Risers
Biggest Fallers
```

Bu tabs aynı underlying rating system'in farklı presentation'larıdır; ayrı rating systems değildir.

### League selection

Default:
- selected competition.

User:
- Premier League;
- La Liga;
- Serie A;
- Süper Lig;
- etc.
arasında geçebilir.

Cross-league global ranking yalnızca rating scale gerçekten cross-competition comparable ise yayınlanır.

Comparability validate edilmeden:
`All Europe #1`
gibi claim yapılmaz.

## 6.7 ATT / DEF / OVR Semantics

Exact matematik daha sonra **Power Rating Architecture** içinde dondurulacaktır.

Product-level expectations:

**ATT**
- attacking strength/state representation.

**DEF**
- defensive strength representation.

**OVR**
- combined overall team-strength representation.

Kurallar:
- DEF sayısı kullanıcıya “yüksek = iyi” mi “düşük = iyi” mi açık olmalı;
- scale competition/time arasında semantik olarak tutarlı olmalı;
- OVR sadece UI için ATT+DEF'in keyfi ortalaması olamaz;
- rank changes exact historical snapshot'lar arasında hesaplanır;
- current match result gelince geçmiş snapshot rewrite edilmez.

## 6.8 Power Ranking History

Team row click:
→ Team Page Power section.

Dedicated history visualization:

```text
Date      Rank   ATT   DEF   OVR
W1        8      ...   ...   ...
W2        6      ...   ...   ...
W3        4      ...   ...   ...
```

Chart:
- OVR history;
- rank history;
- ATT;
- DEF.

Optional event annotations:
- manager change;
- major player absence/return;
- important fixture
yalnızca reliable structured context varsa.

Chart explanation causality uydurmaz.

## 6.9 Team Stats Leaderboards

Route:
**`/stats/teams`**

Canonical metric families:

### Scoring
- goals;
- goals per match;
- xG supported olduğunda;
- shots;
- SOT;
- conversion rate;
- big chances appropriate olduğunda.

### Defense
- goals conceded;
- xGA;
- shots allowed;
- SOT allowed;
- clean sheets;
- defensive process metrics.

### Match Profile
- possession;
- pass metrics;
- tempo/progression metrics supported olduğunda;
- fouls;
- corners;
- cards.

### Outcome Pattern
- wins;
- draws;
- losses;
- BTTS rate;
- Over 1.5;
- Over 2.5;
- Over 3.5;
- Under 2.5;
- first-half goals;
- scoring first;
- conceding first.

### Split

```text
Overall
Home
Away
```

### Team Leaderboard Row

```text
#3 [ARSENAL CREST] Arsenal
2.11 xG / match
▲ 0.18 vs previous window
18 matches
```

`▲` yalnızca comparable window tanımı varsa gösterilir.

Row click:
→ `/team/arsenal`

## 6.10 Player Stats Leaderboards

Route:
**`/stats/players`**

Canonical player metric families:

### Output
- goals;
- assists;
- goal contributions;
- xG;
- xA.

### Shooting
- shots;
- shots / 90;
- shots on target;
- SOT / 90;
- shot accuracy;
- conversion.

### Creation
- key passes;
- chances created;
- progressive/creative metrics supported olduğunda.

### Discipline / Defensive
- cards;
- fouls;
- tackles;
- interceptions.

### Goalkeeping
- saves;
- save rate;
- clean sheets;
- goals prevented type metrics yalnızca source methodology uygunsa.

### Rate vs Total

User toggles:

```text
Total
Per 90
```

Per-90 leaderboard minimum-minutes threshold olmadan gösterilmez.

### Player Row

```text
#1
[player headshot]
Mohamed Salah
Liverpool · RW

Goals       19
Goals/90    0.81
Minutes     2110
```

Player row click:
→ `/player/{slug}`

Team crest/name:
→ Team Page.

## 6.11 Player Position Filters

Filters:
- GK;
- DEF;
- MID;
- FWD
veya daha granular provider positions.

Position categories provider değiştikçe aynı oyuncuyu iki farklı semantics altında göstermemelidir.

User-facing normalized position taxonomy Engineering/domain'de ayrıca tanımlanır.

## 6.12 Streaks — Dedicated Discovery Product

Route:
**`/stats/streaks`**

Streaks basit marketing cümleleri değil, exact consecutive-event sequences'dır.

Canonical families:

### Result
- winning;
- unbeaten;
- losing;
- winless.

### Scoring
- scored in N;
- failed to score;
- scored 2+;
- conceded;
- clean sheets.

### Totals
- Over 1.5;
- Over 2.5;
- Over 3.5;
- Under 2.5;
- Under 3.5.

### BTTS
- BTTS Yes;
- BTTS No.

### Period
- first-half goal;
- first-half Over;
- second-half scoring
support varsa.

### Corners / Cards
- team corner thresholds;
- match corners;
- card thresholds
source coverage varsa.

### Streak Card

```text
ARSENAL

SCORING STREAK
Scored in 11 consecutive league matches

11 matches
Premier League
Sep 2 → Nov 18

Next fixture:
Arsenal vs Chelsea

[Team] [Match]
```

Streak cümlesinin denominator/competition scope'u görünür olmalıdır.

## 6.13 Active vs Historical Streaks

`Active`
ve
`Historical`

ayrılır.

Default discovery:
**Active streaks**

Historical:
- records;
- previous longest streaks
gibi context için.

Bitmiş streak current'mış gibi gösterilmez.

## 6.14 Stats Trends vs Forecasts

Örneğin:

> Team A son 10 maçın 8'inde O2.5 yaptı.

Bu:
**STAT TREND**

dir.

Bu tek başına:
> sonraki maç O2.5 probability %80

demek değildir.

Stats card üzerinde relevant current fixture varsa:

```text
View next match
View current projection
```

deep-link verilebilir.

Ama projection değeri Stats tarafından hesaplanmaz.

## 6.15 Goals / Over-Under Discovery

Stats Hub veya future `/stats/goals` route'unda:

### Team
- goals for;
- goals against;
- O1.5%;
- O2.5%;
- O3.5%;
- team over 0.5;
- team over 1.5.

### Match profile
- average total goals;
- first-half average;
- second-half average.

Controls:
- season;
- last N;
- home/away;
- competition.

Current fixtures ile ilişkilendirilirse:
`Upcoming today`
badge olabilir.

Ama `likely Over 2.5` label'ı yalnızca Forecast destekliyorsa Projection surface'ten gelir.

## 6.16 BTTS Discovery

Stats:
- team scored%;
- team conceded%;
- BTTS%;
- clean-sheet%;
- fail-to-score%;
- home/away splits.

Pairing example:

```text
Arsenal
BTTS 72%

Chelsea
BTTS 68%

Next:
Arsenal vs Chelsea

[Open Match]
```

Bu presentation matchup keşfi sağlar; combined BTTS Forecast değildir.

## 6.17 Shots & SOT Discovery

Team:
- shots for;
- shots against;
- SOT;
- SOT allowed;
- shooting accuracy.

Player:
- shots;
- SOT;
- shots / 90;
- SOT / 90.

Current Player Prop'a deep link varsa:

```text
View Saka SOT projection
```

Stats observed past data olarak kalır.

## 6.18 Corners & Cards Discovery

Data coverage uygunsa Stats içinde first-class metric families olabilir.

Corners:
- corners for;
- corners against;
- total match corners;
- home/away;
- threshold rates.

Cards:
- cards received;
- opponent cards;
- total cards;
- fouls;
- referee context future data support varsa.

Referee statistic mevcut değilse uydurulmaz.

## 6.19 Leaderboard Movement

Stats leaderboards'da `trend/movement` gösterilecekse exact comparison basis gerekir.

Örnek:

```text
Current last-10 xG/90
vs previous 10-match window
```

veya:

```text
Current Power Rank
vs previous weekly snapshot
```

`▲12%`
gibi bir badge comparison period belirtilmeden gösterilmez.

## 6.20 Percentile / Distribution Context

Tek bir raw number bazen anlam ifade etmez.

Optional context:
- league percentile;
- competition rank;
- distribution bar.

Örnek:

```text
Shots / 90: 15.8
League percentile: 88th
Rank: 3 / 20
```

Percentile:
- same competition;
- same season/timeframe;
- eligible population
üzerinden hesaplanır.

Player percentile ise position/minutes population açık olmalıdır.

## 6.21 Stats Compare Entry

Leaderboard row/card:
`Compare`

action sunabilir.

Team:
→ `/compare?type=team...`

Player:
→ `/compare?type=player...`

Compare action ranking row'un primary click'ini çalmaz.

## 6.22 Stats Watch Entry

User:
- team;
- player;
- competition;
- selected metric/streak
takip edebilir.

Metric-specific watch future feature olabilir:

```text
Alert me if Arsenal enters Top 3 ATT
```

Bu Watch/Alert system My CalibraXI altında yönetilir.

## 6.23 Entity Directories

### `/competitions`

Browse:
- country;
- competition type;
- followed;
- alphabetic / popularity product sort.

Competition click:
→ canonical Competition Page.

### `/teams`

Search/filter:
- country;
- competition;
- followed.

Team:
- crest;
- name;
- current competition;
- Power Rating summary
uygun olduğunda.

### `/players`

Search/filter:
- competition;
- team;
- position;
- nationality support varsa.

Player:
- photo;
- name;
- team;
- position;
- selected season summary.

Directories leaderboard değildir.

## 6.24 Stats Hub First Viewport

Working composition:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ STATS                                                   Teams Players       │
│ Rankings, leaders and football trends                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Premier League ▼   2026/27 ▼   Season ▼                                    │
├─────────────────────────────────────────┬────────────────────────────────────┤
│ POWER RANKINGS                          │ BIGGEST MOVERS                     │
│                                         │                                    │
│ # Team        ATT  DEF  OVR  Δ          │ Arsenal      +3                    │
│ 1 Arsenal     ...  ...  ...  ↑          │ Chelsea      -4                    │
│ 2 Liverpool   ...  ...  ...  →          │ ...                                │
│ 3 City        ...  ...  ...  ↓          │                                    │
│                                         │                                    │
│ View full rankings →                    │                                    │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ TEAM LEADERS                  │ PLAYER LEADERS                               │
│ Goals / xG / SOT ...          │ Goals / Assists / SOT ...                   │
└───────────────────────────────┴──────────────────────────────────────────────┘
```

Below fold:
- Streaks;
- O/U;
- BTTS;
- Shots;
- Corners/Cards.

## 6.25 Stats Visual Direction

Light-first.

Stats should feel:
- editorial;
- sortable;
- dense when needed;
- not spreadsheet-only;
- not casino;
- real football identity-forward.

Use:
- team crests;
- player headshots;
- sparklines;
- rank movement;
- compact distribution visuals;
- clear tabular alignment.

Avoid:
- every number in colored pill;
- red/green for normal rank changes everywhere;
- huge decorative cards for simple rows.

## 6.26 Mobile Stats

Mobile:
- competition/season controls compact sheet;
- horizontal metric-family chips;
- leaderboard cards/rows;
- one primary metric + secondary context;
- expand for more columns.

Desktop 10-column table mobile'da sıkıştırılmaz.

Power Rankings mobile row:

```text
#1  [crest] Arsenal
OVR ...
ATT ... · DEF ...
▲ 2
```

tap → Team Page.

## 6.27 Stats Methodology

Every major family links to methodology:

- Power Ratings;
- xG/source methodology as available;
- per-90;
- streak definitions;
- percentile population.

Stats methodology ile Forecast methodology aynı sayfa olmak zorunda değildir ama cross-linked olabilir.

## 6.28 Stats Non-Goals

Stats UI:
- Forecast üretmez;
- probability uydurmaz;
- statistical rate'i future probability diye etiketlemez;
- form streak'i Recommendation yapmaz;
- player leaderboard'u Player Prop Forecast'a çevirmeye çalışmaz;
- market odds'u metric'e karıştırmaz;
- Power Ranking'i league table points ile aynı şey gibi göstermez;
- small sample rate'i büyük sample ile eşitmiş gibi sunmaz.

## 6.29 Homepage Statistics Discovery — Relationship

Homepage'in altındaki existing Stats Discovery section artık `/stats` ürün alanının preview layer'ıdır.

Homepage:
- Player Leaders;
- Team Leaders;
- Streaks;
- O/U;
- BTTS;
- supported extra stats
gösterir.

`View All`:
→ ilgili `/stats/...` page.

Homepage bu metric calculation logic'i kendi içinde tekrar etmez.

## 6.30 Canonical Stats Division

```text
/stats
= curated statistical discovery

/stats/power-rankings
= team strength/rating discovery

/stats/teams
= team leaderboards

/stats/players
= player leaderboards

/stats/streaks
= consecutive-pattern discovery

/competition/{slug}
= competition context

/team/{slug}
= team deep research

/player/{slug}
= player deep research

/projections
= future model outputs
```

Bu division Stats'in CalibraXI'ın en zengin alanlarından biri olmasını sağlar ama Forecast/Market semantics'ini bozmaz.

---

# 7. Deep Pages, Research Flow ve Kullanıcı Geri Dönüş Döngüsü

Ana sayfa discovery yüzeyidir. Kullanıcı bir fixture, team, player, league, projection veya market movement gördüğünde daha derine gidebileceği kalıcı bir entity page sistemine sahip olacaktır.

## 7.1 Match Center / H2H Page — FULL WORKING ARCHITECTURE

Her fixture'ın kendi kalıcı detay sayfası vardır.

**Canonical product name:** **Match Center**  
**Working route family:** `/h2h/...`

Aynı iki takım bir sezonda birden fazla kez karşılaşabileceği için URL yalnızca takım isimlerine dayanamaz. Human-readable slug yanında stable Fixture identity korunur.

Örnek:

```text
/h2h/galatasaray-vs-fenerbahce/{fixtureId}
```

`H2H` route ailesidir; sayfanın kullanıcı-facing ana adı **Match Center** olacaktır. Böylece sayfa yalnızca geçmiş karşılaşma istatistiği sunuyormuş gibi daraltılmaz.

### 7.1.1 Match Center'ın temel amacı

Match Center CalibraXI'ın en derin **fixture research surface**'idir.

Kullanıcı başka sayfalarda gördüğü:
- fixture;
- projection;
- player prop;
- power-rating movement;
- odds movement;
- alert;
- Studio leg;
- Track Record item
üzerinden aynı canonical Match Center'a gelir.

Amaç farklı sayfalarda aynı maç için farklı/çelişkili analiz ekranları üretmek değil, tek fixture identity altında bütün ilgili veriyi ve analytical outputs'u birleştirmektir.

### 7.1.2 Karmaşıklık kuralı — One Page, Progressive Depth

Match Center tek dev “her şeyi aynı anda göster” ekranı değildir.

Ana yaklaşım:

```text
Match Identity
→ Match Summary
→ Projections
→ Lineups
→ Matchup
→ Markets
→ History
```

Desktop'ta hero sonrasında sticky local section navigation kullanılabilir:

```text
Summary | Projections | Lineups | Matchup | Markets | History
```

Mobile'da aynı yapı yatay scrollable section chips veya compact sticky selector olarak kullanılabilir.

Ayrı ayrı 12–15 top-level tab oluşturulmaz.

Aşağıdaki içerikler bu altı araştırma alanının içine yerleştirilir:
- player props → Projections;
- team/player stats → Matchup;
- H2H → Matchup;
- injuries/suspensions → Lineups;
- odds comparison/movement → Markets;
- historical runs/snapshots → History;
- live timeline → Summary içindeki state-aware Live Match module.

### 7.1.3 Global shell ile ilişkisi

Match Center ana site shell'ini kullanır:

```text
Optional announcement
Primary Header
Live Match Tracker
Breadcrumb / Match Context
Match Hero
Sticky Match Navigation
Page Content
```

Global Live Match Tracker açıksa ilgili fixture tracker'da da görünmeye devam edebilir.

Sağ global Betslip Match Center'da kullanılabilir.

### 7.1.4 Breadcrumb / Context

Hero'nun üstünde compact context:

```text
Türkiye
> Süper Lig
> Galatasaray vs Fenerbahçe
```

veya:

```text
UEFA
> Champions League
> Arsenal vs Barcelona
```

Context clickable olabilir:
- country;
- competition;
- team entity links.

### 7.1.5 Match Hero — Fixture Identity First

Hero'nun amacı analitik sonuç vermeden önce maçın kimliğini kesin biçimde kurmaktır.

#### Sol team block
- gerçek club crest;
- home team adı;
- competition position uygun olduğunda;
- compact recent form;
- current Power Ranking / OVR snapshot;
- team page link.

#### Orta match block
Upcoming:
- kickoff date;
- kickoff local time;
- countdown uygun olduğunda;
- venue;
- round/stage;
- fixture status.

Live:
- live minute / period;
- current score;
- cards/red cards gibi önemli state cues uygun olduğunda.

Finished:
- final score;
- FT/AET/PEN settlement state gerektiğinde.

#### Sağ team block
Away team için sol team block'un simetriği.

### Hero quick actions

Hero identity alanını boğmadan:

```text
Watch
Compare
Share
Open in Studio
```

bulunabilir.

`+ Add to Betslip` yalnızca exact selectable market/selection context'inde görünür; fixture'ın kendisi bir betslip selection değildir.

### 7.1.6 State Banner

Hero altında fixture state'e bağlı tek satırlık contextual banner bulunabilir.

Upcoming örnekleri:
- `Lineups expected in ~45 min`
- `Confirmed lineups available`
- `New current pre-match run after lineup confirmation`

Live:
- `LIVE — 67'`
- `Pre-match projections remain frozen`
- gelecekte live model varsa `Live projections available` ayrı context olarak.

Finished:
- `Final — evaluations available`
- `Open historical pre-match snapshot`

Postponed:
- new schedule / current status;
- invalidated/replaced schedule context.

Bu banner marketing dili değil, state açıklamasıdır.

### 7.1.7 Section A — Match Summary

Match Summary kullanıcının maçı anlaması için ilk analitik katmandır.

**Amaç:** Kullanıcı bütün sayfayı gezmeden maç hakkında dengeli bir özet elde edebilsin.

Recommended composition:

#### A1. Primary 1X2 Projection

```text
HOME      DRAW      AWAY
48%       27%       25%
```

Varsa:
- current Reliability presentation;
- Forecast time;
- Forecast Cutoff;
- updated/current run context.

En yüksek probability otomatik olarak “pick” veya Recommendation diye etiketlenmez.

#### A2. Key Market Projections

Sınırlı sayıda:
- Over/Under;
- BTTS;
- team total;
- first-half;
- supported relevant market families.

Amaç tüm market tablosunu Summary'e yığmak değildir.

#### A3. CalibraXI View

Bir Recommendation gerçekten varsa ayrı biçimde:

```text
RECOMMENDATION
Over 2.5
...
```

Signal varsa `SIGNAL`.

Sadece Forecast varsa `FORECAST`.

Bu semantic label'lar birbirinin yerine kullanılmaz.

#### A4. Why This Match?

3–5 gerçek driver:

```text
Home ATT strength ↑
Away xGA / defensive process ↓
Home performance at venue ↑
Expected lineup effect ...
```

Bu özet, `Why This Projection?` evidence sisteminden beslenir.

#### A5. Power Comparison

Compact:

```text
        HOME    AWAY
ATT      ...
DEF      ...
OVR      ...
Rank     ...
Δ        ...
```

#### A6. Market Pulse

Özet:
- opening price;
- current best price;
- major movement;
- model-vs-market state;
- last market update.

Detailed source comparison Markets section'ında kalır.

#### A7. Squad Context

Compact:
- lineup status;
- notable absences;
- returnees;
- expected/confirmed formation.

Summary burada yalnızca “önemli context” verir; full lineup aşağıdadır.

### 7.1.8 Section B — Projections

Bu bölüm fixture'a ait bütün supported model-output families için canonical deep projection surface'tir.

#### Projection family navigation

Supported olduğunda:

```text
Result
Goals
BTTS
Team Goals
Periods
Handicap
Corners
Cards
Player Props
Special
```

Sistem support etmediği family'yi boş tab olarak göstermek zorunda değildir.

#### Projection row/card minimum content

Her selection için:
- market/Forecast Target;
- selection;
- probability;
- Reliability/Confidence presentation;
- Forecast Availability;
- current market price varsa best/current odds;
- implied market probability uygun olduğunda;
- edge/value state;
- `Why?`;
- Watch;
- Add to Studio/Betslip.

#### Market context compact, authority separate

Projection row current best price gösterebilir.

Fakat bookmaker/source comparison ve odds timeline burada tekrar edilmez; `View Market` ile Markets section'a iner.

#### Probability hierarchy

Aynı family'deki ilişkili probabilities coherence rules'a uygun şekilde birlikte sunulur.

Örnek 1X2:
- Home;
- Draw;
- Away
aynı parent representation'dan gelir.

Over 2.5'i ayrı model, Under 2.5'i başka “en iyi model” ile doldurmak yasaktır.

#### Expanded Why This Projection?

Kullanıcı bir projection'ı açtığında:
- contributing evidence;
- model/release;
- Forecast Cutoff;
- Reliability drivers;
- applicable lineup context;
- caveats;
- supported historical diagnostics
görebilir.

#### Add / Studio interaction

Bir selection:
- doğrudan Betslip'e eklenebilir;
- veya `Open in Studio` ile current fixture/selection context'i Studio'ya taşır.

Same-match multi-selection oluşturma Match Center içinde ayrı builder UI açmaz; Studio kullanılır.

### 7.1.9 Section C — Lineups & Availability

Bu bölüm kadro bilgisinin canonical fixture yüzeyidir.

#### State classes

```text
Unavailable
Projected / Expected
Probable
Confirmed
Historical confirmed
```

Provider'ın yalnızca “lineup” demesi confirmed anlamına gelmez; source semantics korunur.

#### Pitch View

Confirmed/expected lineup için:
- formation;
- player positions;
- real player headshots uygun olduğunda;
- shirt number;
- captain;
- goalkeeper;
- status cue.

Home ve away formation aynı pitch canvas veya karşılıklı iki pitch olarak gösterilebilir.

Mobile'da:
- Home;
- Away
switcher kullanılabilir.

#### Bench

Starting XI altında:
- substitutes;
- position;
- headshot;
- status.

#### Missing / Doubtful / Suspended

Ayrı listeler:
- injured;
- suspended;
- doubtful;
- unavailable;
- returning.

“Not in lineup” otomatik “injured” sayılmaz.

#### Lineup Impact

Eğer confirmed lineup yeni eligible evidence oluşturup yeni Current Canonical Run doğurduysa:

```text
Before lineups: Home 46%
After lineups:  Home 51%
```

gibi değişim gösterilebilir.

Bu comparison iki exact immutable Prediction Run arasında yapılır.

UI eski Forecast'ı mutate etmiş gibi göstermez.

#### Player click

Player identity:
`/player/{slug}`

Player prop varsa shortcut:
`View player props`.

### 7.1.10 Section D — Matchup

Matchup section H2H + form + team process data'yı birleştirir.

Alt modüller:

#### D1. Recent Form

Her takım için:
- W/D/L sequence;
- goals;
- xG/xGA uygun olduğunda;
- shots/SOT;
- opponent quality;
- home/away relevant split.

Default yalnızca `last 5` göstermek zorunda değildir.

Controls:
- Last 5;
- Last 10;
- season;
- home/away;
- comparable competition scope.

#### D2. Power Ratings

- ATT;
- DEF;
- OVR;
- league rank;
- rank movement;
- recent rating history sparkline.

#### D3. H2H

Recent head-to-head:
- date;
- competition;
- home/away;
- result;
- key stats appropriate olduğunda.

H2H açıkça historical context'tir.

Modelin gerçekten H2H-specific feature kullanmadığı durumda H2H, Forecast'ın “nedeni” olarak sunulmaz.

#### D4. Team Comparison

Side-by-side:
- goals;
- xG;
- shots;
- SOT;
- corners;
- cards;
- possession;
- PPDA veya other advanced stats support varsa;
- clean sheets;
- BTTS;
- Over rates;
- relevant per-90/per-match normalization.

Period/timeframe visible olmalıdır.

#### D5. Streaks

- wins/unbeaten;
- scoring;
- conceding;
- clean sheets;
- BTTS;
- Over/Under;
- first-half;
- team totals;
- corners/cards supported olduğunda.

#### D6. Key Players

Her takımdan relevant leaders:
- goals;
- assists;
- shots;
- SOT;
- xG/xA;
- form;
- current availability.

Click → Player Page.

### 7.1.11 Section E — Markets

Markets section bookmaker/piyasa evidence'ın canonical fixture deep surface'idir.

#### E1. Market selector

```text
1X2
O/U
BTTS
Handicap
Team Totals
...
```

#### E2. Odds Comparison

Source/bookmaker table:
- bookmaker/source;
- selection;
- price;
- timestamp;
- best-price marker;
- availability.

CalibraXI bahis işlemi yapmaz.

#### E3. Market Consensus

Support varsa:
- quoted implied probability;
- margin;
- normalized/no-vig context;
- consensus range.

Consensus Forecast değildir.

#### E4. Odds Movement

Timeline:
- opening;
- intermediate points;
- current;
- high/low;
- movement %;
- quote timestamps.

#### E5. Model vs Market

```text
Model probability
Market implied / normalized probability
Difference
Fair contract value
Signal state
```

yalnızca exact compatible contract ve point-in-time evidence varsa gösterilir.

#### E6. Selection action

`+`:
- Betslip'e selection ekler.

`Studio`:
- Studio context'i açar.

### 7.1.12 Section F — History

History Match Center'ın “CalibraXI o anda ne biliyordu?” alanıdır.

#### Run Timeline

Pre-match run'lar:
- initial;
- later data update;
- lineup update;
- final pre-kickoff run
gibi exact immutable identities ile listelenebilir.

User bir run seçtiğinde:
- Forecasts;
- Reliability;
- known lineup state;
- odds snapshot;
- Signals;
- Recommendations
o run/as-of bağlamında gösterilir.

#### Historical Snapshot Mode

Finished fixture'da prominent:

```text
View Pre-Match Snapshot
```

Bu mode:
- match sonucu;
- post-match stats
gibi future information'ı Forecast explainability'ye bulaştırmaz.

#### Outcome & Evaluation

Finished olduğunda:
- authoritative result;
- settlement;
- selection evaluations;
- Recommendation outcome;
- Studio builder outcome uygun olduğunda;
- public Track Record population'a dahil olup olmadığı
gösterilebilir.

#### Track Record link

`View this artifact in Track Record`

kullanıcıyı exact historical evaluation'a götürür.

### 7.1.13 Live Match Center Behavior

Match Center identity live olduğunda değişmez.

Hero:
- current score;
- minute/period;
- match events.

Summary'nin üst kısmına bir **Live Match module** gelir:
- score;
- timeline;
- possession/shots/SOT gibi live stats available ise;
- major events;
- cards/substitutions;
- momentum chart yalnızca reliable event stream varsa.

### PRE_MATCH visibility while live

Pre-match analytical artifacts kaybolmaz.

Ayrı label:

```text
PRE-MATCH VIEW
Forecast frozen before kickoff
```

ile gösterilir.

### LIVE Forecast boundary

Eğer CalibraXI henüz LIVE Forecast Capability yayınlamıyorsa:

```text
Live score & stats available
Live projections not available
```

denir.

Pre-match probability live score'a göre UI içinde recalculated gösterilmez.

Gelecekte LIVE Forecast varsa:
- ayrı LIVE Run Context;
- ayrı currentness;
- ayrı probability;
- ayrı Reliability;
- PRE_MATCH ile açıkça ayrılmış görünüm
kullanılır.

### 7.1.14 Finished Match Center Behavior

Finished Match Center'ın üstünde:

- final score;
- outcome state;
- fixture statistics;
- timeline;
- historical pre-match view
öne çıkar.

Default page şu iki şeyi aynı anda gösterebilir:

```text
FINAL RESULT
2–1

PRE-MATCH CALIBRAXI VIEW
...
```

Ama sonuç bilgisi historical Forecast'ın probability/reasoning alanını rewrite etmez.

Post-match modules:
- result;
- key stats;
- lineups;
- events;
- Forecast evaluation;
- Signal/Recommendation evaluation;
- historical odds;
- Track Record link.

### 7.1.15 Postponed / Cancelled / Abandoned

Bu state'ler normal upcoming/finished gibi gösterilmez.

- schedule revision;
- disposition;
- new kickoff varsa;
- market suspension;
- current analytical availability
explicit olur.

Historical runs queryable kalır.

### 7.1.16 Match Center Right Rail / Secondary Surface

Default Match Center için ikinci kalıcı sağ rail zorunlu değildir; çünkü global Betslip zaten sağ panel davranışına sahiptir.

Large screens'de contextual mini-rail düşünülebilir:
- Watch state;
- quick navigation;
- relevant alert;
- next/previous fixture.

Ama analytical content iki ayrı sağ rail'e bölünmez.

### 7.1.17 Sticky Match Navigation

Hero'dan sonra scroll ile sticky hale gelebilir:

```text
Summary
Projections
Lineups
Matchup
Markets
History
```

Active section scroll konumuna göre değişir.

Deep link desteklenebilir:

```text
/h2h/.../{fixtureId}#projections
/h2h/.../{fixtureId}#lineups
/h2h/.../{fixtureId}#markets
```

Notification veya external link kullanıcıyı doğrudan doğru module'e indirebilir.

### 7.1.18 Match Center Search/Share Semantics

Share link stable Fixture identity'yi kullanır.

Sayfa title/OG metadata:
- home;
- away;
- competition;
- kickoff/state
ile güncellenebilir.

Finished fixture'ın URL'si değişmez.

### 7.1.19 Mobile Match Center

Mobile hierarchy:

```text
Compact context
Hero / score
Quick actions
Sticky section chips
Summary
Projections
Lineups
Matchup
Markets
History
```

Kurallar:
- 1X2 probabilities yan yana okunabilir kalmalı;
- odds table horizontal overflow yerine bookmaker rows/cards'a adapte olabilir;
- formation pitch responsive olmalı;
- player headshots aşırı küçük olmamalı;
- Betslip bottom sheet;
- `+` touch target yeterli;
- large comparison tables progressive disclosure kullanmalı.

### 7.1.20 Match Center Visual Direction

Light-first.

Hero:
- clean white/off-white;
- real club crests;
- strong typography;
- muted competition context;
- restrained brand accent.

Analytical modules:
- probability semantic treatment;
- Reliability treatment;
- market movement colors;
- outcomes
brand accent'ten bağımsız tutulur.

Bütün section'ları aynı rounded card sistemine sokmak yasaktır.

Önerilen visual rhythm:

```text
IDENTITY HERO

SUMMARY GRID

FULL-WIDTH PROJECTION MATRIX

VISUAL LINEUP / PITCH

SIDE-BY-SIDE MATCHUP

MARKET TABLE + CHART

HISTORICAL TIMELINE
```

### 7.1.21 Match Center İlk Viewport Working Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Brazil > Serie A > Flamengo vs Palmeiras                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   [FLA CREST]          20:30 / UPCOMING                 [PAL CREST]           │
│   Flamengo          Maracanã · Round 27                   Palmeiras           │
│   OVR 1.18                                                OVR 1.09            │
│   W W D W L                                               W D W L W           │
│                                                                              │
│              Watch   Compare   Share   Open in Studio                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Summary | Projections | Lineups | Matchup | Markets | History               │
├───────────────────────────────────────────────────────┬──────────────────────┤
│ MODEL VIEW                                            │ MATCH CONTEXT        │
│                                                       │                      │
│ HOME          DRAW          AWAY                       │ Power Edge           │
│ 48%           27%           25%                        │ Flamengo +...        │
│                                                       │ Lineups: Expected    │
│ O2.5  61%   BTTS 58%   Home O0.5 82%                 │ 2 notable absences  │
│                                                       │ Market move ...      │
│ Reliability ...    Forecast cutoff ...                │                      │
│                                                       │                      │
│ Why this match?                                       │                      │
│ • ...                                                 │                      │
│ • ...                                                 │                      │
└───────────────────────────────────────────────────────┴──────────────────────┘
```

### 7.1.22 Match Center Canonical User Flows

#### Projection flow

```text
Homepage Top Projection
→ Match Center #projections
→ Why This Projection?
→ Markets
→ Add selection
→ Betslip / Studio
```

#### Lineup flow

```text
Alert: Lineups Confirmed
→ Match Center #lineups
→ Confirmed XI
→ inspect exact new current run if one exists
→ Projections
```

#### Player flow

```text
Player Props
→ Match Center #projections/player-props
→ player card
→ Player Page
```

#### Odds flow

```text
Odds Movement alert
→ Match Center #markets
→ movement timeline
→ model vs market
→ selection
```

#### Historical audit flow

```text
Track Record
→ Match Center #history
→ exact historical run
→ historical projection + odds
→ outcome evaluation
```

### 7.1.23 Match Center Non-Goals

Match Center:
- yeni Forecast hesaplamaz;
- “latest row” seçerek Current Canonical Run icat etmez;
- raw stat'i Forecast diye sunmaz;
- odds movement'ı model change gibi sunmaz;
- result geldikten sonra geçmiş probability'yi değiştirmez;
- H2H record'u otomatik causal evidence yapmaz;
- unsupported market için tahmini sayı uydurmaz;
- ayrı bir Match Builder yaratmaz; Studio kullanır;
- Betslip'i bookmaker checkout'a dönüştürmez.

### 7.1.24 Working Decision

**Canonical Match Center structure:**

```text
Identity
→ Summary
→ Projections
→ Lineups
→ Matchup
→ Markets
→ History
```

Fixture state bu yapının içeriğini değiştirir; fixture identity veya analytical authority'yi değiştirmez.

Bu yapı homepage'in sade kalmasını sağlar: homepage keşif ve scan yüzeyi, Match Center ise derin araştırma yüzeyidir.

## 7.2 Competition Pages — FULL WORKING ARCHITECTURE

Her league, cup, tournament veya group-stage competition'ın canonical entity page'i vardır.

**Canonical route:**

```text
/competition/{slug}
```

UI'da competition türüne göre `League`, `Cup`, `Tournament` denebilir; route/domain family ayrılmaz.

### 7.2.1 Competition Hero

- real competition logo;
- country/region;
- competition name;
- current season;
- stage/round context;
- Follow/Watch;
- season selector.

Example:

```text
[PREMIER LEAGUE LOGO]
Premier League
England · 2026/27

[Follow]   Season ▼
```

### 7.2.2 Competition Local Navigation

```text
Overview
Standings
Fixtures
Power Rankings
Teams
Players
Stats
Projections
```

Knockout-only competition için `Standings` yerine:
- Bracket;
- Groups;
- Rounds
gibi semantics kullanılabilir.

Template competition format'a adapte olur.

### 7.2.3 Competition Overview

- current table / stage snapshot;
- next fixtures;
- recent results;
- Power Rankings preview;
- top team stats;
- top player stats;
- active streaks;
- projection preview;
- key season context.

### 7.2.4 Standings

Canonical sporting table:
- position;
- team;
- played;
- W/D/L;
- GF/GA/GD;
- points;
- qualification/relegation zones.

League standings **Power Rankings değildir**.

İkisi yan yana gösterilebilir ama semantic labels net kalır.

### 7.2.5 Fixtures & Results

Controls:
- round/matchweek;
- date;
- upcoming/results;
- stage.

Fixture click:
→ Match Center.

### 7.2.6 Competition Power Rankings

Same canonical Power Rating system, filtered to competition population.

Show:
- Rank;
- ATT;
- DEF;
- OVR;
- Δ.

CTA:
→ full `/stats/power-rankings?competition=...`.

### 7.2.7 Competition Team Leaders

Examples:
- goals;
- xG;
- shots;
- SOT;
- clean sheets;
- BTTS;
- O/U;
- corners/cards.

Team row:
→ Team Page.

### 7.2.8 Competition Player Leaders

Examples:
- goals;
- assists;
- shots;
- SOT;
- xG/xA;
- cards;
- goalkeeper metrics.

Player:
→ Player Page.

### 7.2.9 Competition Projections

Preview:
- next fixture projections;
- team outrights if supported;
- top player props.

`View all`:
→ `/projections?...competition=...`

Projection engine burada duplicate edilmez.

### 7.2.10 Competition Track Record

Optional trust module:
CalibraXI performance for this competition:
- exact population;
- period;
- Forecast/Recommendation type;
- sample size.

CTA:
→ `/track-record?competition=...`

### 7.2.11 Competition Page State

Season selector historical season açtığında:
- historical standings;
- historical fixtures;
- historical stats
gösterilebilir.

Current projections historical season'a yapıştırılmaz.

### 7.2.12 Competition First Viewport

```text
Premier League
England · 2026/27

Overview | Standings | Fixtures | Power Rankings | Teams | Players | Stats

TABLE SNAPSHOT                    NEXT FIXTURES
#1 Arsenal  ...                   Arsenal vs ...
#2 Liverpool ...                 ...
#3 City ...                       ...

POWER RANKINGS                    TOP PLAYERS
...
```

## 7.3 Team Pages — FULL WORKING ARCHITECTURE

Canonical route:

```text
/team/{slug}
```

Team Page takımın season-long ve current-state araştırma merkezidir.

### 7.3.1 Team Hero

- real club crest;
- club name;
- country;
- current competition(s);
- current league position;
- current Power Ranking;
- ATT;
- DEF;
- OVR;
- current form;
- Follow;
- Compare.

Optional:
- stadium;
- manager
yalnızca reliable source data varsa.

### 7.3.2 Team Local Navigation

```text
Overview
Fixtures
Form
Power
Stats
Squad
Projections
History
```

### 7.3.3 Team Overview

Above fold:
- current Power summary;
- league position;
- recent form;
- next fixture;
- latest result;
- current projection preview;
- key team stats;
- active streaks;
- important squad availability.

### 7.3.4 Team Fixtures

Two groups:
- upcoming;
- results.

Filters:
- competition;
- season;
- home/away.

Fixture click:
→ Match Center.

### 7.3.5 Team Form

Controls:
- Last 5;
- Last 10;
- Last 20;
- season;
- home;
- away.

Display:
- W/D/L;
- goals;
- xG/xGA;
- shots/SOT;
- opponent strength;
- scorelines.

Form ≠ Power Rating.

### 7.3.6 Team Power

- current ATT;
- DEF;
- OVR;
- competition rank;
- historical rank;
- rating history graph;
- biggest movements.

Exact snapshot dates visible.

### 7.3.7 Team Stats

Metric groups:
- attack;
- defense;
- possession/build-up;
- shooting;
- set pieces;
- discipline;
- goals/totals;
- streaks.

Context:
- league rank;
- percentile;
- home/away;
- recent vs season.

### 7.3.8 Squad

Real player photos when licensed/available.

Groups:
- Goalkeepers;
- Defenders;
- Midfielders;
- Forwards.

Player:
- name;
- age if supported;
- position;
- shirt number;
- minutes;
- starts;
- selected output stats;
- availability.

Click:
→ Player Page.

### 7.3.9 Availability

Separate semantic states:
- available;
- injured;
- suspended;
- doubtful;
- unavailable;
- returning.

Team Page current availability is not historical lineup truth for older fixtures.

### 7.3.10 Team Projections

Team-related current supported outputs:
- upcoming fixture projections;
- Team Outrights;
- team totals;
- related player props;
- current Recommendations/Signals if relevant.

Deep link:
→ Projections / Match Center.

Team Page does not recalculate Forecasts.

### 7.3.11 Team History

- prior seasons;
- competition participation;
- Power Rating history;
- results history;
- historical CalibraXI projections access as appropriate.

### 7.3.12 Team Alerts

User can configure:
- next match;
- lineup;
- Power Ranking movement;
- projection threshold;
- odds/value change;
- player availability.

Managed:
→ `/my/alerts`.

### 7.3.13 Team First Viewport

```text
[ARSENAL CREST]
Arsenal
Premier League · #2

Power Rank #1
ATT ...
DEF ...
OVR ...
Form W W D W L

[Follow] [Compare]

NEXT MATCH
Arsenal vs Liverpool
Saturday 20:00

CURRENT SNAPSHOT
League position | Power | Goals | xG | Clean Sheets
```

## 7.4 Player Pages — FULL WORKING ARCHITECTURE

Canonical route:

```text
/player/{slug}
```

Player Page historical stats ile future Player Props'u aynı sayfada fakat ayrı semantic sections olarak birleştirir.

### 7.4.1 Player Hero

- real player photo/headshot;
- name;
- current club crest + name;
- position;
- shirt number if supported;
- nationality if supported;
- age if supported;
- Follow;
- Compare.

### 7.4.2 Player Local Navigation

```text
Overview
Stats
Matches
Props
Form
History
```

### 7.4.3 Player Overview

- current season minutes;
- starts;
- goals;
- assists;
- selected xG/xA;
- shots/SOT;
- current form;
- next fixture;
- current prop preview if available;
- availability status.

### 7.4.4 Player Stats

Metric families depend on position.

Attacker:
- goals;
- xG;
- shots;
- SOT;
- assists;
- xA;
- chances.

Midfielder:
- creation;
- passes;
- progression;
- tackles
source support'a göre.

Defender:
- tackles;
- interceptions;
- aerial;
- cards;
- passing
as supported.

Goalkeeper:
- saves;
- save%;
- clean sheets;
- goals conceded;
- advanced GK metrics if valid.

### 7.4.5 Total vs Per 90

Toggle:

```text
Total
Per 90
Per Match
```

Minimum minutes sample displayed.

### 7.4.6 Player Match Log

Rows:
- date;
- opponent;
- competition;
- starter/bench;
- minutes;
- key stats;
- result.

Click:
→ Match Center.

### 7.4.7 Player Form

Recent:
- minutes;
- starts;
- shots;
- SOT;
- goals;
- assists;
- relevant role metrics.

A 10-minute substitute appearance weighted/displayed appropriately; raw per-match average should not silently equal full-match appearance.

### 7.4.8 Player Props

Current supported future props:

```text
Shots
SOT
Goal
Assist
Cards
etc.
```

Each:
- line;
- probability;
- Reliability;
- lineup/minutes context;
- market price if compatible;
- Why?;
- Match Center;
- `+`.

Historical player stats are not used as direct prop probability display.

### 7.4.9 Player Availability

States:
- expected starter;
- confirmed starter;
- bench;
- injured;
- suspended;
- doubtful;
- unavailable
when source supports.

Current state is timestamped/contextual.

### 7.4.10 Player Transfer Context

Current profile reflects current club.

Historical match logs preserve historical club.

Stats filters can use:
- current club only;
- all clubs in selected season
if meaningful.

No historical event is rewritten after transfer.

### 7.4.11 Player History

- season-by-season totals;
- clubs;
- competitions;
- role/minutes;
- historical prop evaluations if appropriate.

### 7.4.12 Player Alerts

Possible:
- prop becomes available;
- confirmed starting;
- prop probability crosses threshold;
- odds threshold;
- injury/availability update.

### 7.4.13 Player First Viewport

```text
[player photo]
Bukayo Saka
Arsenal · RW · #7

2026/27
Minutes  ...
Goals    ...
Assists  ...
xG       ...
SOT/90   ...

[Follow] [Compare]

NEXT MATCH
Arsenal vs Liverpool

CURRENT PROPS
SOT O1.5  ...
Shots O2.5 ...
```

### 7.4.14 Entity Page Shared Rules

Competition, Team ve Player pages:
- canonical entity identity taşır;
- real licensed identity assets kullanır;
- historical stats ile future Forecast'ı ayırır;
- current vs historical state'i açık tutar;
- relevant Match Center'a bağlanır;
- relevant Projections'a bağlanır;
- Follow/Watch destekler;
- Compare appropriate olduğunda destekler.

Bu pages ayrı hesaplama authority'si değildir.

## 7.5 Markets / Odds / Value — FULL WORKING ARCHITECTURE

CalibraXI'ın **Markets** alanı bookmaker/exchange fiyat gözlemlerini, line movement'ı, best-price context'ini ve model-vs-market karşılaştırmasını inceler.

Temel product boundary:

```text
PROJECTIONS
= CalibraXI ne olacağını düşünüyor?

STATS
= geçmiş veride ne oldu?

MARKETS
= piyasa exact contract'ı nasıl fiyatlıyor?

SIGNAL
= compatible Forecast + contract + market evidence üzerinde governed evaluation

RECOMMENDATION
= Signal'dan sonra gelen ayrı user-facing decision layer
```

Markets alanı Forecast üretmez ve odds'u Forecast'a feedback olarak sokmaz.

### 7.5.1 Canonical Markets Routes

```text
/markets
├── /value
├── /odds-movement
├── /best-prices
└── /movers
```

Working meanings:

- `/markets` — market analytics overview / Market Pulse;
- `/markets/value` — model-vs-market / Fair Value / Signal-oriented read surface;
- `/markets/odds-movement` — fixture/contract price timelines;
- `/markets/best-prices` — exact selection için source-by-source best observed/current quotes;
- `/markets/movers` — selected scope'taki anlamlı price/line movements.

Launch'ta ayrı `/markets/consensus` route'u zorunlu değildir. Source-specific, consensus ve best-price comparison modes aynı market context içinde açıkça ayrılarak gösterilebilir.

### 7.5.2 Market Observation — Canonical Boundary

Bir **Market Observation**:
- external market evidence'dır;
- bir exact Betting Contract + Selection'a bağlanır;
- bir source/bookmaker/exchange'den gelir;
- immutable historical observation'dır.

Conceptually korunacak minimum context:
- Fixture/Event;
- exact Betting Contract;
- period;
- subject;
- market family;
- operator/line;
- selection;
- settlement specification;
- source/bookmaker/exchange;
- original quote representation;
- normalized display representation varsa;
- quote/observation time;
- source availability time;
- market Knowledge Time;
- processing/receipt provenance;
- market state;
- correction/replay lineage;
- commission/liquidity convention relevant olduğunda;
- quality/integrity state.

**Mutable `latest odds` satırı historical authority değildir.**

UI current quote gösterebilir fakat historical timeline immutable observations'dan türetilir. Bu, legacy Signal Architecture'daki Market Observation chronology sınırını korur. fileciteturn17file2L1-L1

### 7.5.3 Exact Betting Contract Rule

Market comparison exact contract üzerinden yapılır.

Uyum gereken dimensions, applicable olduğunda:
- fixture;
- period;
- subject;
- market family;
- operator;
- line;
- selection;
- settlement rules;
- push/void;
- extra-time/overtime treatment;
- score-period semantics;
- payout/commission convention.

Örnek:

```text
Over 2.5 @ 1.85
```

ile

```text
Over 3.0 @ 1.92
```

aynı contract değildir.

Aynı movement chart'a tek continuous price series gibi yapıştırılmaz.

Likewise:
- Full Time Over 2.5;
- First Half Over 2.5
aynı market değildir.

### 7.5.4 Forecast Time vs Market Time

İki zaman ekseni ayrı tutulur:

```text
Forecast Cutoff
Market Knowledge Time
```

Örneğin Forecast 14:00'te üretilmiş olabilir ve aynı immutable Forecast:
- 14:05 market quote;
- 15:30 quote;
- 18:00 quote
ile ayrı Signal Evaluation / market comparisons içinde kullanılabilir.

Yeni odds:
**yeni Forecast Run yaratmak zorunda değildir.**

Yeni odds:
**eski Forecast probability'yi değiştirmez.**

Aynı şekilde yeni Forecast Run eski Market Observation'ı rewrite etmez.

### 7.5.5 Market State

User-facing market state, gerektiğinde:

```text
Open
Suspended
Closed
Unavailable
Corrected
Historical
```

olarak gösterilebilir.

Stale/integrity problemi varsa best/current claim yapılmaz.

Generic “Data Freshness Badge” hâlâ deferred'dır; fakat market quote'ın timestamp ve state'i market semantics'in zorunlu parçasıdır.

### 7.5.6 Odds Display Convention

UI default display:
**Decimal Odds**

olabilir.

User setting olarak ileride:
- Decimal;
- Fractional;
- American
representation desteklenebilir.

Price conversion:
- sadece representation conversion'dır;
- bookmaker margin'ı kaldırmaz;
- market probability oluşturmaz;
- Forecast'ı değiştirmez.

### 7.5.7 Markets Hub — `/markets`

Markets Hub price-first araştırma ana sayfasıdır.

Vertical composition:

```text
Markets Header
Date / Time Scope
Competition + Market Filters
Market Pulse
Model vs Market
Biggest Movers
Best Prices
Odds Movement Preview
Watched Markets
Methodology / Market Definitions
```

Hub aynı anda yüzlerce bookmaker satırı gösteren sportsbook odds grid'i olmayacaktır.

Amaç:
**scan → understand → drill down**

### 7.5.8 Markets Header

```text
MARKETS
Prices, movement and model-vs-market context.

Today | Tomorrow | Weekend | Next 7 Days | Custom
3H | 6H | 12H

Competition ▼
Market ▼
```

Optional controls:
- source;
- comparison mode;
- odds display format.

### 7.5.9 Market Pulse

İlk analitik overview.

Potential compact counts:
- tracked fixtures;
- open observed contracts;
- significant movements;
- current qualified model-vs-market comparisons;
- watched market changes.

Count yalnızca read model gerçekten destekliyorsa gösterilir.

“27 value bets” gibi Recommendation çağrışımı yapan copy kullanılmaz.

### 7.5.10 Market Comparison Modes

Aynı odds data üç farklı soruya cevap verebilir.

#### A. Source-Specific

> Belirli bir bookmaker/source bu exact marketi nasıl fiyatlıyor?

Requires:
- named source;
- coherent same-source quote set;
- valid synchronization when normalized market probability is calculated.

#### B. Best Observed / Best Offered Price

> Bu exact selection için policy-qualified sources içinde en iyi gözlenen/current quote hangisi?

Bu:
- selection-specific price comparison'dır;
- market belief distribution değildir.

User-facing safer term:
**Best observed price**
veya policy gerçekten executability doğruluyorsa:
**Best available price**.

CalibraXI gerçek bet placement yapmadığı için “you can definitely get this price” gibi claim yapılmaz.

#### C. Consensus

> Governed multi-source transformation piyasayı topluca nasıl temsil ediyor?

Consensus:
- source set;
- exclusions;
- timing;
- weighting;
- normalization;
- outlier handling;
- missingness;
- source quality
tanımlayan versioned method ister.

**Consensus daha fazla source kullandığı için otomatik truth değildir.** Bu ayrım eski Signal Architecture ile uyumludur. fileciteturn17file7L1-L1

### 7.5.11 Source-Specific Market Probability

Decimal quote için:

```text
quoted_implied = 1 / odds
```

yalnızca **quoted implied probability**'dir.

Bu doğrudan fair/no-vig market probability değildir.

Örneğin 1X2 için source-specific normalized market view üretilecekse normalde:
- Home;
- Draw;
- Away

aynı:
- source;
- exact market;
- relevant line;
- governed observation epoch
içinden coherent set olarak alınmalıdır.

HOME A bookmaker'dan, DRAW B bookmaker'dan, AWAY C bookmaker'dan seçilip:

`market probability`

diye sunulmaz.

Legacy architecture bunu özellikle yasaklar. fileciteturn17file0L1-L1

### 7.5.12 Margin / Overround Presentation

Complete compatible set mevcut olduğunda:

```text
Quoted implied probabilities
Overround / margin context
Normalized market estimate (if supported)
Normalization method
```

gösterilebilir.

Örnek conceptual display:

```text
HOME   quoted 51.0%
DRAW   quoted 28.6%
AWAY   quoted 25.0%

Quoted sum: 104.6%
```

No-vig percentages ancak versioned normalization method uygulanabiliyorsa gösterilir.

UI:
- proportional;
- power;
- Shin-style;
- etc.
arasından kendi kafasına göre yöntem seçmez.

Universal method henüz frozen değildir.

### 7.5.13 Best Prices — `/markets/best-prices`

Amaç:
exact selection için sources arasındaki quote comparison.

Example row:

```text
Arsenal vs Liverpool
Over 2.5

Source A   1.78   19:42
Source B   1.82   19:41
Source C   1.76   19:43

Best observed: 1.82
```

Filters:
- date/time;
- competition;
- fixture;
- market family;
- selection;
- line;
- source;
- min/max odds.

Sort:
- kickoff;
- best observed price;
- source spread;
- recent change.

### Important boundary

Best price:
- tek selection için kullanılabilir;
- diğer outcomes'tan independently cherry-pick edilip “market consensus” diye sunulmaz.

### Source Spread

Useful metric:

```text
Highest observed quote
Lowest observed quote
Spread
```

Source disagreement göstergesi olabilir.

Ama büyük spread:
- “bookmaker hata yaptı”;
- “sure value”;
- “smart money”
demek değildir.

### 7.5.14 Odds Movement — `/markets/odds-movement`

Price timeline exact contract bazındadır.

Example:

```text
Over 2.5

12:00   1.95
14:30   1.90
17:10   1.82
19:20   1.74
```

Show:
- opening observed quote;
- current quote;
- high/low observed;
- absolute change;
- percentage price change appropriate olduğunda;
- timestamps;
- source;
- status.

### Movement views

```text
Single Source
Best Observed
Governed Consensus
```

aynı chart semantics'e sahip değildir ve ayrı labels kullanır.

### Opening price

`Opening`:
- product/source policy ile tanımlanmalıdır;
- ilk database row = universal opening price varsayımı yapılmaz.

### Closing price

Closing price yalnızca:
- market kapanışı/kickoff sonrasında;
- historical evaluation context'inde
kullanılır.

Pre-match 16:00 ekranı gelecekteki closing quote'u göremez.

### 7.5.15 Price Movement vs Line Movement

İki farklı olaydır.

#### Price Movement

Same exact contract:

```text
O2.5
1.95 → 1.75
```

#### Line Movement

Contract line değişir:

```text
O2.5
→ O3.0
```

Line movement visual:
- market line trajectory;
- selection prices around each line
gösterebilir.

Ama O2.5 price ile O3.0 price tek series'miş gibi birleştirilmez.

### 7.5.16 Market Movers — `/markets/movers`

Movers seçilen scope'taki material changes discovery page'idir.

Possible mover classes:

- largest shortening;
- largest drifting;
- significant line move;
- largest source spread change;
- consensus shift if governed;
- newly suspended/reopened market;
- best-price change.

Filters:
- date/time;
- competition;
- market;
- source;
- movement class;
- threshold.

### Important language

Movement nedeni bilinmiyorsa UI:

`Significant market move`

der.

Aşağıdaki ifadeler evidence olmadan kullanılmaz:
- sharp money;
- insider move;
- smart money;
- informed betting;
- bookmaker knows something.

Market movement bir observation'dır; motive inference değildir.

### 7.5.17 Market Mover Card

```text
MARKET MOVE

Arsenal vs Liverpool
Over 2.5

Source A
1.94 → 1.76
-9.3% price

18:05 → 19:22

Model probability: 61%
[Open Match] [View Timeline] [Watch]
```

Model probability kartta context olabilir ama move'un nedeni gibi sunulmaz.

### 7.5.18 Model vs Market — Conceptual Boundary

Model-vs-market comparison yalnızca:
- exact compatible Forecast Target;
- exact Betting Contract;
- valid Market Observation;
- applicable normalization/price basis
varsa yapılır.

Potential displayed quantities:

```text
Model Probability
Quoted Implied Probability
Normalized Market Probability (if valid)
Model Fair Price / Fair Contract Value
Observed Price
Probability Edge (where defined)
Price Advantage (where defined)
EV (where contract-valid)
```

Bunlar aynı metric değildir.

### 7.5.19 Fair Contract Value

Simple binary no-push decimal contract için:

```text
fair odds = 1 / p
```

olabilir.

Ama bu universal formül değildir.

Complex contracts:
- Asian handicap;
- Asian totals;
- quarter lines;
- integer push lines;
- draw no bet;
- dead heat;
- partial settlement;
- exchange commission;
- void/refund cases

için full settlement/payoff semantics gerekir.

Legacy Signal Architecture Fair Contract Value'yu exact contract settlement distribution'ından türetilen downstream valuation olarak tanımlar; bookmaker odds Forecast'ı değiştiremez. fileciteturn17file1L1-L1

### 7.5.20 Expected Value Presentation

Simple valid binary example:

```text
EV/unit = p × decimal_odds - 1
```

yalnızca matematiksel olarak contract uygunsa kullanılır.

UI complex marketlerde aynı formülü zorla uygulamaz.

EV:
- Probability değildir;
- Reliability değildir;
- Recommendation değildir.

### 7.5.21 `/markets/value` — Model vs Market / Signal Surface

`Value` route product name olarak kalabilir fakat semantics kesindir.

Page purpose:

> Canonical Forecast + exact contract + market evidence arasında governed comparison olan durumları incelemek.

Bu page:
- yeni Forecast üretmez;
- edge'i Recommendation'a dönüştürmez;
- positive EV'i “bet” diye etiketlemez.

### Value Result Row

Potential:

```text
MODEL VS MARKET

Arsenal vs Liverpool
Over 2.5

Model Probability      61%
Model Fair Price       1.64

Best Observed Price    1.82
Reference Market       ...
Normalized Market      55%   (if valid)

Probability Edge       +6pp
EV / unit              ...   (if contract-valid)

Reliability            ...
Signal State           Eligible / Not eligible / Cannot evaluate

[Why?] [Market Timeline] [Open Match] [+]
```

### 7.5.22 Market Edge vs Signal vs Recommendation

Canonical hierarchy:

```text
Positive Market Edge
≠ Eligible Signal
≠ Recommendation
```

Possible:
- edge positive but quote stale;
- edge positive but contract mismatch;
- edge positive but source integrity insufficient;
- edge positive but Signal Policy says NOT_ELIGIBLE;
- eligible Signal but no Recommendation published.

User-facing design bu ayrımları saklamaz.

### 7.5.23 Signal State Presentation

Internal authority:
- ELIGIBLE;
- NOT_ELIGIBLE;
- CANNOT_EVALUATE.

User copy daha anlaşılır olabilir:

```text
Signal available
Not signal-eligible
Cannot evaluate
```

Ama mapping deterministic olmalıdır.

`CANNOT_EVALUATE`:
negative edge demek değildir.

`NOT_ELIGIBLE`:
Forecast yanlış demek değildir.

### 7.5.24 Value Filters

`/markets/value` filters:

- date/time;
- competition;
- fixture;
- market family;
- selection;
- line;
- source/comparison basis;
- Forecast probability;
- Reliability band if governed;
- odds range;
- probability edge;
- EV range if contract-valid;
- Signal state;
- Recommendation available yes/no.

Sort:
- curated/relevance;
- kickoff;
- probability edge;
- price advantage;
- EV where comparable;
- current update.

Sort by edge:
Recommendation ranking değildir.

### 7.5.25 Market Detail in Match Center

Markets dedicated hub bir fixture için ayrı truth oluşturmaz.

Fixture-specific market deep view:
→ Match Center `#markets`.

Burada:
- exact market selector;
- source comparison;
- odds movement;
- normalized market context;
- model-vs-market
tek fixture bağlamında gösterilir.

`/markets/...` discovery pages:
→ Match Center'a deep-link eder.

### 7.5.26 Market Watch + Alerts

User watch types:

- exact selection price;
- source price;
- best observed price;
- line;
- model-vs-market edge state;
- Signal state.

Alert examples:

```text
Notify me if Over 2.5 best observed price >= 1.90
Notify me if line moves from 2.5 to 3.0
Notify me if model-vs-market edge crosses X
Notify me when Signal becomes eligible
```

Alert:
- existing governed data üzerinde çalışır;
- Forecast yaratmaz;
- Recommendation yaratmaz.

### 7.5.27 Price Threshold Jitter

Odds 1.89 ↔ 1.90 gibi küçük salınımlar spam yaratmamalıdır.

Alert policy:
- debounce;
- hysteresis;
- cooldown;
- material change threshold
kullanabilir.

Exact threshold semantics Engineering'de tanımlanır.

### 7.5.28 Market Saved Views

Market filter state login user tarafından kaydedilebilir.

Examples:

```text
Premier League — O2.5 movers
Next 6H — 1X2 best prices
Watched Teams — model vs market
```

Stored:
- query/filter definition.

Not stored as:
- analytical truth.

Saved Market View:
→ `/my/saved`.

### 7.5.29 Market Selection Actions

Exact current selection context varsa actions:

```text
Watch
Open Match
Compare Sources
View Movement
+
Open in Studio
```

`+`:
virtual Betslip'e selection ekler.

Gerçek bookmaker checkout'a yönlendirme bu ürün kararının parçası değildir.

### 7.5.30 Market Comparison Table

Desktop example:

```text
Arsenal vs Liverpool — 1X2

SOURCE      HOME      DRAW      AWAY      STATUS     QUOTED
A           1.92      3.60      4.10      Open       19:42
B           1.95      3.50      4.00      Open       19:43
C           1.89      3.70      4.20      Open       19:41
```

Below:
- source-specific margin;
- normalized set if valid;
- best observed price per selection in a **separate** row.

The best-per-selection row is explicitly:

```text
BEST OBSERVED PRICES
```

not:
```text
MARKET CONSENSUS
```

### 7.5.31 Market Chart Design

Odds movement chart:
- line chart;
- time x-axis;
- price y-axis;
- source selection visible.

Multiple sources:
- user explicitly toggles sources;
- dozens of lines default render edilmez.

Line market:
- line/handicap movement ayrı visualization.

Model probability:
- optional separate panel/chart;
- odds line ile same y-axis'a bind edilmez.

### 7.5.32 Market First Viewport

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ MARKETS                                                                      │
│ Prices, movement and model-vs-market context                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Today Tomorrow Weekend 7D Custom | 3H 6H 12H | Competition ▼ | Market ▼   │
├──────────────────────────┬──────────────────────────┬────────────────────────┤
│ MODEL vs MARKET          │ BIGGEST MOVERS          │ BEST PRICE CHANGES     │
│                          │                          │                        │
│ Arsenal-Liverpool O2.5   │ Milan-Roma U2.5         │ PSG ML                 │
│ Model 61%                │ 1.94 → 1.74             │ 1.61 → best 1.72       │
│ Market 55%               │ View movement →         │ Compare sources →      │
│ Edge +6pp                │                          │                        │
│ Signal ...               │                          │                        │
├──────────────────────────┴──────────────────────────┴────────────────────────┤
│ MARKET WATCH / RECENT MOVEMENTS / SELECTED FIXTURES                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

This is analytical market research—not sportsbook bet tiles.

### 7.5.33 Markets Mobile

Mobile:
- page-local chips:
  - Overview;
  - Value;
  - Movers;
  - Best Prices;
  - Movement.
- filters in full-screen sheet;
- source comparison becomes stacked rows;
- movement charts full-width;
- selection action bar compact;
- Betslip bottom sheet.

A 10-column odds matrix squeezed into mobile is prohibited.

### 7.5.34 Bookmaker / Source Identity Assets

Where legally/licensing permitted:
- actual bookmaker/source names;
- actual logos
may be shown.

If rights or provider contract do not allow logo use:
- text identity;
- neutral source mark
used.

Fake/generated bookmaker logos are not created.

### 7.5.35 Exchanges / Liquidity — Future-Compatible

Architecture must not assume every source is a fixed-odds bookmaker.

Future support may include:
- back/lay;
- exchange commission;
- available liquidity;
- price depth.

But exchange price cannot be forced into bookmaker semantics.

Launch support is separate product/data decision.

### 7.5.36 Market Availability vs Forecast Availability

Distinct:

```text
Forecast AVAILABLE
Market UNAVAILABLE
```

can happen.

Also:

```text
Forecast UNSUPPORTED
Market OPEN
```

can happen.

Odds existence:
**Forecast Target yaratmaz.**

Forecast existence:
**market quote varmış gibi davranmaz.**

### 7.5.37 Source Correction Handling

Provider/source quote later corrected olduğunda:
- original observation remains historical lineage;
- corrected observation/relation recorded;
- current read may choose corrected valid quote under policy.

Historical Signal:
- silently rewritten olmaz.

If correction invalidates a past evaluation, this requires explicit correction/supersession semantics—not row mutation.

### 7.5.38 Market Integrity / Conflict

If quotes conflict or source data cannot be deterministically resolved:
- do not choose the price that maximizes apparent edge;
- current comparison may become unavailable/cannot evaluate.

This protects against accidental “best looking” data selection.

### 7.5.39 Market Methodology Surface

Markets links:
- How market prices are observed;
- Odds formats;
- Market probability / margin;
- Fair Value;
- Signal methodology;
- source/consensus methodology;
- settlement rules.

Methodology pages can be technical; primary UI stays compact.

### 7.5.40 Markets Non-Goals

Markets UI:
- Forecast probability'yi odds'a göre değiştirmez;
- odds varsa unsupported Forecast uydurmaz;
- `1/odds`'u otomatik fair market probability demez;
- universal no-vig method seçmez;
- cross-book best prices'ı bookmaker distribution gibi göstermez;
- asynchronous quotes'ı sessiz coherent snapshot yapmaz;
- different lines'ı same contract gibi chart etmez;
- closing odds'u geçmiş pre-match context'e sızdırmaz;
- positive edge'i Recommendation diye etiketlemez;
- Reliability'yi probability veya EV ile çarpmaz;
- highest edge selection'ı otomatik “best bet” yapmaz;
- movement'tan “smart money” motive'i uydurmaz;
- real betting transaction gerçekleştirmez.

### 7.5.41 Canonical Market Flow

```text
Immutable Forecast
      ↓
Exact Forecast Target
      ↓
Exact Betting Contract + Settlement
      ↓
Fair Contract Value
      ↓
Point-in-Time Market Observation
      ↓
Source-specific / Best Price / Consensus Context
      ↓
Market Edge comparison
      ↓
Signal Evaluation
      ↓
Eligible Signal (if policy says ELIGIBLE)
      ↓
Recommendation (separate architecture)
```

Bu one-way flow Markets product'ının analytical sınırıdır.

## 7.6 Watchlist + Smart Alerts — FULL WORKING ARCHITECTURE

Watchlist ve Alerts, My CalibraXI'ın iki ayrı fakat bağlı personal-state sistemidir.

Temel ayrım:

```text
WATCHLIST
= kullanıcı hangi entity / analytical object / query'yi takip etmek istiyor?

ALERT RULE
= hangi future change / threshold / event olduğunda kullanıcı bilgilendirilmeli?

NOTIFICATION
= bir Alert Rule veya system event sonucunda oluşmuş immutable/delivered user event
```

Bir item'ı Watchlist'e eklemek otomatik olarak bütün alert'leri açmaz.

Bir alert oluşturmak da entity'yi zorunlu olarak Watchlist'e eklemek zorunda değildir.

### 7.6.1 Canonical Routes

```text
/my/watchlist
/my/alerts
```

Header:
- Watchlist için ayrı global icon zorunlu değildir;
- Notifications icon compact inbox açar;
- `View all` → `/my/alerts`.

Watchlist:
My CalibraXI içinde primary personal workspace destination'dır.

### 7.6.2 Watchable Object Types

Kullanıcı en az aşağıdaki object classes'ı takip edebilir:

#### Football entities
- Fixture;
- Team;
- Player;
- Competition.

#### Analytical objects
- Projection target / selection;
- exact Market Selection;
- Signal context;
- Recommendation publication;
- Power Rating / rank subject.

#### User-defined research objects
- saved Projection Explorer view;
- saved Market view;
- Strategy;
- Studio template.

Bir generic page URL'sini bookmark etmek Watchlist semantic'i değildir.

Watch object stable canonical identity'ye bağlanır.

### 7.6.3 Watchlist Object Identity

Watch item conceptually:

```text
WatchItem
- user
- object type
- canonical object identity
- createdAt
- user label/tag optional
- source surface
- status
```

User surface'teki display name değişse bile stable entity identity korunur.

Team transfer / player transfer / fixture schedule change Watch identity'yi bozmaz.

### 7.6.4 Watchlist Groups

Launch minimum:
- All;
- Matches;
- Teams;
- Players;
- Competitions;
- Projections;
- Markets;
- Strategies / Saved.

Future:
user-created collections:

```text
Premier League
Weekend
Player Props
My Teams
```

Collections user organization'dır; analytical population değildir.

### 7.6.5 Watchlist Card / Row

Entity-type'a göre relevant compact state:

Fixture:
```text
Arsenal vs Liverpool
Sat 20:00
Projection available
Lineups: Expected
```

Team:
```text
Arsenal
Power #1 ↑2
Next: vs Liverpool
```

Player:
```text
Bukayo Saka
Arsenal
Next fixture ...
Current props available
```

Projection:
```text
Arsenal-Liverpool
O2.5
Current Forecast 61%
Last reviewed ...
```

Market:
```text
Arsenal-Liverpool O2.5
Best observed 1.82
Movement ...
```

Strategy:
```text
PL O2.5 High Reliability
3 current candidates
Forward test ...
```

Watchlist presentation canonical data'yı okur; yeni Forecast üretmez.

### 7.6.6 Watchlist Quick Actions

Context-appropriate:
- Open;
- Alert;
- Remove;
- Add to Studio;
- Compare;
- Pin to My Home.

`Add to Studio` yalnız exact selectable analytical/market object varsa.

Team/Player gibi generic entity doğrudan betting leg'e dönüşmez.

### 7.6.7 Alert Trigger Families

#### Fixture Alerts
- kickoff approaching;
- date/time changed;
- venue changed if material;
- lineup expected window reached;
- confirmed lineups available;
- key availability changed;
- match became live;
- halftime/fulltime;
- postponement/cancellation;
- settlement/evaluation available.

#### Projection Alerts
- projection newly available;
- new Current Canonical Run;
- probability crossed user threshold;
- probability moved materially between valid runs;
- Reliability class changed;
- Forecast became unavailable/withheld;
- Signal became eligible/ineligible;
- Recommendation published.

#### Market Alerts
- source price threshold crossed;
- Best Observed Price threshold crossed;
- material odds movement;
- line changed;
- source spread widened/narrowed materially;
- market suspended/reopened;
- model-vs-market edge appeared/disappeared;
- Signal state changed.

#### Player Alerts
- player prop became available;
- expected/confirmed starter;
- moved to bench;
- unavailable;
- relevant prop projection changed;
- player team changed where supported.

#### Power Alerts
- team moved N ranks;
- ATT / DEF / OVR crossed user threshold;
- biggest daily/weekly mover state;
- new historical high/low if supported.

#### Strategy Alerts
- strategy found new candidate;
- candidate count changed materially;
- forward-test opportunity;
- draft prepared;
- simulation settled;
- strategy performance milestone only if user explicitly enables.

### 7.6.8 Alert Rule Structure

A user-defined alert conceptually contains:

```text
Subject
Trigger
Threshold / condition
Scope
Channel
Frequency
Cooldown
Quiet-hour behavior
Enabled state
CreatedAt
```

Example:

```text
Subject:
Arsenal vs Liverpool — O2.5

Trigger:
Best Observed Price >= 1.90

Scope:
Policy-qualified tracked sources

Channel:
In-app

Cooldown:
30m
```

Exact persistence schema Engineering'de tanımlanır.

### 7.6.9 Threshold Direction

Alert condition explicit direction kullanır:

```text
crosses above
crosses below
changes by at least X
enters state
leaves state
```

`Probability = 65%`
gibi equality-based alert floating value için tercih edilmez.

### 7.6.10 Alert Hysteresis / Deduplication

Threshold jitter notification storm yaratmamalıdır.

Example:

```text
1.89 → 1.90 → 1.89 → 1.90
```

her tick'te yeni notification üretmez.

Policy:
- hysteresis;
- debounce;
- cooldown;
- event deduplication;
- material-change threshold
kullanabilir.

Exact numbers product/engineering tuning'de belirlenir.

### 7.6.11 Alert Currentness Rule

Notification üretileceği anda trigger:
- current valid analytical artifact;
- current eligible market observation;
- relevant fixture state
üzerinde yeniden doğrulanır.

Stale state:
notification üretmez.

Historical item:
new alert gibi tekrar gönderilmez.

### 7.6.12 Notification Event

Notification oluştuğunda mümkün olduğunca immutable event context taşır:

- notification ID;
- alert rule/version;
- subject;
- trigger reason;
- event timestamp;
- relevant value before;
- value after;
- exact referenced artifact;
- deep-link target;
- delivery channel;
- read/unread;
- delivery state.

Current page daha sonra değişse bile notification:

> “19:42'de O2.5 price 1.90 threshold'unu geçti.”

gibi historical event'i açıklayabilir.

### 7.6.13 Notification Center

Header bell:
compact recent inbox.

Groups:
```text
Now
Today
Earlier
```

Each notification:
- icon/type;
- title;
- one-line reason;
- timestamp;
- unread;
- deep link.

Actions:
- Mark read;
- Mark all read;
- Snooze related alert;
- Manage rule;
- View all.

### 7.6.14 `/my/alerts`

Full Alerts Center tabs:

```text
Inbox
Rules
Muted / Snoozed
History
```

#### Inbox
Triggered notification events.

#### Rules
Active/inactive user alert definitions.

#### Muted / Snoozed
Temporarily suppressed rules/entities.

#### History
Old delivered/read events, retention policy permitting.

### 7.6.15 Alert Deep Links

Fixture lineup:
→ Match Center `#lineups`.

Projection change:
→ Match Center `#projections`.

Market movement:
→ Match Center `#markets`.

Power movement:
→ Team Page `#power` or Power Rankings.

Strategy candidate:
→ `/my/strategies/{strategyId}`.

Settlement:
→ `/my/bets/{simulationId}`.

### 7.6.16 Notification Channels

Launch recommended:
**In-app first.**

Future-compatible:
- email;
- mobile push.

Channel support:
account preference + alert-rule setting.

A future channel can be added without changing analytical event identity.

### 7.6.17 Quiet Hours

Optional user notification preference:

```text
Quiet hours
22:30 → 08:00
```

During quiet hours:
- non-critical notification delivery may be deferred/digested;
- underlying event remains recorded.

This is user delivery policy, not analytical state.

### 7.6.18 Digest

Future:

```text
Morning Digest
Evening Digest
Daily Digest
```

may aggregate non-urgent alerts.

Digest:
- does not replace individual event history;
- links to canonical pages.

Today's Brief remains a product-generated daily summary and is not identical to user alert digest.

### 7.6.19 Watch → Alert Flow

Example:

```text
Team Page
→ Follow Arsenal
→ Add to Watchlist
→ Optional:
   [Lineups]
   [Next Match]
   [Power Moves]
   [Projection Changes]
```

Do not enable 15 alert types automatically.

Recommended default:
watch silently;
user explicitly opts into meaningful alert classes.

### 7.6.20 Saved View → Alert Flow

Projection Explorer:

```text
Save View
→ PL O2.5 P>=65
→ Create Alert
→ Notify when a new current projection matches
```

Alert matches query definition.

A historical projection entering index after repair must not be falsely presented as a newly produced Forecast unless event semantics genuinely say so.

### 7.6.21 Strategy → Alert Flow

```text
Strategy v4
→ Alert when a new forward candidate appears
```

Notification includes:
- strategy/version;
- candidate;
- why rule matched;
- current eligibility;
- open in Strategy;
- open in Studio.

No automatic real bet placement.

### 7.6.22 Watchlist / Alerts Privacy

User watch state is private by default.

Future social profile:
- following a team may optionally be public;
- alerts/thresholds/strategies remain private unless explicit sharing model later permits.

Public profile design must not expose:
- bankroll;
- alerts;
- private watchlist;
- private strategies;
- simulation ledger
by default.

### 7.6.23 Watchlist / Alerts Non-Goals

Watchlist/Alerts:
- do not generate Forecast;
- do not generate Recommendation;
- do not transform historical Forecast into new current artifact;
- do not treat threshold crossing as causal insight;
- do not auto-bet;
- do not silently subscribe user to every event;
- do not spam repeated threshold jitter;
- do not expose private user research state publicly by default.

---

## 7.7 My CalibraXI — FULL PERSONAL TERMINAL ARCHITECTURE

**Canonical route:** `/my`

`/dashboard` canonical alternative değildir. Gerekirse legacy/marketing alias redirect olabilir.

My CalibraXI, logged-in kullanıcının personal operating surface'idir.

Amaç:

> Kullanıcının takip ettiği futbol context'ini, kendi research state'ini, simulations'ını, Strategy Lab'ını ve saved work'ünü tek kişisel terminalde toplamak.

Public homepage herkese:
**“Bugün CalibraXI'da ne oluyor?”**

sorusunu cevaplar.

My CalibraXI ise:
**“Benim takip ettiğim dünyada ne oluyor ve benim çalışmalarım hangi durumda?”**

sorusunu cevaplar.

### 7.7.1 Canonical My Routes

```text
/my
├── /watchlist
├── /alerts
├── /bets
├── /strategies
├── /saved
├── /performance
└── /settings
```

Potential deep routes:

```text
/my/bets/{simulationId}
/my/strategies/{strategyId}
/my/strategies/{strategyId}/backtest
/my/strategies/{strategyId}/forward
/my/saved/{savedViewId}
```

Exact nested route contract Engineering aşamasında finalize edilir.

### 7.7.2 My Local Navigation

Desktop side/local navigation:

```text
Overview
Watchlist
Alerts
Simulations
Strategies
Saved
Performance
Settings
```

User-facing label:
`Simulations`

route:
`/my/bets`

olarak kalabilir.

“Bets” ifadesinin gerçek para hesabı olduğu algısını azaltmak için UI'da **Simulations** tercih edilir.

### 7.7.3 `/my` — Overview Role

Overview'ın amacı her kişisel modülün tamamını göstermek değil, **attention queue** oluşturmaktır.

First 30 seconds:
1. bugün takip ettiğim ne var?
2. hangi alert önemli?
3. açık simulation'larım ne durumda?
4. bankroll'um ne?
5. Strategy Lab yeni candidate buldu mu?
6. hangi saved research'e dönmeliyim?

### 7.7.4 My Overview — Vertical Composition

Recommended:

```text
My Header
Personal Today / Attention
Watchlist Next Up
Open Simulations + Virtual Bankroll
Strategy Lab Snapshot
Saved Research
Recent Alerts
Recent Activity / Recently Viewed
Performance Snapshot
```

User module personalization bu default composition'ı bozabilir.

### 7.7.5 My Header

```text
MY CALIBRAXI
Your personal football analytics workspace.
```

Compact:
- current date;
- unread alerts;
- open simulations;
- optional virtual bankroll;
- quick `Open Studio`.

User name/avatar olabilir fakat giant profile hero kullanılmaz.

### 7.7.6 Attention Queue

My Overview'daki en üst dynamic module:

```text
NEEDS YOUR ATTENTION

2 lineups confirmed
1 Studio draft has a changed line
3 strategy candidates available
1 simulation settled
```

Bu bir analytical ranking değildir.

Priority:
- time sensitivity;
- user subscription;
- unread state;
- actionability
gibi product rules üzerinden olabilir.

### 7.7.7 Personalized Today / Next Up

Followed/watchlisted entity'ler içinden:
- next fixtures;
- starting soon;
- lineups;
- projections available;
- market alert;
- player prop
gibi relevant items.

Bu module public homepage fixture feed'ini kopyalamaz.

Only user context.

### 7.7.8 Virtual Bankroll — Product Boundary

Virtual bankroll:
**real money değildir.**

It is simulation accounting state.

Display:

```text
Virtual Bankroll
10,420 units

Starting
10,000

Net
+420

Open exposure
120 units
```

Currency-like symbol yerine launch'ta **units** kullanmak daha temiz olabilir.

Exact user display unit later settings'de configurable olabilir.

### 7.7.9 Bankroll Initialization

User:
- default starting amount;
- custom simulation starting balance
seçebilir.

Changing starting bankroll after history exists:
old ledger silently rewrite etmez.

Options:
- start a new simulation bankroll;
- create new ledger/season;
- explicit reset/archive.

“Reset” old performance history'yi delete etmek anlamına gelmemelidir unless user explicitly deletes their user data under product policy.

### 7.7.10 Multiple Simulation Ledgers — Future-Compatible

Launch:
one primary virtual bankroll sufficient olabilir.

Architecture future:
- Main;
- Strategy Test;
- Conservative;
- Experimental
gibi separate simulation ledgers desteklemeyi engellememelidir.

A ledger:
- own starting balance;
- placements;
- settlements;
- performance.

User cannot merge two ledgers and pretend one historical strategy.

### 7.7.11 Simulation Bet Domain

Placed Simulation Bet:
immutable placement snapshot.

At minimum:
- simulation ID;
- user;
- ledger;
- created/placed time;
- exact selections;
- exact contracts;
- odds snapshots;
- source/price basis;
- combined odds;
- stake;
- potential return;
- Forecast refs;
- Signal refs;
- Recommendation refs;
- Studio composition ref;
- Strategy/version ref;
- bankroll before;
- settlement state;
- realized return;
- bankroll after;
- settlement policy.

This extends the earlier virtual betslip requirement without changing its core semantics.

### 7.7.12 `/my/bets` — Simulations

UI label:
**Simulations**

Tabs:

```text
Open
Settled
All
```

Filters:
- date;
- single / combination;
- Studio mode;
- strategy;
- competition;
- market;
- source type;
- settlement.

### 7.7.13 Simulation Card

Open:

```text
SIMULATION
3-leg Cross-Match

Placed 19:42
Stake 1.0u
Combined 4.82
Potential +3.82u

2 upcoming
1 live

[Open]
```

Settled:

```text
SETTLED
3-leg Cross-Match

Result: LOSS
Stake 1.0u
Return 0u
P/L -1.0u

[View exact placement]
```

No celebratory casino animation.

### 7.7.14 Simulation Detail

`/my/bets/{simulationId}`

Shows immutable placement:

- placed timestamp;
- exact leg snapshots;
- exact prices;
- current price may be shown separately but never replace placement price;
- source class;
- strategy tag/version;
- Recommendation lineage if any;
- settlement per leg;
- return calculation;
- bankroll before/after;
- event timeline.

Link:
- Match Center historical;
- Studio composition;
- Strategy version.

### 7.7.15 Open Simulation Current Context

Placed bet's historical truth frozen.

But UI may show separate:

```text
PLACED
O2.5 @1.82

CURRENT MARKET
1.70
```

or:
```text
Current projection updated
```

These are context only.

They do not mutate placement.

### 7.7.16 Cashout — OUT OF SCOPE

Virtual cashout is not assumed.

If future simulation supports cashout:
- requires explicit market/source semantics;
- new ledger event;
- separate evaluation behavior.

Launch:
no fabricated cashout value.

### 7.7.17 Favorite Markets

User can favorite:
- 1X2;
- totals;
- BTTS;
- player SOT;
- etc.

Purpose:
- order/filter My surfaces;
- quick access.

Favorite market:
- does not influence Forecast;
- does not influence Recommendation;
- does not create model personalization.

### 7.7.18 Saved Research — `/my/saved`

Unifies user-saved research definitions:

```text
Projection Views
Market Views
Studio Drafts/Templates
Comparisons
Collections
```

Strategy definitions remain `/my/strategies`, not generic Saved.

### 7.7.19 Saved Projection View

Example:

```text
Premier League O2.5
Next 12H
P >=65%
Reliability High
Odds 1.50–2.20
```

Shows:
- saved filter definition;
- current match count;
- last opened;
- alert status.

Open:
→ Projection Explorer with URL/query state.

### 7.7.20 Saved Market View

Example:

```text
Top 5 Leagues — O2.5 Movers
Next 6H
Move >= 8%
```

Open:
→ Markets with exact filters.

### 7.7.21 Saved Studio Draft

Saved composition lives in Studio domain but surfaced here.

Status examples:
- Current;
- Updates available;
- Market closed;
- Fixture completed;
- Needs review.

Open:
→ `/studio` draft context.

### 7.7.22 Recently Viewed

Optional convenience module:
- Match Centers;
- Team Pages;
- Player Pages;
- Competition Pages;
- Explorer views.

Recently Viewed:
navigation aid'dir;
Watchlist değildir.

Retention/privacy settings can control it later.

### 7.7.23 Strategy Lab — Canonical Location

Canonical route:

```text
/my/strategies
```

Strategy Lab is user-owned hypothesis testing workspace.

Strategy:
- Recommendation değildir;
- production model değildir;
- auto-betting system değildir.

### 7.7.24 Strategy List

Each Strategy card:

```text
PL O2.5 High Reliability
Version 4

Status: Forward testing
Backtest N: ...
Forward opportunities: ...
Executed simulations: ...
Forward ROI: ...
Last candidate: ...

[Open] [Candidates] [Pause]
```

Backtest and forward metrics visually separate.

### 7.7.25 Strategy States

Working product states:

```text
Draft
Backtest ready
Backtesting
Backtest complete
Forward testing
Paused
Archived
```

Failure:
- data insufficient;
- unsupported condition;
- no PIT coverage
may be explicit.

Strategy state is not analytical quality grade.

### 7.7.26 Strategy Builder — Condition Groups

Rule builder should be human-readable, not raw SQL.

Example:

```text
ALL of:
  Competition is Premier League
  Forecast Probability >= 65%
  Reliability is High
  Odds between 1.50 and 2.20
  Market is Over 2.5

AND:
  Signal is Eligible
```

Future:
nested ANY/ALL groups may be supported.

But arbitrary unconstrained scripting launch requirement değildir.

### 7.7.27 Strategy Condition Classes

Possible:

#### Forecast
- probability;
- family;
- target;
- availability.

#### Reliability
- band/class.

#### Market
- odds;
- price source/basis;
- edge;
- line.

#### Entity
- competition;
- team;
- player;
- home/away.

#### Power / Form
- OVR difference;
- form-state metric
only if exact historical PIT version exists.

#### Signal / Recommendation
- Signal decision;
- Recommendation availability.

#### Time
- horizon;
- kickoff window;
- day of week
if meaningful.

#### Composition
- single;
- Cross-Match;
- Same-Match.

### 7.7.28 Strategy PIT Validity

A rule can only backtest a condition if historical PIT semantics exist.

Example:

```text
Current Power Rank <= 5
```

cannot be backtested by applying today's rank backward.

Need historical Power snapshot.

Likewise:
- current injury;
- current Reliability;
- current odds;
- current lineup
must have historical eligible evidence.

If not:
condition is:
`Not backtestable for requested period`
or coverage limited.

### 7.7.29 Historical Backtest View

Backtest report includes:

- requested date range;
- PIT eligibility;
- opportunity count;
- executed simulation rule;
- settled;
- hit rate;
- avg odds;
- unit ROI/yield;
- P/L;
- max drawdown;
- probability buckets;
- odds buckets;
- league/market;
- sample;
- uncertainty;
- exclusions;
- PIT coverage.

This is user strategy research, not CalibraXI public Track Record.

### 7.7.30 Backtest Opportunity vs Execution

Separate:

```text
Opportunities
= rule matched

Executed simulations
= stake/execution rule says simulation placed
```

If user changes execution/stake rule:
new strategy version.

Do not silently recalculate old forward history.

### 7.7.31 Forward Test View

After strategy activation:
new real-time candidates.

Shows:
- opportunities;
- user reviewed;
- placed simulation;
- skipped;
- settled;
- open;
- performance.

Backtest results remain separate.

### 7.7.32 Backtest vs Forward Comparison

Side-by-side:

```text
                 BACKTEST    FORWARD
Opportunities       ...        ...
N                   ...        ...
Avg odds            ...        ...
Hit rate            ...        ...
Unit ROI            ...        ...
Drawdown            ...        ...
```

Gap:
descriptive.

Do not claim overfitting causally from one gap without analysis.

### 7.7.33 Strategy Versioning UX

Editing active strategy:

```text
This strategy has historical results.
Saving these changes will create Version 5.
Version 4 results remain unchanged.
```

User can:
- duplicate;
- create new version;
- archive old.

Strategy name may remain same, version distinct.

### 7.7.34 Strategy Candidate Inbox

Strategy detail:

```text
CANDIDATES
3 new
```

Candidate card:
- fixture;
- selection;
- rule-match reasons;
- Forecast;
- Reliability;
- market price;
- Signal state;
- time;
- `Open Match`;
- `Open in Studio`;
- `Skip`.

Candidate is not Recommendation.

### 7.7.35 Candidate Expiry

Candidate may expire because:
- kickoff passed;
- market closed;
- line changed;
- Forecast superseded;
- rule no longer matches.

Historical candidate event remains queryable if retention permits.

Current inbox removes/marks expired.

### 7.7.36 Strategy Automation Boundary

Allowed future automation:

```text
New candidate
→ notify
→ optionally create Studio draft
→ user reviews
→ user sends to Betslip
→ user explicitly places simulation
```

No:
- automatic real bookmaker bet;
- hidden placement;
- strategy silently converting to Recommendation.

Future auto-paper placement could be a separate explicit user opt-in feature, but not launch default.

### 7.7.37 `/my/performance`

Personal performance uses user's Simulation Ledger.

Views:

```text
Overview
Singles
Studio
Strategies
Markets
Competitions
```

Potential metrics:
- current virtual bankroll;
- starting bankroll;
- total P/L;
- ROI;
- yield;
- settled simulations;
- hit rate;
- avg odds;
- avg stake;
- max drawdown;
- best/worst period;
- strategy breakdown;
- market breakdown;
- league breakdown;
- builder vs single;
- bankroll/equity curve.

### 7.7.38 Personal Performance Is Not Public Track Record

User selected:
- different stake sizes;
- manual selections;
- skipped candidates;
- mixed strategies
can materially affect performance.

Therefore personal performance cannot be used as:

`CalibraXI Track Record`.

Public `/track-record` and `/my/performance` may share charts/components but not population authority.

### 7.7.39 Stake-Weighted vs Unit-Stake Personal Views

Personal performance can show:

#### Actual Simulation Ledger
User-entered virtual stakes.

#### Normalized Unit-Stake
Optional comparison view.

These are separate.

A large user stake must not alter analytical Signal/Forecast truth.

### 7.7.40 Personal Performance Filters

- date;
- ledger;
- strategy/version;
- single/combo;
- Studio mode;
- market;
- competition;
- odds bucket;
- source type.

Outcome-conditioned cherry-picking may be allowed only as exploratory transaction history, but headline performance should make active filters clear.

### 7.7.41 My Overview Performance Snapshot

Compact:

```text
MY SIMULATION
Bankroll 10,420u
30D P/L +84u
30D ROI ...
Open 4
Settled 62

[Performance]
```

It must say:
**Simulation**

to avoid real-money account impression.

### 7.7.42 Personal Activity Feed

Optional:

```text
You followed Arsenal
Strategy v4 found a candidate
You placed a 3-leg simulation
Saka prop alert triggered
Simulation settled
```

Activity feed:
user-event history.

It does not replace notifications.

### 7.7.43 Module Personalization

User can:
- pin;
- hide;
- reorder
eligible My Overview modules.

Core safety/status modules cannot be permanently hidden when required.

Potential configurable modules:
- Watchlist Next Up;
- Strategies;
- Open Simulations;
- Saved Research;
- Alerts;
- Recent;
- Performance.

### 7.7.44 Layout Persistence

Personal layout:
account-scoped when logged in.

Device-specific compactness/preferences may be local.

If sync conflict:
server/account layout may be authoritative under Engineering policy.

Layout state analytical data değildir.

### 7.7.45 My CalibraXI First Viewport

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ MY CALIBRAXI                                              Open Studio →     │
│ Your personal football analytics workspace                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ NEEDS YOUR ATTENTION                                                         │
│ 2 lineups confirmed · 3 strategy candidates · 1 draft changed              │
├────────────────────────────────────────────┬─────────────────────────────────┤
│ WATCHLIST — NEXT UP                        │ SIMULATION                      │
│                                            │                                 │
│ Arsenal vs Liverpool · 20:00              │ Bankroll 10,420u               │
│ Saka prop available                        │ Open 4                          │
│ Galatasaray lineup confirmed              │ 30D P/L +84u                   │
│                                            │                                 │
│ View watchlist →                           │ View simulations →             │
├────────────────────────────────────────────┼─────────────────────────────────┤
│ STRATEGY LAB                               │ RECENT ALERTS                   │
│                                            │                                 │
│ PL O2.5 v4 · 3 candidates                 │ Price threshold ...            │
│ Player SOT v2 · Forward test              │ Lineups confirmed ...          │
│                                            │                                 │
│ View strategies →                         │ View all →                     │
└────────────────────────────────────────────┴─────────────────────────────────┘
```

Below:
- Saved Research;
- Recently Viewed;
- Performance Snapshot.

### 7.7.46 Mobile My CalibraXI

Mobile bottom nav:
`My`

opens `/my`.

Top:
- compact header;
- unread notification count;
- bankroll compact state.

Modules stacked.

Secondary My navigation can use:
- horizontal chips;
- menu/sheet.

Recommended frequent actions:
- Watchlist;
- Simulations;
- Strategies;
- Alerts.

### 7.7.47 My Search

Personal workspace search can filter:
- saved views;
- simulations;
- strategies;
- watchlist.

Global football Search remains separate.

Query:
`Arsenal`
inside My can surface:
- watched Arsenal;
- Arsenal simulation history;
- Arsenal-related strategies/saved views.

### 7.7.48 Onboarding — First Login

New account empty terminal should not look broken.

Working onboarding:

```text
1. Follow competitions/teams/players
2. Choose favorite market families optional
3. Set virtual bankroll
4. Save first view / create first alert
```

All optional except necessary account setup.

Do not force strategy creation.

### 7.7.49 Empty States

Watchlist:
`Follow a match, team, player or competition to build your workspace.`

Alerts:
`Create an alert from a Match, Projection, Market or Strategy.`

Simulations:
`Use the virtual Betslip to place your first simulation.`

Strategies:
`Create a rule-based strategy or start from a template.`

Saved:
`Save Projection or Market views to return to them quickly.`

### 7.7.50 Settings — `/my/settings`

Personal settings groups:

```text
Account
Display
Notifications
Simulation
Privacy
Connected delivery channels future
```

Not all account management must live in product UI if auth provider owns it.

### 7.7.51 Notification Settings

- in-app;
- email future;
- push future;
- quiet hours;
- digest;
- default alert frequency;
- muted entities/rules.

Global notification preference cannot convert disabled analytical outputs into alerts.

### 7.7.52 Simulation Settings

Potential:
- odds display format;
- default virtual stake;
- confirmation before placement;
- primary ledger;
- starting bankroll for new ledger.

Do not expose “real bookmaker bankroll sync” unless separately designed in future.

### 7.7.53 Privacy Settings

Launch/private default.

Future-ready controls might include:

```text
Profile visibility
Followed teams visibility
Shared collections visibility
Selected strategy summary visibility
Selected simulation summary visibility
```

But:
- exact alerts;
- exact private strategy rules;
- bankroll;
- full bet ledger
private by default.

### 7.7.54 Future Public Profile

Future route could be:

```text
/u/{handle}
```

Potential public content:
- avatar/name;
- favorite teams/leagues;
- shared saved views;
- shared collections;
- selected strategy summaries;
- intentionally shared simulation Track Record.

This is future direction only.

It is not current implementation requirement.

### 7.7.55 Future Social Graph

Future:
- follow users;
- shared analysis collections;
- public strategy templates;
- public saved screens.

No future social feature should change canonical Forecast/Signal/Recommendation truth.

Popularity:
- likes;
- follows;
- saves
must not become analytical ranking evidence.

### 7.7.56 Sharing a Personal Object

Future user may explicitly share:
- saved Explorer view;
- Studio template;
- strategy definition;
- performance snapshot.

Share artifact should declare:
- what is shared;
- version;
- visibility;
- date/as-of;
- whether performance is Backtest or Forward.

Private source data not included automatically.

### 7.7.57 My CalibraXI Data Ownership Boundary

User-owned:
- Watchlist;
- alerts;
- saved views;
- strategies;
- Studio drafts;
- virtual ledger;
- module layout;
- notification preferences.

Canonical product-owned:
- Fixtures;
- Forecasts;
- Signals;
- Recommendations;
- Market Observations;
- Outcomes;
- Track Record.

User actions reference canonical artifacts but do not mutate them.

### 7.7.58 Deleting / Archiving User Objects

Strategy:
archive preferred over delete if history exists.

Saved view:
can delete.

Alert:
disable/delete under user-data policy.

Simulation:
historical ledger integrity suggests archive/hide rather than mutate settlement.

Exact privacy/deletion obligations Engineering/legal implementation determines.

### 7.7.59 Account Without Premium

My CalibraXI architecture should support entitlement gating without breaking identity.

Example:
user may see:
- followed fixture;
- saved query definition;
but some premium analytical fields locked.

Gating:
does not alter canonical Forecast availability.

`Premium locked`
≠ `Forecast unavailable`.

### 7.7.60 My CalibraXI and Today's Brief

Today's Brief:
public/product-generated daily overview.

My Overview:
personal attention surface.

Logged-in future:
Today's Brief may include followed entities.

But it does not become identical to My.

Header Brief remains independently reopenable.

### 7.7.61 My CalibraXI and Studio

Studio:
composition workspace.

My:
saved/personal state.

Flows:

```text
My Strategy
→ Studio draft
→ Betslip
→ Simulation
→ My Performance
```

```text
My Saved Draft
→ Studio
→ revalidate
→ Betslip
```

```text
My Watchlist
→ Match Center
→ selection
→ Studio
```

### 7.7.62 My CalibraXI and Track Record

Public Track Record:
product accountability.

My Performance:
user simulation.

Cross-links allowed:

```text
Simulation created from Published Recommendation
→ View Recommendation public Track Record artifact
```

But user's result doesn't alter public Recommendation evaluation.

### 7.7.63 My CalibraXI and Match Center

Watchlisted fixture:
Match Center.

Alert:
deep section.

Simulation leg:
Match Center historical/current.

Recently viewed:
Match Center.

No duplicate match detail inside My.

### 7.7.64 My CalibraXI and Projection Explorer

Saved query:
Explorer.

Alert:
new matching projection.

Candidate:
Studio.

My does not duplicate Explorer filtering engine.

### 7.7.65 My CalibraXI and Markets

Watched market:
Markets/Match Center.

Threshold alert:
Markets.

Saved market screen:
Markets.

My does not keep its own odds truth.

### 7.7.66 Personalization Does Not Alter Analytical Truth

User preferences may change:
- ordering;
- visibility;
- notifications;
- favorite markets;
- followed entities.

They do **not** change:
- Forecast probability;
- Reliability;
- Signal eligibility;
- Recommendation;
- Power Rating;
- Track Record.

A future personalized Recommendation architecture, if ever considered, requires a separate explicit decision. It is not implied by My CalibraXI.

### 7.7.67 Personalization Ranking

My Overview ordering can be personalized based on:
- followed status;
- time-to-kickoff;
- unread alert;
- recent activity;
- pinned modules.

This ranking is product attention ordering.

It is not:
- Recommendation ranking;
- betting quality ranking;
- model confidence ranking.

### 7.7.68 Security-Sensitive Actions

At minimum:
- session/account protection;
- notification destination changes;
- profile visibility changes;
- data export/delete
may require appropriate re-auth/confirmation.

Exact auth/security architecture belongs to Engineering.

### 7.7.69 Auditability for User Simulations

User should be able to inspect why historical simulation balance changed.

Ledger event examples:
- placement -1.0u;
- settlement +1.82u;
- void refund +1.0u;
- correction adjustment if policy supports.

Bankroll should be reconstructable from ledger events rather than arbitrary mutable total only.

### 7.7.70 Settlement Correction in User Ledger

If authoritative settlement changes:
- placed Simulation remains unchanged;
- earlier settlement ledger event remains historical;
- correction creates adjustment/new settlement event under explicit semantics.

User sees:
`Settlement corrected`

rather than old history silently changing.

### 7.7.71 Strategy/Simulation Provenance

Personal performance drill-down can answer:

```text
Which Strategy version produced this?
Which candidate matched?
Which Studio revision was used?
Which Forecast/Signal/Recommendation existed?
Which odds were frozen at placement?
```

This allows genuine user research.

### 7.7.72 My Performance Avoids False Scientific Claims

Personal sample:
self-selected.

Therefore:
- user ROI;
- win rate;
- best strategy
are personal descriptive results.

They are not automatically generalizable strategy validation.

Backtest/Forward labels and N remain visible.

### 7.7.73 Personal Best / Worst

If shown:
- best day;
- worst day;
- biggest win/loss
are secondary descriptive stats.

They should not dominate the page or gamify losses/wins.

### 7.7.74 Responsible Simulation Presentation

Because virtual bankroll is educational/research simulation:
- no deposit wording;
- no withdraw;
- no “cash balance”;
- no confetti;
- no urgent “bet now” language;
- no false real-money framing.

Use:
`Simulation`
`Virtual Bankroll`
`Units`
`Place Simulation`

### 7.7.75 My CalibraXI Visual Direction

Light-first.

More workspace-like than public homepage.

Visual rhythm:
- attention strip;
- compact modules;
- ledger tables;
- strategy analytics;
- saved research;
- controlled dense data.

Avoid:
- generic social profile dashboard;
- financial brokerage imitation;
- casino wallet styling.

### 7.7.76 My CalibraXI Non-Goals

My CalibraXI:
- does not create new analytical truth;
- does not personalize Forecast probability;
- does not turn followed items into Recommendations;
- does not mix personal ROI with public Track Record;
- does not auto-bet;
- does not rewrite saved historical odds;
- does not silently change Strategy versions;
- does not backfill current data into historical backtests;
- does not make private strategies/alerts public by default;
- does not make favorite markets model inputs;
- does not duplicate Match Center/Explorer/Markets/Studio engines.

### 7.7.77 Canonical Personal Workflow

```text
FOLLOW / WATCH
      ↓
MY OVERVIEW
      ↓
ALERT / SAVED RESEARCH
      ↓
MATCH / PROJECTION / MARKET
      ↓
STUDIO
      ↓
VIRTUAL BETSLIP
      ↓
PLACE SIMULATION
      ↓
MY SIMULATIONS
      ↓
MY PERFORMANCE
```

Strategy:

```text
CREATE STRATEGY
      ↓
PIT BACKTEST
      ↓
VERSION
      ↓
FORWARD TEST
      ↓
CANDIDATE ALERT
      ↓
STUDIO
      ↓
SIMULATION
      ↓
STRATEGY PERFORMANCE
```

### 7.7.78 Working Decision

**My CalibraXI = personal terminal, not account settings page.**

Canonical split:

```text
/my
= attention / personal overview

/my/watchlist
= followed entities / research objects

/my/alerts
= notification inbox + alert rules

/my/bets
= virtual simulation ledger

/my/strategies
= Strategy Lab

/my/saved
= saved research / drafts / templates

/my/performance
= personal simulation performance

/my/settings
= personal product/settings/privacy
```

Future social/profile architecture may extend this domain, but launch personal data remains private-by-default.

## 7.8 Power Rankings History

Power Ranking yalnızca bugünkü sıralama değildir.

Her team için:
- current rank;
- previous rank;
- Δ rank;
- ATT history;
- DEF history;
- OVR history;
- rolling chart;
- highest/lowest rank;
- selected time range.

League sayfasında weekly snapshots, biggest risers/fallers ve rating-change leaderboard bulunabilir.

Rating history geçmiş snapshot'ları bugünkü rating hesabıyla sessizce rewrite etmez.

## 7.9 Daily Analytics Brief — İlk Saat Deneyimi

Kullanıcı gün içinde CalibraXI'ı ilk kez açtığında kısa bir **Today's Brief** görür.

Örnek içerik:
- bugün izlenen fixture sayısı;
- projection coverage;
- önemli Power Ranking hareketleri;
- dikkat çekici matchup/form durumları;
- önemli market movements;
- available high-quality Signals/Recommendations;
- günün önemli player/team statistical leaders;
- live/upcoming schedule highlights.

### Görünürlük mantığı
- günün ilk ziyareti tespit edilir;
- `firstSeenAt` kaydedilir;
- brief yaklaşık **60 dakika boyunca** ana sayfada görünür olabilir;
- 60 dakika sonrasında ana dashboard'dan otomatik olarak çekilir/collapse olur;
- kullanıcı daha erken `Dismiss` edebilir;
- sonrasında header/menu içindeki **Today's Brief** entry'sinden manuel açılabilir;
- ertesi calendar day yeni brief lifecycle başlar;
- login olmayan kullanıcıda device/local-state, login olan kullanıcıda account-aware state uygulanabilir.

Böylece brief kalıcı hero'ya dönüşmez ve gün boyunca dashboard alanını işgal etmez.

## 7.10 Compare Mode

Entity-type bazında compare desteklenir:
- Fixture vs Fixture;
- Team vs Team;
- Player vs Player;
- Projection vs Projection.

Farklı semantic entity türleri tek anlamsız tabloya zorla karıştırılmaz.

Fixture compare probability, Reliability, odds, edge, power difference, form ve relevant context gösterebilir. Team compare ATT/DEF/OVR, form, process stats, home/away ve trajectory; Player compare minutes, per-90, shots/SOT, goals/assists, supported xG/xA ve props gösterebilir.

Compare sonucu bir “winner” üretmek zorunda değildir; aynı ölçümleri yan yana sunar.

## 7.11 Historical Snapshot — “CalibraXI O Anda Ne Biliyordu?”

Historical fixture görünümünde kullanıcı yalnızca bugünkü güncellenmiş datayı görmez.

Historical Snapshot mode:
- exact Prediction Run;
- Forecast Cutoff;
- eligible Evidence Manifest;
- Feature Snapshot identity;
- o anda bilinen lineup/availability state;
- publication state;
- Forecast probability;
- Reliability evidence;
- o andaki odds snapshot;
- varsa exact historical Signal/Recommendation;
- subsequent outcome/evaluation
sunabilir.

Kullanıcı gerektiğinde farklı pre-match snapshots/run'lar arasında geçebilir.

Amaç “CalibraXI maçtan önce ne biliyordu?” sorusuna gerçek cevap vermek ve hindsight rewrite'ı engellemektir.

## 7.12 Deferred — Data Coverage / Freshness Badge

Data Coverage/Freshness için prominent kullanıcı-facing özel badge sistemi bu turda **istenmedi ve mevcut ürün requirement'ına eklenmedi**.

Kaynak/tazelik/availability mimarisi backend ve analitik doğruluk için korunur; ayrı UI özelliği gelecekte yeniden açılabilir.

---

# 8. Global Information Architecture & Navigation

Bu bölüm CalibraXI'ın ürün yüzeylerinin birbirine nasıl bağlanacağını ve kullanıcının site içinde kaybolmadan nasıl hareket edeceğini tanımlar.

Temel prensip:

> **Top navigation az sayıda güçlü ürün alanı gösterir; entity page'ler, kişisel araçlar ve özel araştırma yüzeyleri gerektiğinde derinleşir.**

CalibraXI çok sayıda feature'a sahip olsa da header bunların tamamını yan yana dizmez.

## 8.1 Primary Desktop Navigation — LOCKED WORKING IA

Desktop ana navigasyon önerisi:

| Sıra | Navigation | Canonical route | Ana soru |
|---:|---|---|---|
| 1 | **Matches** | `/matches` | Bugün / seçtiğim dönemde hangi maçlar var? |
| 2 | **Projections** | `/projections` | CalibraXI ne öngörüyor? |
| 3 | **Stats** | `/stats` | Veriler, sıralamalar ve trendler ne söylüyor? |
| 4 | **Markets** | `/markets` | Piyasa ne fiyatlıyor ve nasıl hareket ediyor? |
| 5 | **Studio** | `/studio` | Seçimleri nasıl bir araya getirip test ederim? |
| 6 | **Track Record** | `/track-record` | CalibraXI geçmişte nasıl performans gösterdi? |

**Home için ayrı `Home` navigation item'ı kullanılmaz.** CalibraXI logosu `/` ana dashboard'a döner. Bu, primary navigation'ı gereksiz yere kalabalıklaştırmaz.

### Neden bu sıra?

Bu navigation kullanıcı zihnindeki doğal araştırma akışını takip eder:

```text
MATCHES
  → hangi maçlar var?

PROJECTIONS
  → model ne bekliyor?

STATS
  → bunu destekleyen veri ne?

MARKETS
  → piyasa bunu nasıl fiyatlıyor?

STUDIO
  → ben neyi birleştirmek / simüle etmek istiyorum?

TRACK RECORD
  → bu sistem geçmişte gerçekten nasıl çalıştı?
```

Bu sıralama sadece görsel değildir; ürünün kavramsal ayrımlarını da korur.

## 8.2 Header Utility Layer

Primary navigation'ın sağ tarafında ürün destinasyonları yerine **utility actions** bulunur:

- **Global Search / Command Search**
- **Today's Brief**
- **Notifications**
- **My CalibraXI / user avatar**
- **Betslip toggle + selection count**

Örnek desktop shell:

```text
CALIBRA XI
Matches | Projections | Stats | Markets | Studio | Track Record

                                      Search
                                      Brief
                                      Notifications
                                      My CalibraXI
                                      Betslip (3)
```

Betslip bir navigation destination değildir. Sağ panel/drawer olarak açılır.

Today's Brief de standalone top-level product alanı değildir; günün context utility'sidir.

## 8.3 Global Live Tracker Placement

Collapsible Live Match Tracker:

```text
Primary Header
↓
Live Match Tracker
↓
Page-specific toolbar / filters
↓
Page content
```

şeklinde header'ın altında yer alır.

Tracker ana ürün shell'inin parçasıdır ve aşağıdaki ana yüzeylerde gösterilebilir:

- Home;
- Matches;
- Projections;
- Stats;
- Markets;
- Studio;
- Track Record;
- Match Center;
- League/Competition;
- Team;
- Player.

Aşağıdaki utility/legal yüzeylerde zorunlu değildir:

- login/register;
- account settings;
- pricing;
- methodology;
- legal/responsible-use.

Kullanıcının collapse tercihi yüzeyler arasında korunabilir.

## 8.4 `/matches` — Fixture Discovery Hub

`/matches` bütün fixture discovery akışının ana girişidir.

Bu sayfa:
- Today;
- Tomorrow;
- This Weekend;
- Next 7 Days;
- Custom Date Span;
- Next 3 / 6 / 12 Hours
scope'larını kullanır.

Filtreler:
- competition;
- country;
- kickoff;
- match state;
- projection availability;
- watched/followed entities
gibi boyutlarla genişleyebilir.

Bir fixture row/card'ın primary action'ı ilgili **Match Center / H2H** sayfasına gider.

```text
/matches
  → /h2h/{home-vs-away}/{fixtureId}
```

Live fixture'a tıklamak aynı stable Match Center identity'sini açar; ayrı bir unrelated live page oluşturulmaz.

## 8.5 `/projections` — Model Output Hub

Projections navigation doğrudan mevcut canonical hub'a bağlanır.

Dropdown / secondary navigation:

```text
Projections Overview
Fixture Projections
Form Edges
Player Props
Team Outrights
Top 10
Projection Explorer
```

Routes:

```text
/projections
/projections/fixtures
/projections/form-edges
/projections/player-props
/projections/team-outrights
/projections/top-10
```

Projection Explorer `/projections` içinde güçlü bir explorer mode olarak başlayabilir. Kullanım büyürse `/projections/explore` route'u ayrılabilir.

### Individual projection click behavior

Fixture projection:
```text
Projection card
  → Match Center
  → Projections section
```

Player prop:
```text
Prop card
  → Match Center / Player Props section

Player name/avatar
  → Player Page
```

Team outright:
```text
Projection
  → relevant Competition Page or Team Page
```

`View All` her zaman ilgili projection family listing'ine gider; individual item click ise ilgili entity/context page'e gider.

## 8.6 `/stats` — Statistical Discovery Hub

Stats top-level navigation altında data-first yüzeyler birleşir.

Recommended secondary structure:

```text
/stats
/stats/power-rankings
/stats/teams
/stats/players
/stats/streaks
```

### Stats Overview

`/stats` içinde:
- Power Rankings;
- Player leaders;
- Team leaders;
- Streaks;
- Over/Under trends;
- BTTS trends;
- biggest movers
gibi özet modüller bulunur.

### Entity directories

Aşağıdaki directory'ler Stats üzerinden keşfedilebilir ancak kendi canonical entity route'larını korur:

```text
/competitions
/teams
/players
```

Entity detail:

```text
/competition/{slug}
/team/{slug}
/player/{slug}
```

### Canonical competition route decision

UI kullanıcıya “League” veya “League & Cup” diyebilir; domain ve canonical URL açısından tek ortak route ailesi tercih edilir:

```text
/competition/{slug}
```

Böylece league, cup, tournament ve knockout competition için ayrı ayrı route sistemleri yaratılmaz.

Eski working `/league/{slug}` route'u canonical olmak zorunda değildir; gerektiğinde redirect/alias olarak desteklenebilir.

## 8.7 `/markets` — Market Analytics Hub

Markets primary navigation destination'ı **price-first market research** alanıdır.

Canonical routes:

```text
/markets
/markets/value
/markets/odds-movement
/markets/best-prices
/markets/movers
```

Division:

```text
/markets
= overview / Market Pulse

/markets/value
= Forecast-first compatibility sağlandıktan sonra model-vs-market / Fair Value / Signal context

/markets/odds-movement
= exact contract price history

/markets/best-prices
= source comparison / best observed exact selection price

/markets/movers
= material price or line movement discovery
```

Source-specific market estimate, Best Observed Price ve Consensus birbirinden farklı comparison identities'dir.

Markets:
- Forecast üretmez;
- Recommendation üretmez;
- Studio'yu duplicate etmez;
- Match Center'daki fixture-specific Markets section'a deep-link eder.

Full product/semantic architecture için `7.5 Markets / Odds / Value` bölümü canonical working specification'dır.

## 8.8 `/studio` — Tek Combination / Builder Destination

Studio primary navigation'da kendi alanıdır.

Canonical local IA:

```text
/studio

DAILY
  ├── Cross-Match
  └── Same-Match

BUILD
  └── Manual Composition

SAVED
  ├── Drafts
  ├── Templates
  └── Strategy-assisted material
```

Site içindeki builder actions:
- Match Center;
- Projections;
- Markets;
- Strategy Lab
üzerinden Studio'ya context taşır.

Studio:
- same-match dependency'yi validate eder;
- cross-match combination support'u gösterir;
- price basis'i açıklar;
- unsupported combined probability uydurmaz;
- virtual Betslip'e handoff yapar.

Stake ve simulation placement Studio'nun değil Betslip'in authority'sidir.

Full Studio product specification için Section `4.5 CalibraXI Studio — FULL WORKING ARCHITECTURE` canonical working source'tur.

## 8.9 `/track-record` — Public Proof Layer

Track Record primary navigation'da görünür kalır.

Canonical routes:

```text
/track-record
/track-record/forecasts
/track-record/signals
/track-record/recommendations
/track-record/studio
```

Semantic division:

```text
Forecasts
= probability quality + calibration + coverage

Signals
= Signal Decision / settlement / price-basis performance

Recommendations
= genuine publication-qualified Recommendation performance

Studio
= genuine Published Studio Composition performance
```

Public Track Record:
- named/versioned populations;
- explicit sample/denominator;
- point-in-time price/outcome semantics;
- uncertainty/dependency treatment;
- artifact drill-down;
- report version/as-of
kullanır.

User simulation results ayrı kalır:

```text
/my/performance
```

Full working product specification Section `5. Track Record — FULL WORKING PRODUCT ARCHITECTURE` içindedir.

## 8.10 My CalibraXI Information Architecture

My CalibraXI header'ın sağındaki account/workspace entry'sinden açılır.

**Canonical route: `/my`**

Primary site navigation'a yedinci item olarak eklenmez.

Canonical routes:

```text
/my
/my/watchlist
/my/alerts
/my/bets
/my/strategies
/my/saved
/my/performance
/my/settings
```

Recommended local labels:

```text
Overview
Watchlist
Alerts
Simulations
Strategies
Saved
Performance
Settings
```

Role division:

```text
/my
= personal attention queue / overview

/my/watchlist
= followed canonical entities and user research objects

/my/alerts
= notifications + rule management

/my/bets
= immutable virtual simulation ledger

/my/strategies
= Strategy Lab / PIT backtest / forward test

/my/saved
= saved Explorer/Market views + Studio drafts/templates

/my/performance
= user's own simulation analytics

/my/settings
= notification/simulation/privacy preferences
```

Public analytical engines are not duplicated inside My.

## 8.11 Watchlist & Alerts Placement

Watchlist and Alerts are connected but separate:

```text
Watch
≠ Alert
≠ Notification
```

Typical flows:

```text
Team Page
→ Watch
→ /my/watchlist
→ optional alert types
```

```text
Projection Explorer
→ Save View
→ Alert when new current result matches
→ /my/alerts
```

```text
Markets
→ Watch exact selection
→ price threshold alert
→ Notification
→ Match Center #markets
```

```text
Strategy
→ candidate alert
→ Notification
→ /my/strategies/{id}
→ Studio
```

Header notification icon:
- compact inbox;
- unread count;
- deep-link to event;
- `View all` → `/my/alerts`.

Launch preferred delivery:
**in-app**.

Email/mobile push remain future-compatible channels.

## 8.12 Compare Mode Placement

Compare Mode top-level navigation değildir.

Entity sayfalarında contextual action:

```text
Compare
```

olarak bulunur.

Shareable route:

```text
/compare?type=team&a=...&b=...
/compare?type=fixture&a=...&b=...
/compare?type=player&a=...&b=...
/compare?type=projection&a=...&b=...
```

Compare aynı entity-type semantic contract'ını korur.

## 8.13 Global Search / Command Search

Çok sayıda deep entity page olduğu için global search ürünün temel navigation araçlarından biri olacaktır.

Search:
- fixtures;
- teams;
- players;
- competitions;
- projection families
üzerinde çalışabilir.

Desktop:
- header search;
- `/` shortcut veya `Cmd/Ctrl + K` düşünülebilir.

Mobile:
- header search icon;
- full-screen search sheet.

Result grouping örneği:

```text
Matches
Teams
Players
Competitions
Projections
```

Bir takım arandığında generic search result sayfasında bırakılmak yerine direkt Team Page'e gidilir.

## 8.14 Cross-Linking Rules — Sayfalar Nasıl Birbirine Bağlanır?

Bu kurallar kullanıcıyı doğal graph içinde tutar:

| Kaynak | Primary click | Secondary entity click |
|---|---|---|
| Fixture card | Match Center | Team/Competition |
| Projection card | Match Center relevant section | Team/Player |
| Player prop | Match Center Player Props | Player Page |
| Power Ranking row | Team Page | Competition Page |
| Team stat row | Team Page | Competition Page |
| Player stat row | Player Page | Team/Competition |
| Odds movement row | Match Center Markets section | bookmaker/source context |
| Alert | event'in canonical page'i | My Alerts |
| Studio leg | Match Center | Projection/Market context |
| Track Record row | exact historical artifact / snapshot | Match Center |
| Today's Brief item | relevant canonical entity/page | ilgili hub |

### Interaction precedence

Card üzerindeki:
- `+` → Betslip / Studio action;
- `Watch` → Watchlist;
- `Compare` → Compare Mode;
- primary body click → detail page.

Bu actions birbirinin davranışını çalmaz.

## 8.15 Breadcrumb / Context Rules

Deep pages bir kullanıcının nerede olduğunu görünür kılmalıdır.

Örnek Match Center context:

```text
Brazil
> Serie A
> Flamengo vs Palmeiras
```

Team:

```text
Premier League
> Arsenal
```

Player:

```text
Arsenal
> Bukayo Saka
```

Breadcrumb her yerde zorunlu değildir; mobile'da compact back/context header kullanılabilir.

## 8.16 Global Date/Time Scope Persistence

Date/time scope bütün siteye körlemesine global state olarak uygulanmaz.

Kural:
- fixture/date-driven yüzeylerde scope taşınır;
- season-long/entity-history yüzeylerinde scope semantik olarak uygun değilse uygulanmaz.

Örnek:

```text
/matches?range=next-12h
  → /projections/fixtures?range=next-12h
  → /markets/value?range=next-12h
```

Ama:

```text
/team/arsenal
```

sayfasına gidildiğinde team profile tarihsel context'i kendi filter'larıyla yönetebilir.

## 8.17 Persistent Betslip Navigation Behavior

Desktop:
- right-side persistent drawer;
- header'daki Betslip control ile collapse/expand;
- selection count visible;
- user preference remembered.

Tablet:
- right overlay drawer.

Mobile:
- bottom sheet / full-height sheet.

Betslip şu ana yüzeylerde kullanılabilir:
- Home;
- Matches;
- Projections;
- Markets;
- Match Center;
- Studio.

Stats ve Track Record içinde açılabilir olmak zorunda değildir; yalnızca gerçekten selectable current market context varsa gösterilir.

## 8.18 Mobile Navigation

Mobile'da desktop'taki altı primary item doğrudan tek sıraya sıkıştırılmaz.

Recommended bottom navigation:

```text
Home
Matches
Projections
Studio
My
```

Mobile header:
- compact CalibraXI mark;
- Search;
- Notifications;
- menu/browse action.

Browse/menu içinde:
- Stats;
- Markets;
- Track Record;
- Competitions;
- Teams;
- Players;
- Methodology
bulunur.

Bu yapı mobile'da en sık tekrar edilen işlere öncelik verir.

## 8.19 Supporting / Trust Routes

Core navigation dışında ama ürün için gerekli supporting pages:

```text
/methodology
/pricing
/responsible-use
/about
/account
/login
/register
/terms
/privacy
```

`Methodology` özellikle:
- Forecast;
- Reliability;
- Power Ratings;
- Track Record;
- Studio joint probability
gibi kavramları açıklamak için güçlü bir trust surface olacaktır.

## 8.20 Navigation'da Bilinçli Olarak Ayrı Tab Yapılmayacak Alanlar

Aşağıdakiler top-level navigation item olmaz:

- **Predictions** — Projections ile duplicate olmaz.
- **Value Bets** — Markets altında yaşar.
- **Power Rankings** — Stats altında yaşar.
- **Teams** — Stats/Explore içinden keşfedilir, entity directory olarak kalır.
- **Players** — Stats/Explore içinden keşfedilir.
- **Leagues** — Competitions directory/entity sistemi içinde.
- **Watchlist** — My CalibraXI altında.
- **Alerts** — utility + My CalibraXI.
- **Strategy Lab** — My CalibraXI altında.
- **Compare** — contextual utility.
- **Daily Builder / Same Match Builder** — Studio mode'ları.
- **Today's Brief** — utility/day-context surface.
- **Betslip** — global panel, destination değil.

Bu kararın amacı CalibraXI'ın feature sayısı büyüdükçe header'ın parçalanmasını engellemektir.

## 8.21 Canonical User Journeys

### Journey A — Maçtan başlayan kullanıcı

```text
Home
→ Today's Fixtures
→ Match Center
→ Projection
→ Why This Projection?
→ Markets
→ Add to Studio / Betslip
→ Simulation Bet
→ My CalibraXI Performance
```

### Journey B — Projection arayan kullanıcı

```text
Projections
→ Projection Explorer
→ filtered result
→ Match Center
→ Market comparison
→ Studio
```

### Journey C — Veri araştıran kullanıcı

```text
Stats
→ Power Rankings
→ Team Page
→ upcoming fixture
→ Match Center
→ Projections
```

### Journey D — Market fırsatı arayan kullanıcı

```text
Markets
→ Value / Odds Movement
→ Match Center
→ exact Forecast + market context
→ Studio / Betslip
```

### Journey E — Kendi sistemini test eden kullanıcı

```text
My CalibraXI
→ Strategy Lab
→ Backtest
→ Save Strategy
→ Alert candidate
→ Studio
→ Simulation Bet
→ Forward Performance
```

### Journey F — Şeffaflık kontrolü

```text
Track Record
→ historical result
→ exact historical artifact
→ Historical Snapshot
→ "CalibraXI o anda ne biliyordu?"
```

## 8.22 Sitemap Snapshot

```text
/
├── matches
│   └── h2h/{slug}/{fixtureId}
│
├── projections
│   ├── fixtures
│   ├── form-edges
│   ├── player-props
│   ├── team-outrights
│   └── top-10
│
├── stats
│   ├── power-rankings
│   ├── teams
│   ├── players
│   └── streaks
│
├── competitions
│   └── competition/{slug}
│
├── teams
│   └── team/{slug}
│
├── players
│   └── player/{slug}
│
├── markets
│   ├── value
│   ├── odds-movement
│   ├── best-prices
│   └── movers
│
├── studio
│
├── track-record
│   ├── forecasts
│   ├── signals
│   ├── recommendations
│   └── studio
│
├── compare
│
├── my
│   ├── watchlist
│   ├── alerts
│   ├── bets
│   ├── strategies
│   ├── saved
│   ├── performance
│   └── settings
│
├── methodology
├── pricing
└── responsible-use
```

Bu sitemap fiziksel framework routing'ini dikte etmez; ürün bilgi mimarisinin canonical working target'ıdır.

---

# 9. Eski Mimariden Korunacak Analitik Çekirdek

Yeni UI ve ürün yönü değişse de aşağıdaki ilkeler CalibraXI'ın güvenilirlik omurgası olarak korunur.

## 9.1 Point-in-time truth
Forecast yalnızca cutoff anında bilinen ve policy tarafından eligible kabul edilen bilgiye dayanır. Sonradan gelen bilgi geçmiş tahmini “düzeltmek” için kullanılmaz.

## 9.2 Immutable analytical history
Evidence Manifest, Feature Snapshot, Prediction Run, Forecast, Signal Evaluation, Recommendation Decision, publication ve evaluation geçmişi append-only/supersession mantığıyla korunur.

## 9.3 Current Canonical Run
Fixture × Run Context için yüzeyden yüzeye farklı “latest prediction” seçilmez. Currentness ortak ve governed bir karardır.

## 9.4 PRE_MATCH ve LIVE ayrımı
İkisi ayrı Run Context'tir. Live çıktısı pre-match tahminini mutate etmez.

## 9.5 Coherence Family ve Primary Distribution
Aynı stochastic process'ten türeyen marketler mümkün olduğunca tek coherent parent distribution'dan türetilir. Aynı aile içinde market başına bağımsız “en iyi model” seçilmez.

## 9.6 No Runtime Model Shopping
Signal, Recommendation, UI, API veya market attractiveness'a göre runtime'da model seçilmez. Capability promotion offline evidence ile yapılır.

## 9.7 Calibration parent-level'dır
Child marketleri tek tek “güzel görünsün” diye kalibre etmek yasaktır. Calibration probability parent/family semantics'ini korur.

## 9.8 Probability != Reliability != Signal != Recommendation
- Forecast Probability: olayın model olasılığı.
- Reliability: o Forecast'a ilişkin evidence/applicability/stability desteği.
- Confidence: ancak ayrı ve doğrulanmış bir summary tanımı dondurulursa kullanıcıya sunulur.
- Signal: Forecast + reliability + exact betting contract + market observation/fair value değerlendirmesi.
- Recommendation: kullanıcı-facing seçim kararı; Signal'dan ayrı governed layer gerektirir.

## 9.9 Market observation Forecast'ı değiştirmez
Odds değişimi yeni market context / Signal Evaluation doğurabilir; geçmiş Forecast probability aynı kalır.

## 9.10 Outcome ve Track Record ayrı authority'dir
Sonuç observation → adjudication → authoritative outcome → atomic evaluation → track record projection zinciri korunur.

---

# 10. Yeni Ürün Yönü Nedeniyle Yeniden Açılan Eski Sınırlar

Aşağıdaki alanlar eski belgelerde özellikle sonraki faza bırakılmıştı. Yeni ürün vizyonu nedeniyle artık resmi olarak tasarlanması gereken ürün/mimari alanlardır.

## 10.1 Recommendation Architecture — REOPENED -> PRODUCT SPEC DEFINED / ANALYTICAL GOVERNANCE SPECIFIED
Günün tahmini, en güvenilir seçimler, builder ve user-facing pick dili için genuine Recommendation Decision katmanı `CalibraXI-Analytics-Architecture.md` içinde tanımlandı. Recommendation immutable decision + policy/version + candidate population + exact target/lineage + publication/withdrawal/evaluation chain'dir. Signal, rank veya UI state Recommendation değildir.

## 10.2 Curation / Ranking Architecture — REOPENED -> PRODUCT SPEC DEFINED / ANALYTICAL GOVERNANCE SPECIFIED
Homepage “günün en iyileri”, power rankings ve widget ordering için:
- football team power ranking;
- recommendation curation;
- product ordering
birbirinden ayrılmalıdır.

Probability/Edge sıralamasını gizli Recommendation mekanizması olarak kullanmak yasaktır.

`Today's Top Projection` ve `Top 10` immutable Curation Decision / Curation Policy output'larıdır. Daily Pick, Single Selection Recommendation ve Daily Studio recommendation ayrı decision/publication families'dir. Explicit withhold, candidate non-recommend reasons, duplicate exposure, diversity/concentration, currentness ve no-backfill rules canonical analytics document'te tanımlıdır.

## 10.3 Combination / Bet Builder Architecture — PRODUCT SPEC DEFINED / GOVERNANCE SPECIFIED / TARGET-FAMILY MATH OPEN

Section 4.5 ile Studio'nun product/UX contract'ı tanımlanmıştır:
- one canonical Studio;
- Daily Cross-Match;
- Daily Same-Match;
- Manual Build;
- Saved/Strategy-assisted material;
- leg identity;
- compatibility;
- contradiction/redundancy;
- dependency support;
- combination probability support classes;
- price basis;
- Studio → Betslip boundary;
- immutable published/placed snapshots.

Governance canonical analytics document'te dondurulmuştur. Aşağıdaki target-family mathematical capabilities separately validated/versioned olmadan production Recommendation/Publication'a açılmayacaktır:
- same-family joint derivation;
- cross-family dependence;
- independence qualification;
- joint calibration;
- combined settlement;
- Combination Reliability;
- correlation/effective-sample treatment in combination evaluation.

UI/product spec bu matematiği kendi içinde icat edemez.

## 10.4 Virtual Betslip / Simulation Ledger — NEW
Eski coupon/bets yüzeylerinden semantik olarak ayrılmış, gerçek para içermeyen bir simulation domain'i gerekir.

## 10.5 Strategy Lab — NEW
Kullanıcıya özel strategy tagging, simulation populations ve performans projection'ları gerekir.

## 10.6 User-facing Confidence Presentation — REOPENED
Kullanıcı “güven derecesi” görmelidir; fakat bu arbitrary `%87 confidence` olamaz. Confidence/grade/band formatı Reliability evidence'tan türetilen ve tarihsel olarak validate edilen ayrı specification ile tasarlanmalıdır.

## 10.7 Homepage / Information Architecture — SUPERSEDED
Eski üç-destination merkezli Today / Signals / Track Record ana deneyimi tek başına yeterli değildir. Yeni ana yüzey **Daily Analytics Dashboard** olacaktır. Today/Matches, Signals, Track Record gibi alanlar dashboard içi modüller ve/veya ayrı derin sayfalar olarak devam edebilir.

## 10.8 Entity Pages / Match Center — NEW
Fixture, League, Team ve Player artık yalnızca listelerdeki satırlar değildir; canonical deep page entity'leridir.

## 10.9 Watchlist / Alerts — NEW
User-specific watch relationships ve threshold/event-based alert definitions ayrı product domain'i gerektirir. Alert generation analytical truth üretmez; mevcut governed facts üzerindeki notification policy'dir.

## 10.10 Personal Workspace / Future Profile — NEW
My CalibraXI kullanıcıya ait kişisel terminaldir. Gelecekte sosyal profile dönüşebilme ihtimali nedeniyle personalization, privacy ve visibility kavramları baştan ayrılmalıdır.

## 10.11 Odds Movement Analytics — EXTENDED
Immutable Market Observation timeline artık yalnızca Signal upstream girdisi değil, kullanıcı-facing historical market analytics surface olarak da kullanılacaktır.

## 10.12 Historical Snapshot UX — NEW
Point-in-time architecture kullanıcıya doğrudan görünür hale getirilecektir. Historical read exact Prediction Run/Publication/Market Observation identity'lerini korur.


## 10.13 Public Track Record Product Surface — PRODUCT SPEC DEFINED

Frozen Track Record / Evaluation Architecture analytical authority olarak korunur.

Section 5 artık bunun public product/read specification'ını tanımlar:
- Forecast / Signal / Recommendation / Studio ayrı report families;
- publication-qualified populations;
- population/exclusion transparency;
- artifact drill-down;
- correction/report versioning;
- as-of/watermark;
- sample/uncertainty presentation;
- no outcome-conditioned performance filtering;
- public Track Record vs `/my/performance` separation.

UI/report layer analytical Evaluation veya Outcome authority üretmez.


## 10.14 My CalibraXI Personal Workspace — PRODUCT SPEC DEFINED

My CalibraXI personal product domain Section 7.6–7.7 ile tanımlandı:

- Watchlist;
- Smart Alerts;
- Notification Center;
- virtual Simulation Ledger;
- Virtual Bankroll;
- Strategy Lab;
- Saved Research;
- personal Performance;
- settings/privacy;
- future profile/social compatibility.

Canonical route `/my`; `/dashboard` canonical değildir.

User-owned state canonical Forecast/Signal/Recommendation/Market/Outcome truth'u mutate etmez.

Strategy Lab backtest/forward-test PIT discipline'ini korur.

Future social/profile direction private-by-default personal-state boundary'sini bozmayacaktır.


## 10.15 Source Acquisition / Scraper Platform — PRODUCT BOUNDARY / ENGINEERING SPEC CONSOLIDATED

All football, statistical, player, fixture, market, and identity-asset data consumed by CalibraXI passes through the governed CalibraXI multi-source acquisition platform and its provenance, validation, entity-resolution, and point-in-time controls.

SoccerData is an approved adapter/accelerator, not canonical truth. Scraped or fetched source data is evidence about what a source reported; it is not canonical football truth.

The detailed acquisition, source-adapter, raw-evidence, source-authority, PIT, asset, health, quarantine, and implementation specification is consolidated in `docs/CalibraXI-Engineering.md`. This section states the product boundary only; it does not duplicate the engineering architecture.
# 11. Legacy Source Register

Aşağıdaki eski dokümanlar çöpe atılmayacaktır. Yeni canonical set oluşturulurken her biri izlenecektir.

| Source | Ana rol | Konsolidasyon davranışı |
|---|---|---|
| `domain-constitution(2).md` | Analitik anayasa | **KORU — çekirdek semantik** |
| `canonical-domain-model(3).md` | Domain kimlikleri, lifecycle, authority | **KORU — çekirdek semantik** |
| `canonical-data-architecture(2).md` | Veri otoritesi, immutability, lineage, PIT reconstruction | **KORU — çekirdek semantik** |
| `market-prediction-architecture(2).md` | Forecast target, coherence family, market derivation | **KORU — analitik çekirdek** |
| `feature-snapshot-architecture(3).md` | Point-in-time feature/evidence sistemi | **KORU — analitik çekirdek** |
| `baseline-models(3).md` | Baseline araştırma programı | **KORU — araştırma temeli** |
| `ensemble-architecture(3).md` | Ensemble/Combination Capability sınırı | **KORU — analitik temeli** |
| `calibration-architecture(4).md` | Kalibrasyon sınırı | **KORU — analitik temeli** |
| `confidence-reliability-architecture(5).md` | Reliability/Confidence ayrımı | **KORU — fakat kullanıcı-facing confidence yeniden tasarlanacak** |
| `signal-engine-architecture(4).md` | Forecast + price + reliability → Signal | **KORU — Recommendation ile genişletilecek** |
| `track-record-evaluation-architecture(4).md` | Outcome/evaluation/track record | **KORU — ROI ve builder raporlarıyla genişletilecek** |
| `production-pipeline-architecture(4).md` | Üretim orkestrasyonu | **KORU — yeni proje uygulamasında yeniden fiziksel tasarım yapılabilir** |
| `api-contracts-architecture(4).md` | API authority/read contract | **KORU — delivery ilkeleri** |
| `ui-ux-architecture(5).md` | Eski conceptual UI/UX | **YENİDEN AÇILDI — yeni dashboard yönü öncelikli** |
| `visual-design-wireframes(3).md` | Eski U4 wireframe | **REFERANS — yeni homepage tarafından büyük ölçüde supersede edilecek** |
| `frontend-rebuild-plan(3).md` | Eski frontend implementation plan | **ARŞİV/MIGRATION EVIDENCE — yeni projeyi kısıtlamaz** |
| `governed-read-implementation-plan(3).md` | Eski governed-read implementation plan | **ARŞİV/MIGRATION EVIDENCE** |
| `repository-audit-replacement-v1.md` | Eski repo audit replacement | **ARŞİV/MIGRATION EVIDENCE** |
| `implementation-protocol(1).md` | GitHub handoff/güvenlik protokolü | **OPERASYONEL REFERANS** |
| `calibraxi-product-and-architecture.md` | Yeni ürün keşif özeti | **BİRLEŞTİR — yeni canonical product doc'a taşınacak** |

---

# 12. Nihai Dokümantasyon Hedefi

Finalde 20+ parçalı mimari arşiv yerine en fazla üç büyük kanonik belge hedeflenmektedir:

### 1. `CalibraXI.md`
Ürün vizyonu, sayfalar, dashboard, widget'lar, UX, kullanıcı akışları, memberships, simulation betslip, power rankings, stats surfaces, Recommendation/Builder davranışı, track-record presentation ve ürün kararları.

### 2. `CalibraXI-Analytics-Architecture.md`
Domain constitution + evidence/PIT + Feature Snapshot + Forecast families + baseline/ensemble/calibration + Reliability/Confidence + Signal + Recommendation + Curation/Ranking + Combination/Studio + Power Ratings + Outcome/Evaluation/Track Record matematik ve governance katmanları. Recommendation/Curation governance bu belgeye işlenmiştir.

### 3. `CalibraXI-Engineering.md`
Canonical data architecture + physical direction + ingestion/providers + production pipeline + API contracts + auth/payment + observability + admin + deployment + migration/implementation protocol. Source-acquisition implementation authority lives here; the former `docs/engineering/source-acquisition.md` path is not a long-term canonical document.

Bu üçlü canonical documentation modelidir. `AGENTS.md`, `CONTEXT.md` ve `docs/agents/` yalnızca lightweight working/context/wayfinding rolündedir; project architecture'ı duplicate etmez. Ordinary decisions relevant canonical document'in Decision Log'unda kalır. Standalone ADR yalnızca exceptional, high-impact decision için oluşturulur.

---

# 13. Decision Log

## 13.1 2026-09-21

Bu turda kullanıcı tarafından verilen yeni kararların tamamı işlenmiştir:

- Homepage = doğrudan dashboard.
- Küçük yatay tanıtım banner'ı.
- Günün fikstürü.
- Günün tahmini.
- Günün öne çıkan / formda takımları + stats.
- League Power Rankings: rank + ATT + DEF + OVR + movement.
- Daily Bet Builder Type 1: farklı maçlardan güçlü selections.
- Daily Bet Builder Type 2: tek maç içinde birden fazla güçlü selections.
- Günün güçlü istatistik/trend kartları + odds + reliability/confidence.
- `+` ile seçim ekleme.
- Desktop sağ panelde persistent betslip.
- Virtual site balance.
- Sanal kupon oluşturma ve settlement takibi.
- Kullanıcının kendi stratejisini gerçek tarihsel ledger ile test edebilmesi.
- CalibraXI'ın tüm prediction'ları ile builder'ların ayrı track-record raporları.
- Detaylı ROI/performance analytics.
- Homepage aşağı indikçe Player Stats.
- Team Stats.
- Streak Stats.
- Günün O2.5 / O3.5 eğilimleri.
- Günün BTTS eğilimleri.
- Bu ailelerin benzeri yeni stats/analytics widget'larının türetilebilir olması.
- Kullanıcının bundan sonraki karalama notlarının hiçbir maddesi kaybedilmeden bu living document'a eklenmesi.

## 13.2 2026-09-22

Bu turda eklenen / değiştirilen kararlar:

- **LIGHT-FIRST:** Eski dark-first görsel yön supersede edildi; yeni CalibraXI birincil olarak light theme olacak.
- Prediction-oriented ve uyumlu date-aware sayfalara ortak tarih/zaman scope selector eklenecek.
- Preset'ler: Today, Tomorrow, This Weekend, Next 7 Days, Custom Date Span.
- Rolling kickoff filtreleri: önümüzdeki 3 / 6 / 12 saat içinde başlayacak maçlar.
- `/projections` tüm projection ailelerini toplayan hub olacak.
- Dedicated projection sayfaları ilk etapta:
  - `/projections/fixtures`
  - `/projections/form-edges`
  - `/projections/player-props`
  - `/projections/team-outrights` *(working route)*
  - `/projections/top-10`
- Projection hub'daki bölümlerde `View All` ile dedicated alt sayfaya geçilecek.
- Date/filter context mümkün olduğunca hub → subpage navigation boyunca korunacak.
- Ana navigasyonun altında horizontally moving bir **Live Match Tracker** olacak.
- Live tracker collapse/expand edilebilecek.
- Live tracker davranış açısından kullanıcının yüklediği xGuara örneğinden esinlenecek fakat dark UI kopyalanmayacak; CalibraXI light theme'e adapte edilecek.
- Live ticker PRE_MATCH Forecast'ı değiştirmeyecek; live analytics ayrı LIVE Run Context olarak kalacak.

## 13.3 2026-09-22 — Deep Pages / Studio / Retention Round

- Her fixture için **Match Center / H2H** deep page olacak; lineups dahil maçla ilgili bütün önemli alanlar burada birleşecek.
- Working URL family `/h2h/...`; stable Fixture identity URL'de korunacak.
- Her league/competition, team ve supported player için ayrı canonical page olacak.
- Gerçek takım armaları, oyuncu fotoğrafları ve competition logoları kullanılacak; AI-generated substitute kullanılmayacak.
- Projection Explorer eklendi.
- `Why This Projection?` explainability eklendi.
- Odds Movement / Market Analytics eklendi.
- Watchlist + Smart Alerts detaylandırıldı.
- My CalibraXI kişisel terminal olacak; ileride profile/social katmana genişletilebilir.
- Strategy Lab point-in-time backtest, forward/paper test, versioning ve strategy performance ile genişletildi.
- Power Rankings History eklendi.
- Today's Brief ilk günlük ziyaretten sonra yaklaşık 60 dakika görünür olacak, sonra dashboard'dan kalkacak; manuel yeniden açılabilecek.
- Prominent Data Coverage/Freshness badge özelliği şimdilik **DEFERRED**.
- Compare Mode eklendi.
- Historical Snapshot / “CalibraXI o anda ne biliyordu?” eklendi.
- Builder deneyimleri tek **CalibraXI Studio** altında birleşti; Daily Cross-Match, Daily Same-Match ve Manual Studio mode/preset olacak.
- `Football Intelligence` terimi **RETIRED**.
- Working category: **Predictive Football Analytics**.
- **Football, Calibrated.** public-facing kısa marka cümlesi/tagline olarak **LOCKED / APPROVED**.
- `Daily Intelligence Dashboard` → `Daily Analytics Dashboard`.
- `CalibraXI-Intelligence-Architecture.md` → `CalibraXI-Analytics-Architecture.md` çalışma adı.

## 13.4 2026-09-22 — Global IA / Navigation Round

Bu turda kullanıcı tarafından delegasyonla onaylanan çalışma yönü:

- **Football, Calibrated.** public-facing kısa marka cümlesi/tagline olarak **LOCKED / APPROVED**.
- Primary desktop navigation:
  - Matches
  - Projections
  - Stats
  - Markets
  - Studio
  - Track Record
- Home ayrı nav item olmayacak; CalibraXI logosu `/` dashboard'a götürecek.
- Header utility layer:
  - Search
  - Today's Brief
  - Notifications
  - My CalibraXI
  - Betslip toggle/count
- Live Match Tracker global shell'de primary header altında konumlanacak.
- `/matches` date/time-scoped fixture discovery hub olacak.
- Individual fixture primary click → `/h2h/.../{fixtureId}` Match Center.
- `/projections` model-output hub; `View All` category listing'e, individual projection relevant entity/context page'e gider.
- `/stats` Power Rankings, team/player leaders ve streaks için data-first hub olacak.
- League/cup/tournament entity'leri canonical olarak ortak `/competition/{slug}` route ailesi altında temsil edilecek; UI “Leagues & Competitions” diyebilir.
- `/markets` market-price ve odds/value analytics için projection dünyasından ayrı hub olacak.
- `/studio` tek canonical builder destination olmaya devam edecek.
- `/track-record` public CalibraXI performance için top-level ve görünür destination olacak.
- Kullanıcının personal simulation performance'ı `/my/performance` altında public Track Record'dan ayrı tutulacak.
- Strategy Lab canonical personal route'u `/my/strategies`.
- Watchlist ve Alerts management My CalibraXI altında; Notifications header utility olarak çalışacak.
- Compare Mode top-level navigation item olmayacak; contextual action + shareable `/compare` route'u olacak.
- Global Search/Command Search deep entity navigation için temel utility olacak.
- Mobile recommended bottom nav:
  - Home
  - Matches
  - Projections
  - Studio
  - My
- Stats, Markets, Track Record ve entity directories mobile Browse/menu altında erişilecek.
- `Predictions`, `Value Bets`, `Power Rankings`, `Teams`, `Players`, `Leagues`, `Watchlist`, `Alerts`, `Strategy Lab`, `Compare`, ayrı builder türleri ve Today's Brief top-level navigation item olarak çoğaltılmayacak.

## 13.5 2026-09-22 — Homepage First-30-Seconds Architecture

Bu turda homepage vertical composition için canonical working direction belirlendi:

- Launch/default homepage yaklaşımı: **Command Center**.
- Alternatif Match-First yaklaşım `/matches` için korunur.
- Alternatif Personalized Terminal yaklaşımı `/my` ve future logged-in personalization için korunur.
- Homepage üç ayrı mode'a bölünmez.
- Exact vertical order:
  1. optional micro announcement;
  2. primary header;
  3. collapsible Live Match Tracker;
  4. first-hour Today's Brief;
  5. Daily Scope Bar;
  6. Daily Pulse: Today's Fixtures + Today's Top Projection + Form/Power Movers;
  7. Top Projections Board;
  8. Today's Angles;
  9. Markets Snapshot;
  10. Power Rankings;
  11. CalibraXI Studio Preview;
  12. transparent Track Record snapshot;
  13. Statistics Discovery;
  14. logged-in Personalized Continuation;
  15. Footer/Trust layer.
- Raw stat / Forecast / Market Edge / Form Edge kart tipleri homepage'de açıkça etiketlenir.
- Date scope yalnızca date-driven homepage modules üzerinde ortak davranır; Power Rankings ve season-level stats kendi period controls'ünü kullanır.
- Studio homepage'de Daily Cross-Match / Daily Same-Match preview gösterir; Manual Studio tam `/studio` yüzeyinde kalır.
- Public Track Record preview sample/population/period bilgisi açık olan ince bir transparency surface olarak yer alır.
- Betslip responsive davranışı homepage grid'ini ezmeyecek şekilde large-desktop pinned, medium overlay, mobile sheet olarak ele alınır.

## 13.6 2026-09-22 — Match Center / H2H Full Architecture

Bu turda Match Center'ın full working structure'ı tanımlandı:

- User-facing adı **Match Center**, working route family `/h2h/.../{fixtureId}`.
- Stable Fixture identity URL'de korunur.
- Match Center tek scrollable deep research page olacak; 12–15 top-level tab yerine **6 sticky local sections** kullanır:
  - Summary
  - Projections
  - Lineups
  - Matchup
  - Markets
  - History
- Player Props → Projections altında.
- H2H, form, Power Ratings, team stats, streaks, key players → Matchup altında.
- Injuries/suspensions/expected/confirmed XI → Lineups altında.
- Odds comparison, consensus, movement ve model-vs-market → Markets altında.
- Exact historical Prediction Runs / snapshots / outcomes / evaluations → History altında.
- Match Hero identity-first olacak; team crests, kickoff/state, venue, power/form summary ve quick actions kullanacak.
- Same-match builder Match Center içinde ayrı engine olarak yaratılmayacak; `Open in Studio` kullanılacak.
- Lineup confirmation sonrası projection değişimi gösterilecekse iki immutable run karşılaştırılacak; old Forecast mutate edilmeyecek.
- Upcoming, live, finished, postponed/cancelled fixture states aynı stable Match Center identity içinde state-aware composition kullanacak.
- LIVE durumunda pre-match Forecast açıkça `PRE-MATCH VIEW` olarak frozen kalacak.
- LIVE model yoksa live score/stat gösterilir fakat live probability uydurulmaz.
- Finished sayfada final result ile pre-match historical view birlikte görülebilecek; hindsight rewrite yasak.
- Match Center deep links `#projections`, `#lineups`, `#markets`, `#history` gibi anchor'ları destekleyebilir.
- Match Center light-first visual rhythm: identity hero → summary grid → projection matrix → lineup pitch → matchup comparison → markets → historical timeline.

## 13.7 2026-09-22 — Projections Hub / Explorer Full Architecture

Bu turda Projections product area tam working architecture seviyesine genişletildi:

- User-facing `Projection` ürün sunum terimidir; canonical analytical artifact **Forecast** olarak kalır.
- Canonical projection routes:
  - `/projections`
  - `/projections/fixtures`
  - `/projections/form-edges`
  - `/projections/player-props`
  - `/projections/team-outrights`
  - `/projections/top-10`
  - `/projections/explore`
- `/projections` curated discovery hub.
- `/projections/explore` dedicated power-user screener olarak **canonical working route** haline geldi.
- Projections Hub vertical order:
  - projection header;
  - date/time scope;
  - local family navigation;
  - Top 10 preview;
  - Fixture Projections;
  - Form Edges;
  - Player Props;
  - Team Outrights;
  - Model vs Market preview;
  - Explorer entry;
  - Saved Views.
- Top 10 yalnızca probability sırası veya “Best Bets” değildir; ayrı Projection Curation Policy gerektirir.
- Fixture Projections cards/table görünümü ve dedicated listing tanımlandı.
- Form Edge'in Forecast ve Market Edge'den ayrı analytical discovery object olduğu netleştirildi.
- Player Props, historical player leaderboard'dan açıkça ayrıldı; lineup/minutes context'i tasarlandı.
- Team Outrights fixture-time scope'tan ayrıldı; competition/season/as-of filters kullanacak.
- Projection Explorer filter groups:
  - Time & Fixture;
  - Competition;
  - Entity;
  - Projection;
  - Probability;
  - Reliability;
  - Market Context;
  - Product State.
- Filters projection family'ye göre contextual olarak açılıp kapanır.
- Explorer URL state bookmark/share/back-forward friendly olacak.
- Explorer result views: Compact Table + Cards.
- Sorting bir Recommendation üretmez; default Curated/Relevance ve semantic-safe sort modes tanımlandı.
- Result semantic labels Forecast / Form Edge / Market Edge / Signal / Recommendation / Player Prop / Outright olarak ayrılır.
- Quick detail drawer + canonical deep page navigation birlikte kullanılabilir.
- Multi-select research mode Compare / Watch / Open in Studio destekleyebilir; Explorer combined probability hesaplamaz.
- Saved Views `/my/saved` ile entegre olacak ve Smart Alert'e dönüştürülebilecek.
- No Results / Unsupported / No Current Projection ayrı state'lerdir.
- Prominent generic Data Freshness badge hala deferred; correctness için explicit availability states korunur.
- Probability movement ve Odds movement ayrı timelines olarak gösterilir.
- Mobile Projections ve filter-sheet davranışı tanımlandı.

## 13.8 2026-09-22 — Stats / Competition / Team / Player Architecture

Bu turda Stats ve football entity pages full working architecture seviyesine çıkarıldı:

- `Stats`, `Projections` ve `Markets` semantically ayrıldı:
  - Stats = observed/historical aggregated football data;
  - Projections = future model Forecast outputs;
  - Markets = bookmaker/market observations.
- Canonical Stats routes:
  - `/stats`
  - `/stats/power-rankings`
  - `/stats/teams`
  - `/stats/players`
  - `/stats/streaks`
- Future metric-family routes goals/shots/corners/cards için extensible yapı bırakıldı.
- Stats Hub: Power Rankings → Team Leaders → Player Leaders → Streaks → O/U/BTTS → shots/corners/cards discovery.
- Competition/season/timeframe/home-away/minimum-sample controls tanımlandı.
- Metric denominator, sample ve timeframe açık olmalı; aynı label altında farklı populations sessizce karıştırılmayacak.
- Power Rankings flagship stats product olarak detaylandırıldı.
- ATT/DEF/OVR exact mathematics hâlâ Power Rating Architecture'a bırakıldı; UI matematik icat etmeyecek.
- Cross-league ranking yalnızca rating scale gerçek anlamda comparable ise yayınlanacak.
- Power Ranking history exact immutable snapshots ile gösterilecek.
- Team leaderboard metric families ve movement comparison rules tanımlandı.
- Player leaderboards total/per-90, position filters ve minimum-minutes threshold ile tanımlandı.
- Streaks active/historical olarak ayrıldı; competition/sample scope görünür olacak.
- Statistical trend'in future probability olmadığı tekrar canonical rule olarak donduruldu.
- Percentile/distribution context same competition/population üzerinden tanımlandı.
- Stats Compare/Watch entry points eklendi.
- Canonical entity directories `/competitions`, `/teams`, `/players`.
- Canonical competition route `/competition/{slug}`.
- Competition Page local sections: Overview, Standings/format equivalent, Fixtures, Power Rankings, Teams, Players, Stats, Projections.
- League standings ile CalibraXI Power Rankings ayrı semantic objects olarak korunacak.
- Team Page local sections: Overview, Fixtures, Form, Power, Stats, Squad, Projections, History.
- Team Form ile Power Rating ayrımı korundu.
- Team Squad gerçek player assets + availability semantics ile detaylandırıldı.
- Player Page local sections: Overview, Stats, Matches, Props, Form, History.
- Player historical stats ile future Player Props aynı sayfada fakat ayrı semantic sections olarak tutulacak.
- Current player transfer association historical fixture context'i rewrite etmeyecek.
- Competition, Team ve Player pages analytical calculation authority olmayacak; canonical data/Forecast read surfaces olarak kalacak.

## 13.9 2026-09-22 — Markets / Odds / Value Full Architecture

Bu turda Markets alanı full working architecture seviyesine çıkarıldı:

- Canonical routes:
  - `/markets`
  - `/markets/value`
  - `/markets/odds-movement`
  - `/markets/best-prices`
  - `/markets/movers`
- Markets = bookmaker/exchange price observations; Projections = model Forecast; Stats = observed football data.
- Market Observation exact Betting Contract + Selection + source + chronology ile immutable external evidence olarak korundu.
- Forecast Cutoff ile Market Knowledge Time ayrı time axes olarak canonical hale getirildi.
- New odds Forecast probability'yi değiştirmez ve yeni Forecast Run zorunlu kılmaz.
- Exact line/period/settlement mismatch karşılaştırmaları yasaklandı.
- Decimal odds default working display; format conversion margin removal değildir.
- Markets Hub: Market Pulse → Model vs Market → Movers → Best Prices → Movement → Watched Markets.
- Üç distinct comparison mode:
  - Source-Specific;
  - Best Observed / Best Offered Price;
  - Consensus.
- Best-per-selection cross-source prices market-belief/no-vig distribution olarak kullanılmayacak.
- Quoted implied probability (`1/odds`) ile normalized/no-vig market probability ayrıldı.
- No-vig yalnızca coherent outcome set + versioned valid normalization method ile gösterilecek.
- `/markets/best-prices` exact selection source comparison surface olarak tanımlandı.
- `/markets/odds-movement` same-contract price history olarak tanımlandı.
- Price Movement ile Line Movement ayrı semantics olarak donduruldu.
- Opening/Closing price product semantics tanımlanmadan ilk/son database row diye varsayılmayacak.
- Closing price geçmiş pre-match evaluation'a sızdırılmayacak.
- `/markets/movers` price/line/source-spread/consensus movement discovery olarak tanımlandı; movement motive'i (“smart money” vb.) evidence olmadan uydurulmayacak.
- Fair Contract Value simple binary dışında full settlement-aware valuation gerektirir.
- Simple `p × odds - 1` EV formülü complex contracts'a uygulanmayacak.
- `/markets/value` Market Edge / Signal evaluation surface'tir; positive edge ≠ eligible Signal ≠ Recommendation.
- Signal user presentation ELIGIBLE / NOT_ELIGIBLE / CANNOT_EVALUATE authority'sini korur.
- Market watch/alerts, saved market views ve threshold-jitter controls eklendi.
- Market current quote timestamps/state correctness için gösterilebilir; bu deferred generic Data Freshness badge kararını geri açmaz.
- Exchange/liquidity architecture future-compatible bırakıldı.
- Forecast Availability ve Market Availability ayrı state'ler olarak korundu.
- Source corrections/conflicts historical market/signal truth'u sessizce mutate etmeyecek.
- Markets gerçek betting transaction yapmayacak; `+` yalnızca CalibraXI virtual simulation Betslip'e gider.

## 13.10 2026-09-22 — CalibraXI Studio Full Product Architecture

Bu turda tek canonical builder sistemi **CalibraXI Studio** full working product architecture seviyesine çıkarıldı:

- `/studio` tek builder/combination destination olarak korundu.
- Local IA sadeleştirildi:
  - DAILY → Cross-Match / Same-Match
  - BUILD → Manual Composition
  - SAVED → Drafts / Templates / Strategy-assisted material
- Selection/Leg, Composition Draft, Published Studio Composition, Simulation Bet ve Saved Template semantic olarak ayrıldı.
- Studio entry points Match Center, Projection Explorer, Markets, Recommendation ve Strategy Lab ile tanımlandı.
- Deep-link/client values analytical truth sayılmayacak; canonical IDs re-resolve edilecek.
- Desktop Studio workspace Selection Library + Composition + Inspector olarak tanımlandı; global Betslip duplicate right rail yaratmayacak.
- Raw stats, streak, Form Edge, Power Rating, odds movement event exact Betting Contract'a resolve edilmeden Studio leg'i olamaz.
- Combination validation sequence:
  - identity;
  - availability/currentness;
  - contract compatibility;
  - contradiction;
  - redundancy;
  - same-fixture grouping;
  - dependency;
  - probability support;
  - price basis;
  - settlement;
  - integrity.
- Same-match component probabilities'in naïf multiplication'ı kesin olarak yasaklandı.
- Same coherence family combination'ları canonical parent distribution'dan legal exact joint derivation ile desteklenebilir.
- Goals + corners/cards/player events gibi cross-family same-match combinations valid joint/dependency model yoksa combined model probability alamaz.
- Player-event combinations dependency-sensitive olarak sınıflandırıldı.
- Exact same-match combined source quote yoksa individual leg odds çarpılıp bookmaker combination price diye gösterilmeyecek.
- Same-match model probability mevcut fakat price yoksa Research-Only composition mümkün; price-dependent EV/ROI/simulation placement yok.
- Cross-match different fixtures otomatik independent sayılmayacak.
- Combined probability support classes working semantics:
  - Exact Joint;
  - Validated Joint/Dependency;
  - Independence-Qualified;
  - Unavailable.
- User-facing coverage:
  - Full Model Coverage;
  - Partial Model Coverage;
  - Price-Only;
  - Research-Only;
  - Unsupported.
- Cross-match price basis:
  - Single Source;
  - Best Observed Per Leg — explicitly Synthetic Simulation.
- Combined price ile combined probability semantic olarak ayrıldı.
- Exact Combination Price ile Synthetic Accumulator Price farklı labels olacak.
- Fair combination value ve EV yalnızca joint probability + settlement + price semantics destekleniyorsa hesaplanacak.
- Composition-level Reliability arbitrary multiplication/score olmayacak; analytical spec açık kaldı.
- Daily Cross-Match / Same-Match arbitrary high-probability/high-edge leg listesi olmayacak; genuine Combination Curation/Recommendation/Publication architecture gerektirecek.
- Manual user composition CalibraXI Recommendation değildir.
- Strategy candidate Recommendation değildir.
- Saved Draft, Saved Template, Published Composition ve Placed Simulation immutable/mutable semantics ayrıldı.
- Saved draft reopen olduğunda quote/Forecast/market changes diff olarak gösterilecek; silently rewritten olmayacak.
- Forecast update `New projection available` şeklinde review gerektirecek; published/placed artifact değişmeyecek.
- Line change exact contract change sayılacak ve auto-replacement yapılmayacak.
- Studio stake yönetmeyecek; Betslip stake + bankroll + final review + virtual placement authority'si olacak.
- Simulation placement exact Forecast/Signal/Recommendation/Market Observation/price/dependency/settlement refs ile immutable snapshot freeze edecek.
- Public Studio Track Record yalnızca explicitly Published Studio Compositions population'ını kullanacak.
- User Manual/Strategy-assisted simulations `/my/performance` population'ında kalacak.
- Builder historical performance publication-time odds/probability/coverage üzerinden immutable kalacak.
- Mobile Studio Daily / Build / Saved düzeni ve filter/analysis sheets tanımlandı.
- Leg count policy, Combination Reliability ve Combination Recommendation matematiği **OPEN analytical specs** olarak bırakıldı.
- Section 10.3 status: **PRODUCT SPEC DEFINED / ANALYTICS REOPENED**.

## 13.11 2026-09-22 — Track Record Full Product Architecture

Bu turda frozen Track Record / Evaluation Architecture korunarak public Track Record product/read surface tam working architecture seviyesine çıkarıldı:

- Canonical routes:
  - `/track-record`
  - `/track-record/forecasts`
  - `/track-record/signals`
  - `/track-record/recommendations`
  - `/track-record/studio`
- Public Track Record ile `/my/performance` kesin olarak ayrıldı.
- Track Record mutable win/loss counter değil; Evaluation Population Specification + Aggregation/Reporting Policy üzerinden immutable evaluations'dan türetilen report projection olarak korunuyor.
- Forecast / Signal / Recommendation / Studio report families aynı metric semantics'e zorlanmıyor.
- Forecast default public scientific view için `Production Analytical — Final Canonical Pre-Match`; publication-qualified Forecast ayrı view.
- Recommendation default population yalnız genuine **publication-qualified Recommendations**.
- Studio default population yalnız genuine **Published Studio Compositions**.
- Signals production vs publication-qualified class açık label ile ayrılacak.
- Publication hiçbir zaman Signal eligibility, API visibility, cache, page display veya user bet'ten infer edilmeyecek.
- Track Record Hub layout: Header → controls → public snapshot → Forecast → Signal → Recommendation → Studio → Coverage & Exclusions → rolling → breakdowns → artifact ledger → methodology.
- Generic `CalibraXI Accuracy = X%` headline yasaklandı.
- Forecast report proper scores + calibration + coverage odaklı; hit rate secondary declared discrete view.
- Forecast Quality, robustness ve coverage tek composite score'a sıkıştırılmayacak.
- Final Canonical Pre-Match one-run-per-fixture population default Forecast production view olarak seçildi; all-runs ayrı population.
- Horizon performance (T-24h/T-6h/T-1h/final) explicit information regimes olarak tasarlandı; exact bins analytical policy'ye açık.
- Capability Release comparisons paired/common populations gerektirir; different-population raw averages winner claim üretmez.
- Signal Track Record eligibility, discrimination ve support/coverage sorularını ayrı tutar.
- CANNOT_EVALUATE loss sayılmaz.
- Every Signal/Recommendation/Studio performance report exact price basis taşır.
- CLV yalnız exact same contract/line ve governed Closing Price Policy ile retrospective metric olabilir.
- Recommendation history historical Signals'tan backfill edilmeyecek.
- Daily Pick history yalnız genuine publication subtype varsa oluşacak.
- Studio Track Record yalnız Published Studio Compositions population'ını kullanacak; manual user builds public record'a girmez.
- Unit-stake public reporting user stake/bankroll'dan ayrıldı.
- Complex settlement push/void/half win/half loss/dead heat semantics korunacak.
- Coverage & Exclusions panel denominator hiding'i engellemek için mandatory product concept oldu.
- Population Inspector ve Metric Definition drawer tanımlandı.
- Headline metrics sample `N` olmadan gösterilmeyecek; applicable olduğunda Effective N da gösterilecek.
- Dependence-aware uncertainty / small-sample context eklendi.
- Rolling 7D/30D/90D/YTD/Season/All-Time views tanımlandı.
- Probability, Reliability, odds ve edge buckets evaluation views olarak tanımlandı; Recommendation threshold değiller.
- Performance aggregate filters yalnız ex-ante dimensions üzerinden yapılacak; outcome-conditioned `Winners Only → ROI` pseudo-reports yasaklandı.
- Every aggregate report atomic historical artifact ledger'a drill-down edebilecek.
- Artifact → Match Center Historical Snapshot bidirectional audit flow tanımlandı.
- `Why Included?` / exclusion reason inspection eklendi.
- Outcome corrections old report'u mutate etmeyecek; new Evaluation/Track Record Projection version oluşacak ve previous report queryable kalacak.
- Report identity as-of, watermark, population version ve reporting policy version taşıyacak.
- Pending/unresolved/integrity/quarantine counts görünür olacak; winning/losing data seçiminde cherry-picking yapılamayacak.
- Production, Shadow/Challenger, Synthetic PIT, Corrected-Data Replay ve offline candidate populations default public headline'da karışmayacak.
- Backtest ve Track Record conceptual/product boundary açıkça donduruldu.
- Model release timeline historical production artifacts'ı current modelle re-score etmeyecek.
- Public share/export future direction population/report version context'ini koruyacak.
- Section 10.13 status: **Public Track Record Product Surface — PRODUCT SPEC DEFINED**.

## 13.12 2026-09-22 — My CalibraXI / Watchlist / Alerts / Personal Terminal Full Architecture

Bu turda My CalibraXI full working product architecture seviyesine çıkarıldı:

- `/my` canonical personal terminal route olarak **LOCKED WORKING**; `/dashboard` canonical değil.
- Canonical routes:
  - `/my`
  - `/my/watchlist`
  - `/my/alerts`
  - `/my/bets`
  - `/my/strategies`
  - `/my/saved`
  - `/my/performance`
  - `/my/settings`
- User-facing `/my/bets` label'ı `Simulations` olarak tercih edildi; gerçek para hesabı algısı azaltıldı.
- Watchlist, Alert Rule ve Notification semantic olarak ayrıldı.
- Watchable object classes: Fixture, Team, Player, Competition, Projection, exact Market Selection, Signal/Recommendation context, Power subject, Saved View, Strategy, Studio Template.
- Watchlist stable canonical identities'e bağlanacak; page URL bookmark sistemi olmayacak.
- Watchlist entity groups, quick actions ve optional user collections tanımlandı.
- Alert trigger families Fixture, Projection, Market, Player, Power ve Strategy olarak detaylandırıldı.
- Alert Rule subject/trigger/threshold/scope/channel/frequency/cooldown/quiet-hour semantics tanımlandı.
- Hysteresis/debounce/cooldown/deduplication ile threshold jitter spam prevention requirement oldu.
- Alert trigger delivery öncesinde currentness yeniden doğrulanacak; stale/historical state yeni alert gibi gönderilmeyecek.
- Notification event exact trigger reason/value before-after/timestamp/artifact/deep-link context'i taşıyacak.
- Header Notification Center + `/my/alerts` Inbox/Rules/Muted-History yapısı tanımlandı.
- Launch notification channel önerisi **in-app first**; email/push future-compatible.
- Watch default olarak bütün alerts'i otomatik açmayacak; user opt-in modeli tercih edildi.
- Quiet hours ve future digest delivery policy olarak tanımlandı.
- My Overview public homepage'in kopyası olmayacak; personal `Needs Your Attention` queue ile başlayacak.
- Recommended My Overview order:
  - attention queue;
  - watchlist next-up;
  - open simulations + bankroll;
  - Strategy Lab;
  - Saved Research;
  - alerts;
  - recent activity/viewed;
  - personal performance.
- Virtual Bankroll gerçek para değil; launch display unit olarak `units` preferred.
- Historical bankroll değişimleri ledger-event üzerinden reconstructable olacak.
- Starting bankroll reset old history'yi silently rewrite etmeyecek; new ledger/archive modeline future compatibility bırakıldı.
- `/my/bets` Open / Settled / All simulation ledger olarak tanımlandı.
- Simulation detail immutable placement odds/contracts/refs/bankroll before-after/settlement provenance gösterecek.
- Current market/projection context placed simulation'ı mutate etmeyecek.
- Virtual cashout launch out-of-scope.
- Favorite Markets yalnız UI preference; Forecast/Recommendation input'u değil.
- `/my/saved` Projection views, Market views, Studio drafts/templates, comparisons/collections için unified research library olarak tanımlandı.
- Strategy definitions `/my/strategies` altında kalacak.
- Strategy Lab states, human-readable Rule Builder, condition classes ve PIT backtestability semantics genişletildi.
- Historical PIT evidence olmayan Strategy condition geçmişe today's data ile uygulanmayacak; not-backtestable / limited coverage explicit olacak.
- Backtest Opportunity ile Executed Simulation ayrı tutulacak.
- Historical Backtest ile Forward Test side-by-side fakat ayrı populations olacak.
- Strategy edits new version oluşturacak; existing historical/forward results relabel edilmeyecek.
- Strategy Candidate Inbox ve candidate expiry semantics tanımlandı.
- Strategy automation flow candidate → alert → optional Studio draft → user review → Betslip → explicit simulation; real auto-betting yok.
- `/my/performance` personal simulation analytics olarak tanımlandı ve public `/track-record` authority'sinden kesin ayrıldı.
- Personal performance actual virtual-stake view + optional normalized unit-stake view destekleyebilir.
- Module pin/hide/reorder ve account-scoped layout persistence tanımlandı.
- New-user first-login onboarding and empty states tanımlandı.
- `/my/settings` Account/Display/Notifications/Simulation/Privacy groups ile tanımlandı.
- Personal state private-by-default.
- Future `/u/{handle}` public profile/social direction desteklenebilir; current implementation requirement değil.
- Future shared views/strategies/performance explicit visibility + version/as-of taşımalı.
- User-owned state vs canonical product-owned analytical truth boundary canonical hale getirildi.
- User preferences/order/favorites Forecast, Reliability, Signal, Recommendation, Power Rating veya Track Record'ı değiştiremez.
- Simulation settlement corrections old ledger history'yi silently overwrite etmeyecek; explicit correction/adjustment event semantics kullanılacak.
- Personal ROI/win rate self-selected descriptive user results; scientific/public CalibraXI validation değildir.
- Responsible simulation copy: `Simulation`, `Virtual Bankroll`, `Units`, `Place Simulation`; deposit/withdraw/casino framing yok.
- Section 10.14 status: **My CalibraXI Personal Workspace — PRODUCT SPEC DEFINED**.

## 13.13 2026-09-22 — Source Acquisition / Scraper Platform Decision — MOVED / CONSOLIDATED

Detailed engineering specification: **MOVED / CONSOLIDATED** into `docs/CalibraXI-Engineering.md`. The product-level boundary remains in §10.15; this Decision Log preserves the original decision and its history.

- CalibraXI tek provider veya tek scraper library'ye bağımlı olmayacak.
- **SoccerData approved adapter/accelerator**, canonical ingestion authority değil.
- Preferred stack: Python 3.12+, Scrapy, direct HTTP/XHR/JSON, Playwright fallback, Parsel/lxml, Redis, PostgreSQL, S3-compatible storage / MinIO local.
- Acquisition preference: permitted official/licensed machine-readable source → direct JSON/HTTP → deterministic HTML → browser fallback.
- `Scraped Data != Canonical Truth` invariant'i donduruldu.
- Raw Source Snapshot / Observation katmanı mandatory.
- Source Adapter + Source Capability Registry architecture tanımlandı.
- SoccerData DataFrame schema canonical domain contract olmayacak; SoccerData cache canonical provenance store olmayacak.
- Critical capabilities gerektiğinde native CalibraXI adapters'a graduate edebilecek.
- Entity Resolution Competition/Season/Fixture/Team/Player/Manager/Venue/Referee ve relevant source identities için mandatory.
- Stable source IDs korunacak; string name normalization tek başına identity authority olmayacak.
- Field/capability-level source authority desteklenecek.
- Source disagreement latest-write-wins ile çözülmeyecek.
- Valid/source-availability/knowledge/processing time distinctions ingestion'a uygulanacak.
- Backfill/current/near-kickoff/live/post-match/repair/asset jobs ayrıldı.
- Incremental/event-aware polling kullanılacak; brute-force global rescrape yok.
- Source-specific rate/backoff/circuit breaker davranışı mandatory.
- Source Health + schema-drift detection operational architecture'a eklendi.
- Parser failure canonical zero/empty data olarak yorumlanmayacak.
- Missing / zero / unsupported / source failure ayrı states.
- Fallback provenance kaybetmeyecek.
- Asset ingestion ayrı pipeline olacak; hash/dedupe/storage/derivatives/canonical mapping + usage/license metadata tutulacak.
- Technical scrapeability commercial usage right anlamına gelmez.
- Fake/generated team crest/player face/competition logo yasağı korunuyor.
- PostgreSQL canonical structured state; object storage raw payload/assets; Redis coordination/cache rolünde.
- Production extraction deterministic/versioned; LLM extraction canonical parser olmayacak.
- Model code SoccerData/source clients'i doğrudan çağırmayacak.
- Initial implementation sequence A0–A10 tanımlandı.
- Section 10.15 status: **LOCKED WORKING ARCHITECTURE**.

## 13.14 2026-09-22 — Recommendation + Curation Architecture

- Recommendation and Curation are separate immutable decision layers. A Signal being `ELIGIBLE`, a Forecast being highly probable, a Reliability band, a Top Projection rank, an Explorer sort, API visibility, a cache entry, a page render, or a user simulation never creates a Recommendation.
- Recommendation decisions use an immutable Candidate Population Manifest, exact target identity, objective/context, versioned Recommendation Policy, hard/selection gates, positive reason codes, non-recommend reason codes, currentness evidence, supersession links, and explicit publication/withdrawal facts.
- A policy may withhold a Single Selection or Daily Pick. It is never required to publish a pick to fill a widget or date.
- Today's Top Projection and Top 10 are governed Curation outputs. They are not Daily Picks, Best Bets, or hidden Recommendations. Probability/edge/odds sorting remains research ordering and cannot enter Recommendation or Track Record populations.
- Daily Cross-Match and Daily Same-Match Studio outputs require separate candidate population and Curation/Recommendation decisions, exact contract/price/settlement lineage, currentness, duplicate/concentration/diversity controls, and explicit publication. Different fixtures do not prove independence; same-match marginal multiplication is prohibited.
- Target-family combination mathematics (joint derivation, dependence, calibration, combination Reliability/support, and effective-sample evaluation) remains open until separately validated and versioned. Unsupported or withheld states are explicit; manual Studio builds and strategy candidates remain user-owned and are not public Recommendations.
- Public Recommendation Track Record includes only genuinely published Recommendation artifacts; Daily Pick is a genuine Recommendation subtype; public Studio Track Record includes only Published Studio Compositions. Withdrawals do not erase publication or evaluation history, and old Forecasts/Signals/rankings/user bets are never retrospectively backfilled as Recommendations.
- The canonical analytical governance is recorded in `docs/CalibraXI-Analytics-Architecture.md`; this product document retains the product-facing behavior and decision history.

## 13.15 2026-09-25 - Data Bootstrap and Forecasting Foundation

- The first governed EPL vertical slice is populated from the production acquisition path. The measured archive contains 33 seasons (`1993/94` through `2025/26`), 12,704 completed fixtures, and 51 canonical teams.
- Coverage is reported by source and capability. The bootstrap preserves 697 quarantined rows and 9,120 historical odds observations whose publication chronology is unknown; those odds are not pre-match features for an earlier cutoff.
- Forecast outputs are consumed through immutable, versioned Feature Snapshots and Prediction Runs. A historical view is always an as-known-at-time artifact with cutoff, knowledge time, feature schema, model, calibration, and evidence lineage.
- Forecast Probability, Reliability, Signal, Recommendation, and Curation remain separate product concepts. This phase establishes forecasting only; it does not publish Recommendations, Signals, portfolios, or betting decisions.
- Historical Football-Data rows remain canonical evidence but are withheld from production PIT training until source availability chronology is proven. Synthetic PIT backtests are labeled synthetic-only and cannot establish production model performance.

### 13.16 2026-09-25 - EPL 2025/26 ESPN reconciliation

- The production acquisition path collected 114 known EPL 2025/26 match dates and retained 380 ESPN fixtures plus 20 teams in raw evidence.
- Explicit provider-to-canonical aliases confirmed 380/380 ESPN fixture mappings; unresolved and ambiguous populations are both zero. Reconciliation retains 158 one-hour kickoff schedule revisions as evidence.
- ESPN retrieval knowledge time is preserved, but provider publication/availability chronology is unknown. The enriched rows remain outside historical production PIT training until that chronology is proven.

---

## Sonraki notlar için kural

Kullanıcı bundan sonra fikirleri sırasız, yarım cümlelerle veya karalama şeklinde anlatabilir. Editoryal normalizasyon CalibraXI dokümanında yapılır; **ürün anlamı ve hiçbir gereksinim kaybedilmez**. Çelişki varsa sessiz karar verilmez: mevcut canonical karar ile yeni kararın ilişkisi `PRESERVED`, `EXTENDED`, `SUPERSEDED`, `REOPENED` veya `OPEN` olarak kayıt altına alınır.
