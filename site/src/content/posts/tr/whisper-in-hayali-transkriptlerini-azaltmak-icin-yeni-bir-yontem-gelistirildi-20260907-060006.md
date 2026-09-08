---
title: "Whisper'ın Hayali Transkriptlerini Azaltmak için Yeni Bir Yöntem Geliştirildi"
pubDate: 2026-09-07T06:00:06.805Z
kategori: "Yapay Zeka"
tags:
  - sesli-tanima
  - whisper
  - halusinasyon
  - llm-hata
tagLabels:
  sesli-tanima:
    tr: "Sesli Tanıma"
    en: "Speech Recognition"
  whisper:
    tr: "Whisper"
    en: "Whisper"
  halusinasyon:
    tr: "Hallüsinasyon"
    en: "Hallucination"
  llm-hata:
    tr: "Model Hataları"
    en: "Model Errors"
description: "Araştırmacılar, OpenAI'nin Whisper modelinin sessiz girdilerde oluşturduğu sahte transkriptleri azaltmak için eğitim gerektirmeyen bir projeksiyon yön"
kaynak: "https://arxiv.org/abs/2609.04561"
coverImage: "https://images.unsplash.com/photo-1675557009875-436f71457475?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8MTB8fG9wZW5haSUyMGFydGlmaWNpYWwlMjBpbnRlbGxpZ2VuY2V8ZW58MHwwfHx8MTc4ODY3Mzg0Mnww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Jonathan Kemper"
gorselFotografciLink: "https://unsplash.com/@jupp?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "openai artificial intelligence"
---
OpenAI'nin Whisper modeli otomatik konuşma tanıması (ASR) görevlerinde yaygın olarak kullanılıyor ancak bir sorunu var: sessiz veya az ses içeren girdilerde, model ikna edici fakat tamamen hayali transkriptler üretebiliyor. Bu problem özellikle gerçek dünya uygulamalarında ciddi yanlışlara yol açabiliyor.

Yeni bir araştırma, bu "hallüsinasyon" sorununun çözümü için **eğitim gerektirmeyen, çıkarım zamanında** uygulanabilen bir yöntem sunuyor:

- Düşük dereceli projeksiyon tekniği kullanarak decoder aktivasyonlarını manipüle etme
- Sessiz ses olmayan veri ile hallüsinasyonun yer aldığı altuzayı tanımlama
- Eğitim için ek veriye ihtiyaç duymayan, pratik bir çözüm
- Whisper'ın mevcut mimarisini değiştirmeden entegre edilebilir bir yaklaşım
- Çalışmada arXiv'de yayınlanan tam araştırma metodu ve bulgular yer almakta

Bu yöntem, hallüsinasyon ile ilişkili aktivasyonları tanımlayarak decoder'ın gizli durumlarını belirli bir matematik altuzayında "temizliyor". Böylece model sessiz seçişlerde boş konuşma üretmek yerine daha güvenilir davranabiliyor. Önerilen teknik kalibrasyon verisi olarak sadece konuşmasız örneklere ihtiyaç duyuyor, bu da uygulamayı ekonomik hale getiriyor.

Whisper gibi büyük dil modelleri için hallüsinasyon azaltma giderek önemli bir araştırma alanı haline geliyor. Bu çalışma, eğitim-gerektirmeyen çözümlerin model davranışını nasıl iyileştirebileceğini gösteriyor.