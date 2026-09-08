---
title: "MikroTik RouterOS 7.23.4'teki Sessiz Yamayı Reverse Engineer'lar Ortaya Çıkardı"
pubDate: 2026-09-05T06:00:05.581Z
kategori: "Güvenlik"
tags:
  - guvenlik
  - reverse-engineering
  - ruteros
  - yazilim-guncelleme
tagLabels:
  guvenlik:
    tr: "Ağ Güvenliği"
    en: "Network Security"
  reverse-engineering:
    tr: "Ters Mühendislik"
    en: "Reverse Engineering"
  ruteros:
    tr: "RouterOS"
    en: "RouterOS"
  yazilim-guncelleme:
    tr: "Yazılım Güncellemesi"
    en: "Software Update"
description: "Güvenlik araştırmacıları, MikroTik'in açıklamadan yayınladığı RouterOS güncellemesindeki gizli düzeltişi tersine mühendislik yöntemiyle analiz etti."
kaynak: "https://npratley.net/reversing-mikrotiks-silent-patch-the-routeros-7-23-4-fix-they-wouldnt-explain/"
coverImage: "https://images.unsplash.com/photo-1579693409321-1be2df1ab130?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8N3x8YXBwbGUlMjB0ZWNobm9sb2d5JTIwcHJvZHVjdHxlbnwwfDB8fHwxNzg4NTAxMDU3fDA&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Zhiyue"
gorselFotografciLink: "https://unsplash.com/@zhiyue?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "apple technology product"
---
MikroTik, ağ yöneticilerinin yaygın şekilde kullandığı RouterOS işletim sisteminin 7.23.4 sürümünü sessizce yayınladı, ancak yapılan değişiklikleri hiç açıklamadı. Bu gizemli güncelleme, bağımsız güvenlik araştırmacılarını yamaya dair bilgi toplamaya yöneltti.

Araştırmacılar aşağıdaki noktaları ortaya koydular:

- MikroTik, güvenlik açığına ilişkin resmi açıklama yayınlamadığı halde kritik bir düzeltme içeren güncelleme sundu
- Tersine mühendislik analizi, yapılan değişikliklerin ağ iletişim protokolüne yönelik olduğunu gösterdi
- Açıklamanın yokluğu, kullanıcıların güncellemelerin aciliyetini anlamasını güçleştirdi
- Sektördeki şirketler genellikle güvenlik yamalarını şeffaf şekilde açıklar ve CVE tanımlayıcıları paylaşırlar

Bu tür sessiz yamalar, bilgi güvenliği topluluğunda tartışmalı kabul edilir. Açık iletişim, yöneticilerin sistemi proaktif olarak güncelleme kararı alabilmesini sağlarken, belirsizlik riski artırır.

MikroTik'in bu yaklaşımı, yazılım güvenliğinde şeffaflığın ne kadar önemli olduğunu ve üreticilerin yamanın nedenini açıklamayı neden bir en iyi uygulama olarak benimsemeleri gerektiğini vurgular. Güvenlik açığının tam niteliğini anlamak, ağ yöneticilerinin riskini doğru değerlendirmesi için kritik öneme sahiptir.