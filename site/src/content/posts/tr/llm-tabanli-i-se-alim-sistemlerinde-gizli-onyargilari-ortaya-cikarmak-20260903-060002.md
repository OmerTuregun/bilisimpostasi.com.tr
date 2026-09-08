---
title: "LLM Tabanlı İşe Alım Sistemlerinde Gizli Önyargıları Ortaya Çıkarmak"
pubDate: 2026-09-03T06:00:02.767Z
kategori: "Yapay Zeka"
tags:
  - llm-fairness
  - multi-agent
  - insan-kaynaklari-ai
  - audit
tagLabels:
  llm-fairness:
    tr: "LLM Adilliği"
    en: "LLM Fairness"
  multi-agent:
    tr: "Çok Ajanlı Sistemler"
    en: "Multi-Agent Systems"
  insan-kaynaklari-ai:
    tr: "İK Yapay Zekası"
    en: "HR AI"
  audit:
    tr: "Denetim"
    en: "Audit"
description: "Araştırmacılar, yapay zeka destekli işe alım kararlarındaki adil olmayan davranışları tespit etmek için süreç odaklı bir tanılama yöntemi geliştirdi."
kaynak: "https://arxiv.org/abs/2609.02092"
coverImage: "https://images.unsplash.com/photo-1662946834868-4e50ea542a48?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8MTR8fGFwcGxlJTIwdGVjaG5vbG9neSUyMHByb2R1Y3R8ZW58MHwwfHx8MTc4ODMyODI1N3ww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "BoliviaInteligente"
gorselFotografciLink: "https://unsplash.com/@boliviainteligente?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "apple technology product"
---
Büyük dil modelleri (LLM) tabanlı çok ajanlı sistemler, işe alım gibi kritik karar vermede giderek daha fazla kullanılıyor. Ancak sadece nihai sonuçları incelemek, sistemin karar verme sürecinde nerede hata yaptığını anlamaya yetmiyor. Yeni araştırma, bu boşluğu doldurmak için **SCOPED-Hiring** adında bir çözüm sunuyor.

SCOPED-Hiring, LLM tabanlı işe alım sistemlerindeki gizli önyargıları ortaya çıkarmak için tasarlanmış bir tanılama aracı:

- Kontrollü ve değiştirilmiş özgeçmiş versiyonları oluşturup sistem tarafından değerlendirilmesini sağlıyor
- Rol tabanlı işe alım komiteleri simülasyonu yaparak gerçekçi karar ortamları oluşturuyor
- 311.000'den fazla yapılandırılmış karar yolculuğu kaydederek detaylı veri toplayıyor
- Karar trajektorylerini analiz edilebilir formata dönüştürerek hangi adımda önyargı oluştuğunu gösteriyor

Bu yaklaşım, geleneksel "çıktı bazlı" adillik denetiminden önemli ölçüde farklılaşıyor. Sonuç olarak adil görünen bir sistem, aslında karar verme sürecinin çeşitli aşamalarında sistematik ayrımcılık yapıyor olabilir. SCOPED-Hiring, bu gizli davranışları ortaya çıkararak, geliştiricilere müdahale etme imkanı sağlıyor.

Araştırma, yüksek riskli alanlarda yapay zeka kullanımının güvenliğini artırmada önemli bir adım temsil ediyor. İşe alım sistemlerinin şeffaflığı ve adilliği, hem adaylar hem de işverenler açısından kritik önem taşıyor.