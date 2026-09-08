---
title: "CodePen 2.0 Sends All Your Code to Servers"
pubDate: 2026-09-07T15:00:04.500Z
kategori: "Security"
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
description: "The new version of CodePen was sent to almost instantly servers everything you write before being saved. Your sensitive data may be at risk."
kaynak: "https://news.ycombinator.com/item?id=49596976"
coverImage: "https://images.unsplash.com/photo-1614064642639-e398cf05badb?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8OXx8Y3liZXJzZWN1cml0eSUyMGRpZ2l0YWwlMjBzZWN1cml0eXxlbnwwfDB8fHwxNzg4NzkyNjUxfDA&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "FlyD"
gorselFotografciLink: "https://unsplash.com/@flyd2069?utm_source=bilisimpostasi&utm_medium=referral"
---
CodePen 2.0 started to create a serious privacy concern in the web development community. According to the findings shared on Hacker News, the entire code you write on the platform is sent to** servers instantly if it is not completed even without being recorded.

A researcher revealed the problem with concrete data by testing this situation:

- Every character written in the editor is transferred to codepen.dev servers within 1-2 seconds
- This data transfer is clearly seen on the Network tab of browser developer tools
- Even unregistered codes are rendered in the preview created
- When tested with a unique marker, even before the marker was recorded, it was detected in the preview HTML

This behavior can be designed for** quick automatic recording** purpose. However, the problem is: if you accidentally paste the API switches, database passwords, or other sensitive information into the editor, these will be saved on CodePen’s servers very first without being deleted.

The developers who have security consciousness know that when using CodePen 2.0 should not write an API key or secret information as a thought editor. The platform should report this behavior and inform users clearly.
