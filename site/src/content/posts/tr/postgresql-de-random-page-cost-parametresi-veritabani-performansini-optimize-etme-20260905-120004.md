---
title: "PostgreSQL'de random_page_cost Parametresi: Veritabanı Performansını Optimize Etme"
pubDate: 2026-09-05T12:00:04.452Z
kategori: "Teknoloji"
tags:
  - postgresql
  - veritabani
  - performans
  - query-planlama
tagLabels:
  postgresql:
    tr: "PostgreSQL"
    en: "PostgreSQL"
  veritabani:
    tr: "Veri Tabanı"
    en: "Database"
  performans:
    tr: "Performans"
    en: "Performance"
  query-planlama:
    tr: "Query Planlama"
    en: "Query Planning"
description: "Veri tabanı yöneticileri için random_page_cost ayarının query planlayıcısı performansına etkisi ve optimizasyon stratejileri"
kaynak: "https://vondra.me/posts/some-more-thoughts-on-random_page_cost/"
coverImage: "https://images.unsplash.com/photo-1606206873764-fd15e242df52?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8N3x8dGVjaG5vbG9neSUyMGlubm92YXRpb258ZW58MHwwfHx8MTc4ODUyMjY3Mnww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Testalize.me"
gorselFotografciLink: "https://unsplash.com/@testalizeme?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "technology innovation"
---
PostgreSQL'in query planlayıcısı, en verimli sorgu yürütme yolunu belirlerken birçok parametreyi dikkate alır. Bu parametrelerden biri olan **random_page_cost**, disk erişim maliyetlerini tahmin etmekte kritik rol oynayan bir ayardır. Doğru yapılandırılmadığında, veritabanı sisteminizin performansı önemli ölçüde düşebilir.

random_page_cost parametresi aşağıdaki yönleri etkiler:

- **Query planlayıcısı kararları**: Dizin taraması ile tam tablo taraması arasında seçim yaparken kullanılan maliyet hesaplaması
- **Disk I/O tahmini**: Rastgele disk erişiminin sıralı erişime kıyasla ne kadar pahalı olduğunu tanımlar
- **Varsayılan değer**: Geleneksel olarak 4.0 olarak ayarlanmıştır, ancak modern SSD'ler için daha düşük değerler gerekebilir
- **Sistem mimarisi**: Fiziksel sunucu ve bulut altyapısı arasında farklılaşan optimal değerler

Bu parametreyi ayarlarken, sistem üzerinde gerçekçi testler yaparak en uygun değeri bulmak önemlidir. SSD tabanlı sistemlerde 1.0 ile 2.0 arasında bir değer, HDD sistemlerde ise 4.0 ile 5.0 arasında bir değer daha iyi sonuç verebilir. Yöneticiler, workload özelliklerine göre ve sorgu performans metriklerini izleyerek bu ayarı dinamik olarak optimize edebilirler.

Sonuç olarak, **random_page_cost** sadece bir ayar değil, veritabanı performansını şekillendiren stratejik bir araçtır. Doğru konfigürasyon, sorgu hızlarını dramatik biçimde artırabilir ve sistem kaynaklarını daha verimli kullanılmasını sağlayabilir.