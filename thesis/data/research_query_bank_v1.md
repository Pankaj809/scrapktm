# Research Query Bank (Impactful, Code‑switched)

| QID | Query (Nepali + English code‑switch) | Failure Mode | Target Doc ID(s) | Expected answer location |
| --- | --- | --- | --- | --- |
| Q001 | “Lalitpur मा business registration application गर्दा कुन‑कुन required documents चाहिन्छ? (citizenship, ward recommendation, photos) सबै list चाहिन्छ।” | Long list extraction + code‑switch | LMC_MUN_004 | `LMC_MUN_004_section_2` (documents list) |
| Q002 | “दर्ता भएपछि business certificate कहाँ record हुन्छ र certificate कुन format/appendix मा दिन्छ?” | Cross‑sentence reference + appendix lookup | LMC_MUN_004 | `LMC_MUN_004_section_2` (registry + certificate issuance format) |
| Q003 | “Same owner को multiple locations छन् भने एउटै registration पुग्छ कि अलग‑अलग registration चाहिन्छ?” | Conditional rule, edge case | LMC_MUN_004 | `LMC_MUN_004_section_2` (separate registration per location) |
| Q004 | “Annual renewal deadline कति हो? fiscal year भित्रै renewal गर्नुपर्ने कि specific months?” | Temporal rule extraction | LMC_MUN_004 | `LMC_MUN_004_section_2` (renewal timing clauses) |
| Q005 | “Bhaktapur नक्सा पास application मा कुन‑कुन documents चाहिन्छ? ‘required documents’ exact list चाहिन्छ।” | Long list extraction | BKT_MUN_001 | `BKT_MUN_001_section_3` (application document list) |
| Q006 | “नक्सा pass certificate निकाल्दा fee कति गुणा लाग्छ? registration vs pass certificate difference स्पष्ट गर।” | Numeric multiplier + contrast | BKT_MUN_001 | `BKT_MUN_001_section_3` (fee multipliers) |
| Q007 | “नक्सा पास/सूचीकरण भएपछि घर‑भवन बेच्न वा भाडामा दिन मिल्छ? any restriction?” | Policy restriction | BKT_MUN_001 | `BKT_MUN_001_section_3` (post‑registration restrictions) |
| Q008 | “Kathmandu मा property tax लगाउने आधार के हो? कुन annex/schedule ले rate तय गर्छ?” | Cross‑reference to annex | KTM_FIN_002 | `KTM_FIN_002_section_2` (tax basis + annex references) |
| Q009 | “Property tax slab मा १–२ करोडको rate कति? exact % चाहिन्छ।” | Numeric table lookup | KTM_FIN_002 | `KTM_FIN_002_section_9` (rate table) |
| Q010 | “Kathmandu public parking मा two‑wheeler vs four‑wheeler fee कति? first half‑hour र per half‑hour rate चाहिन्छ।” | Multi‑field table extraction | KTM_FIN_002 | `KTM_FIN_002_section_63` (parking fee table) |
| Q011 | “Signboard/advertisement को fee per sq ft कति? flex vs digital board फरक rate चाहिन्छ।” | Table lookup + category disambiguation | KTM_FIN_002 | `KTM_FIN_002_section_61` (advertisement fee table) |
