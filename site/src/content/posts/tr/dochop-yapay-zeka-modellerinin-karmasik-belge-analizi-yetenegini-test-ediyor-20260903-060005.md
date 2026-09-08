---
title: "DocHop: Yapay Zeka Modellerinin Karmaşık Belge Analizi Yeteneğini Test Ediyor"
pubDate: 2026-09-03T06:00:05.767Z
kategori: "Yapay Zeka"
tags:
  - mllm
  - belge-analizi
  - benchmark
tagLabels:
  mllm:
    tr: "Çok Modaliteli Dil Modelleri"
    en: "Multimodal LLMs"
  belge-analizi:
    tr: "Belge Analizi"
    en: "Document Analysis"
  benchmark:
    tr: "Benchmark"
    en: "Benchmark"
description: "Yeni bir benchmark, çok modaliteli dil modellerinin metin ve görselleri birlikte kullanarak karmaşık mantıksal çıkarımlar yapabilme becerisini ölçüyor"
kaynak: "https://arxiv.org/abs/2609.02059"
coverImage: "https://images.unsplash.com/photo-1677442135131-4d7c123aef1c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8MTd8fGFydGlmaWNpYWwlMjBpbnRlbGxpZ2VuY2UlMjB0ZWNobm9sb2d5fGVufDB8MHx8fDE3ODgzMjgyNTZ8MA&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Steve A Johnson"
gorselFotografciLink: "https://unsplash.com/@steve_j?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "artificial intelligence technology"
---
Çok modaliteli büyük dil modelleri (MLLM) grafik ve belge sorgulaması gibi yapılandırılmış görsel görevlerde başarılı sonuçlar vermiştir. Ancak mevcut değerlendirme sistemleri bu alanları birbirinden izole olarak test etmekte, önemli bir kapabiliteyi göz ardı etmektedir: modellerin metin bağlamını kullanarak grafik kanıtlarını nasıl seçmesi, yorumlaması ve birleştirmesi gerektiğini belirleyebilme yeteneği.

DocHop adlı yeni benchmark, tam olarak bu boşluğu doldurmayı hedefliyor:

- **Entegre yapı**: Belge metni içindeki bilgilerle grafikleri kombinasyonda anlamlandırmayı gerektiriyor
- **Çok adımlı mantık**: Tek bir soruya cevap vermek için birden fazla bilgi kaynağından veri toplayıp işlemeyi zorunlu kılıyor
- **Alan dışı başarı**: Modellerin tamamen yeni, daha önce görmediği belge türlerine nasıl uyum sağladığını değerlendiriyor
- **Gerçekçi senaryolar**: Bilgi yoğun belgelerden oluşan veri setinde modellerin pratik performansını ortaya çıkarıyor

Bu benchmark, yapay zeka araştırmacılarının MLLM'lerin gerçek dünya uygulamalarındaki sınırlamalarını daha iyi anlamasını sağlayacak. Şu ana kadar benzer araştırmalar, metin ve görselleri ayrı ayrı değerlendirirken, DocHop'un temel katkısı bunları bütünleşik bir çerçevede test etmesidir. Sonuç olarak bu çalışma, gelecek nesil dil modellerinin daha karmaşık bilgi işleme görevleri için nasıl geliştirilebileceğine dair yeni perspektifler sunar.