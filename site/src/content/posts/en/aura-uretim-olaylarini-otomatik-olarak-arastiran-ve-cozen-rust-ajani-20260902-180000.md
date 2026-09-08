---
title: "Aura: Automatic Investigation of Production Events and Rust Agent"
pubDate: 2026-09-02T18:00:00.518Z
kategori: "AI"
tags:
  - incident-response
  - rust
  - llm-ops
  - uretim-otomasyon
tagLabels:
  incident-response:
    tr: "Olay Müdahalesi"
    en: "Incident Response"
  rust:
    tr: "Rust"
    en: "Rust"
  llm-ops:
    tr: "LLM Operasyonları"
    en: "LLM Operations"
  uretim-otomasyon:
    tr: "Üretim Otomasyonu"
    en: "Production Automation"
description: "Mezmo is an open source of AI-supported Aura tool to improve SRE team’s incident response workflows in large-scale data processing systems"
kaynak: "https://github.com/mezmo/aura"
coverImage: "https://images.unsplash.com/photo-1709120395858-92f1c7c577f5?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8OHx8YXJ0aWZpY2lhbCUyMGludGVsbGlnZW5jZSUyMHRlY2hub2xvZ3l8ZW58MHwwfHx8MTc4ODMyODI1Nnww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Numan Ali"
gorselFotografciLink: "https://unsplash.com/@king_designer99?utm_source=bilisimpostasi&utm_medium=referral"
gorselQuery: "artificial intelligence technology"
---
The fast solution for SaaS platforms operating data in the scale of Petabayt is a critical requirement. Mezmo team developed an artificial intelligence-based solution to cope with this difficulty and shared Aura’s tool with the community.

The team tried tools such as Claude and LangChain in case of incident response processes but has encountered serious problems:

- **Bağlam stone**: While working with large data sets, the context window of AI models remain insufficient
- **Requirement problem**: Making wrong or dream product responses of models
- **Material problem**: High costs caused by the paid token consumption of Frontier models, extreme resource expenditure for simple tasks
- **Onay fatigue**: Requirements and management challenges of human intervention in automation decisions  
- **Security concerns**: Solid attitudes to loosen permissions in the production environment

Aura written in Rust language offers a specific framework specifically designed for **incident response workflows**. The platform is structured to meet the requirements of this specific usage state, minimizes unnecessary token consumption and protects safety standards from overtime.

This project published as open source shows a smarter way of artificial intelligence integration to other companies and SRE professionals offering similar scale services. Aura aims to become a practical reference point of incident response automation.
