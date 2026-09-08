---
title: "Moadim.io: Açık Kaynak Agent Scheduler Çözümü Geliyor"
pubDate: 2026-09-05T06:00:04.581Z
kategori: "Teknoloji"
tags:
  - agent-scheduler
  - rust
  - acik-kaynak
  - devops
tagLabels:
  agent-scheduler:
    tr: "Agent Scheduler"
    en: "Agent Scheduler"
  rust:
    tr: "Rust"
    en: "Rust"
  acik-kaynak:
    tr: "Açık Kaynak"
    en: "Open Source"
  devops:
    tr: "DevOps"
    en: "DevOps"
description: "Rust tabanlı yerel daemon, Git entegrasyonu ve agent-agnostik tasarımla tüm sistemlerde çalışan scheduler aracı"
kaynak: "https://moadim.io/"
coverImage: "https://images.unsplash.com/photo-1496065187959-7f07b8353c55?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8M3x8dGVjaG5vbG9neSUyMGlubm92YXRpb258ZW58MHwwfHx8MTc4ODUyMjY3Mnww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Ramón Salinero"
gorselFotografciLink: "https://unsplash.com/@donramxn?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "technology innovation"
---
Yazılım geliştirme dünyasında otomasyonun sınırlarını genişleten yeni bir araç ortaya çıktı. Moadim.io, agent tabanlı sistemlerde rutin görevleri yönetmek için tasarlanan açık kaynak bir scheduler'dır. Özellikle karmaşık altyapılarda zamanlanmış işleri merkezi bir noktadan kontrol etmeyi zorlaştıran sorunlara çözüm sunuyor.

Bu proje, birçok mevcut scheduler'ın eksikliklerini giderecek şekilde inşa edildi:

- **Rust tabanlı yerel daemon** olarak kurulum yapılan araç, hedef makineye kurulup bir isim verilerek hemen kullanıma hazır hale geliyor
- Git repository üzerinden rutin yönetimi sağlıyor; yeni bir görev eklemek için pull request açıp merge etmek yeterli
- Agent-agnostik mimari, herhangi bir AI agent türü ile uyumlu çalışıyor ve özel lock-in olmadan entegrasyon imkanı veriyor
- MCP, UI ve HTTP protokolleri dahil farklı iletişim yöntemlerini destekliyor
- İşletim sistemine ve sistem mimarisine bağlı olmadan tüm platformlarda çalışabiliyor

Moadim.io'nun en ilginç yönü, Git workflow'unun doğal bir şekilde otomasyon yönetimine entegre edilmesidir. Geliştirme takımları, kod değişiklikleriyle aynı disiplini zamanlanmış görevlere uygulayabiliyor. Sınırsız sayıda routine ve cron görevini destekleyen sistem, makine özelinde çalışan dağıtılmış yapılara ideal bir çözüm sunuyor.

Açık kaynak olarak inşa edilen bu proje, topluluk katkılarına ve farklı kullanım senaryolarına uyarlanabilir bir temel sağlıyor.