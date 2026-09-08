---
title: "Omarchy: Herhangi Bir Kullanıcı Sürecinden Root Yetkilendirmesine Yükseltme Açığı"
pubDate: 2026-08-30T18:00:00.385Z
kategori: "Güvenlik"
description: "Güvenlik araştırması, Linux sistemlerinde herhangi bir kullanıcı sürecinin root haklarına yükseltilebildiğini gösteren kritik bir açığı ortaya koymakt"
kaynak: "https://0xcc.io/posts/omarchy-root-creds/"
tags:
  - linux-guvenligi
  - privilege-escalation
  - root-acigi
  - sistem-guvenligi
tagLabels:
  linux-guvenligi:
    tr: "Linux Güvenliği"
    en: "Linux Security"
  privilege-escalation:
    tr: "Yetki Yükseltme"
    en: "Privilege Escalation"
  root-acigi:
    tr: "Root Açığı"
    en: "Root Vulnerability"
  sistem-guvenligi:
    tr: "Sistem Güvenliği"
    en: "System Security"
coverImage: "https://images.unsplash.com/photo-1768839721176-2fa91fdce725?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8MTJ8fGN5YmVyc2VjdXJpdHklMjBkaWdpdGFsJTIwc2VjdXJpdHl8ZW58MHwwfHx8MTc4ODEwMTQzN3ww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Sasun Bughdaryan"
gorselFotografciLink: "https://unsplash.com/@sasun1990?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "cybersecurity digital security"
---
Omarchy adı verilen bu güvenlik açığı, Linux işletim sistemlerinde **privilege escalation** (yetki yükseltme) açısından ciddi bir tehdit oluşturmaktadır. Araştırmacılar tarafından keşfedilen bu zafiyet, standart kullanıcı haklarıyla çalışan herhangi bir işlemin sistem root seviyesine yükseltilebilmesine olanak tanıyor.

Açığın temel özellikleri şöyle sıralanabilir:

- Herhangi bir kullanıcı süreci tarafından exploite edilebilmesi
- Root (sistem yöneticisi) yetkilerine direkt erişim sağlama
- Linux sistemlerinin temel güvenlik mekanizmalarını bypass edebilme
- Potansiyel olarak sistem bütünlüğünü tehlikeye atabilme

Bu tür privilege escalation açıkları, sistem güvenliğinin en kritik zafiyetleri arasında yer almaktadır. Bir saldırgan bunu kullanarak sistemin tam kontrolünü ele geçirebilir, veri çalabilir veya kötü amaçlı yazılım yükleyebilir.

Güvenlik topluluğu bu bulguya yüksek ilgi göstermektedir. Hacker News platformunda 83 puan ve 39 yorum almış olması, konunun endüstri tarafından ne kadar önemli görüldüğünü göstermektedir. Sistem yöneticileri ve güvenlik profesyonelleri acilen etkilenen sistemlerini kontrol etmeli ve gerekli yamaları uygulamalıdır.
