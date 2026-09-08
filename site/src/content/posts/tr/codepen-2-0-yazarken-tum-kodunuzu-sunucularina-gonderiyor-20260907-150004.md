---
title: "CodePen 2.0 Yazarken Tüm Kodunuzu Sunucularına Gönderiyor"
pubDate: 2026-09-07T15:00:04.500Z
kategori: "Güvenlik"
tags:
  - veri-guvenlig
  - web-gelistirme
  - gizlilik-riski
  - bulut-platform
tagLabels:
  veri-guvenlig:
    tr: "Veri Güvenliği"
    en: "Data Security"
  web-gelistirme:
    tr: "Web Geliştirme"
    en: "Web Development"
  gizlilik-riski:
    tr: "Gizlilik Riski"
    en: "Privacy Risk"
  bulut-platform:
    tr: "Bulut Platform"
    en: "Cloud Platform"
description: "CodePen'in yeni sürümü, kaydedilmeden önce yazdığınız her şeyi neredeyse anında sunucularına iletiyormuş. Hassas verileriniz riskte olabilir."
kaynak: "https://news.ycombinator.com/item?id=49596976"
coverImage: "https://images.unsplash.com/photo-1614064642639-e398cf05badb?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8OXx8Y3liZXJzZWN1cml0eSUyMGRpZ2l0YWwlMjBzZWN1cml0eXxlbnwwfDB8fHwxNzg4NzkyNjUxfDA&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "FlyD"
gorselFotografciLink: "https://unsplash.com/@flyd2069?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "cybersecurity digital security"
---
CodePen 2.0, web geliştirme topluluğunda ciddi bir gizlilik endişesi yaratmaya başladı. Hacker News üzerinde paylaşılan bulgulara göre, platform yazdığınız kodun tamamını, kaydedilmeden hatta tamamlanmadan **neredeyse anında** sunucularına gönderiyor.

Bir araştırmacı bu durumu test ederek sorunu somut verilerle ortaya koydu:

- Editöre yazılan her karakter 1-2 saniye içinde codepen.dev sunucularına aktarılıyor
- Tarayıcı geliştirici araçlarının Network sekmesinde bu veri transferleri net şekilde görülüyor
- Kaydedilmemiş kodlar dahi oluşturulan preview'de render ediliyor
- Benzersiz bir işaretçi ile test yapıldığında, işaretçi kaydedilmeden önce bile preview HTML'inde yer aldığı tespit edildi

Bu davranış, **hızlı otomatik kaydetme** amacıyla tasarlanmış olabilir. Ancak sorun şu: eğer yanlışlıkla API anahtarları, veritabanı şifreleri veya diğer hassas bilgiler editöre yapıştırdıysanız, bunlar silinmeden çok önce CodePen'in sunucularında kaydedilmiş olacak.

Güvenlik bilincine sahip geliştiriciler, CodePen 2.0 kullanırken düşünce editörü olarak bir API anahtarı veya gizli bilgisi yazmaması gerektiğini artık biliyorlar. Platform bu davranışı belgelendirmeli ve kullanıcılarına açık şekilde bildirmelidir.