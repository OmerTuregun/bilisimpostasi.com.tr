---
title: "Random page cost Parameter in PostgreSQL: Optimize Database Performance"
pubDate: 2026-09-05T12:00:04.452Z
kategori: "Technology"
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
description: "Effect of random page cost setting query planner performance for database managers and optimization strategies Home"
kaynak: "https://vondra.me/posts/some-more-thoughts-on-random_page_cost/"
coverImage: "https://images.unsplash.com/photo-1606206873764-fd15e242df52?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDM1MjQzfDB8MXxzZWFyY2h8N3x8dGVjaG5vbG9neSUyMGlubm92YXRpb258ZW58MHwwfHx8MTc4ODUyMjY3Mnww&ixlib=rb-4.1.0&w=1200&q=80&fm=jpg&fit=max"
gorselFotografci: "Testalize.me"
gorselFotografciLink: "https://unsplash.com/@testalizeme?utm_source=bilisimpostasi&utm_medium=referral"
---
The query planner of PostgreSQL takes into account many parameters while determining the most efficient way of query execution. **random page cost**, one of these parameters, is a setting that plays a critical role in predicting disk access costs. When not correctly configured, the performance of your database system can significantly decrease.

The random page cost parameter affects the following aspects:

-**Query planner decisions**: Cost calculation used when selection between directory scan and full table scan
- **Disk I/O estimate**: It defines how expensive the random disk access is compared to the queued access
-**: Traditionally set 4.0, but lower values may be required for modern SSDs
- **System architecture**: optimal values that differ between physical server and cloud infrastructure

When setting this parameter, it is important to find the most suitable value by making realistic tests on the system. A value between 1.0 and 2.0 in SSD-based systems can result better than 4.0 and 5.0 in HDD systems. Managers can dynamicly optimize this setting by tracking workload features and query performance metrics.

As a result, **random page cost** is not only a set, but a strategic tool that shapes database performance. The correct configuration can dramatically increase query speeds and provide more efficient use of system resources.
