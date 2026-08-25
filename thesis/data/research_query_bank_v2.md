# Research Query Bank v2 (Expanded, Code-Switched)

50 Nepali–English code-switched queries grounded in the curated corpus. Each row
annotates the target document and the ground-truth chunk that answers it. Queries
Q012–Q050 were authored by reading the repaired corpus content (see
`thesis/code/preeti_to_unicode.py`), independent of the metadata-alias dictionary,
to avoid alias–query leakage.

| QID | Query (Nepali + English code-switch) | Failure Mode | Target Doc ID(s) | Expected answer location |
| --- | --- | --- | --- | --- |
| Q001 | "Lalitpur मा business registration application गर्दा कुन‑कुन required documents चाहिन्छ? (citizenship, ward recommendation, photos) सबै list चाहिन्छ।" | Long list extraction + code‑switch | LMC_MUN_004 | `LMC_MUN_004_section_2` |
| Q002 | "दर्ता भएपछि business certificate कहाँ record हुन्छ र certificate कुन format/appendix मा दिन्छ?" | Cross‑sentence reference | LMC_MUN_004 | `LMC_MUN_004_section_2` |
| Q003 | "Same owner को multiple locations छन् भने एउटै registration पुग्छ कि अलग‑अलग registration चाहिन्छ?" | Conditional rule | LMC_MUN_004 | `LMC_MUN_004_section_2` |
| Q004 | "Annual renewal deadline कति हो? fiscal year भित्रै renewal गर्नुपर्ने कि specific months?" | Temporal rule | LMC_MUN_004 | `LMC_MUN_004_section_2` |
| Q005 | "Bhaktapur नक्सा पास application मा कुन‑कुन documents चाहिन्छ? required documents exact list चाहिन्छ।" | Long list extraction | BKT_MUN_001 | `BKT_MUN_001_section_3` |
| Q006 | "नक्सा pass certificate निकाल्दा fee कति गुणा लाग्छ? registration vs pass certificate difference स्पष्ट गर।" | Numeric multiplier | BKT_MUN_001 | `BKT_MUN_001_section_3` |
| Q007 | "नक्सा पास/सूचीकरण भएपछि घर‑भवन बेच्न वा भाडामा दिन मिल्छ? any restriction?" | Policy restriction | BKT_MUN_001 | `BKT_MUN_001_section_3` |
| Q008 | "Kathmandu मा property tax लगाउने आधार के हो? कुन annex/schedule ले rate तय गर्छ?" | Cross‑reference to annex | KTM_FIN_002 | `KTM_FIN_002_section_2` |
| Q009 | "Property tax slab मा सम्पत्ति करको दर कुन अनुसूची मा छ? exact rate चाहिन्छ।" | Numeric table lookup | KTM_FIN_002 | `KTM_FIN_002_section_9` |
| Q010 | "Kathmandu public parking शुल्कको दररेट कुन अनुसूची मा छ? time‑based rate चाहिन्छ।" | Multi‑field table | KTM_FIN_002 | `KTM_FIN_002_section_63` |
| Q011 | "Signboard/advertisement को fee per sq ft कति? flex vs digital board फरक rate चाहिन्छ।" | Table lookup | KTM_FIN_002 | `KTM_FIN_002_section_61` |
| Q012 | "काठमाडौं मा भवनको मूल्यांकन दर प्रति वर्गफिट कति हो? building valuation rate चाहिन्छ।" | Numeric table lookup | KTM_FIN_002 | `KTM_FIN_002_section_12` |
| Q013 | "सम्पत्ति कर प्रयोजनको लागि जग्गाको प्रति आना दर कहाँ तोकिएको छ? land per‑aana value।" | Table lookup | KTM_FIN_002 | `KTM_FIN_002_section_14` |
| Q014 | "भूमि करको दररेट वर्ग क देखि च सम्म कति हो? land tax by class चाहिन्छ।" | Numeric class table | KTM_FIN_002 | `KTM_FIN_002_section_31` |
| Q015 | "बहाल कर (rental tax) को दर कति percent हो? कुन अनुसूची मा छ?" | Rate lookup | KTM_FIN_002 | `KTM_FIN_002_section_32` |
| Q016 | "व्यवसाय करको दररेट मदिरा आयातकर्ता लाई कति हो? business tax schedule।" | Category rate | KTM_FIN_002 | `KTM_FIN_002_section_38` |
| Q017 | "Electronics सामान (computer, mobile, TV) बिक्री पसल को व्यवसाय कर कति?" | Category disambiguation | KTM_FIN_002 | `KTM_FIN_002_section_39` |
| Q018 | "वैदेशिक रोजगार परामर्श सेवा (foreign employment consultancy) को व्यवसाय कर कति?" | Category rate | KTM_FIN_002 | `KTM_FIN_002_section_43` |
| Q019 | "Travel र trekking agency को व्यवसाय कर पुँजी अनुसार कति फरक हुन्छ?" | Tiered rate | KTM_FIN_002 | `KTM_FIN_002_section_47` |
| Q020 | "बीमा कम्पनी (insurance) केन्द्रीय कार्यालय को व्यवसाय कर कति हो?" | Category rate | KTM_FIN_002 | `KTM_FIN_002_section_49` |
| Q021 | "College मा १००० भन्दा माथि विद्यार्थी भएको institution को tax कति?" | Tiered rate | KTM_FIN_002 | `KTM_FIN_002_section_51` |
| Q022 | "जडीबुटी, कबाडी र जीवजन्तु शुल्क कुन अनुसूची मा छ? scrap/herb fee।" | Annex lookup | KTM_FIN_002 | `KTM_FIN_002_section_60` |
| Q023 | "घरजग्गा नामसारी सिफारिस को सेवा शुल्क दस्तुर कति हो?" | Fee lookup | KTM_FIN_002 | `KTM_FIN_002_section_69` |
| Q024 | "चार किल्ला प्रमाणित एक आना सम्म को दस्तुर कति?" | Tiered fee | KTM_FIN_002 | `KTM_FIN_002_section_70` |
| Q025 | "अनाधिकृत स्थलमा motorcycle पार्किङ गरे पटके जरिवाना कति?" | Fine lookup | KTM_FIN_002 | `KTM_FIN_002_section_82` |
| Q026 | "मापदण्ड भन्दा बढी बनेको भवनको नक्सा जरिवाना दस्तुर प्रति वर्ग फिट कति?" | Numeric penalty | KTM_FIN_002 | `KTM_FIN_002_section_74` |
| Q027 | "Swimming pool को मासिक सदस्य शुल्क कति हो? monthly member fee।" | Fee lookup | KTM_FIN_002 | `KTM_FIN_002_section_78` |
| Q028 | "विदेशी movie छायाङ्कन (SAARC बाहेक) प्रतिदिन शुल्क कति?" | Category fee | KTM_FIN_002 | `KTM_FIN_002_section_75` |
| Q029 | "जन्म मिति प्रमाणित सिफारिस को दस्तुर कति हो? (Kathmandu 2074)" | Fee lookup (corrupted doc) | KTM_FIN_001 | `KTM_FIN_001_section_23` |
| Q030 | "नाता प्रमाणित (नेपाली) सिफारिस को शुल्क कति लाग्छ?" | Fee lookup (corrupted doc) | KTM_FIN_001 | `KTM_FIN_001_section_15` |
| Q031 | "विद्युत जडान सिफारिस नक्सा पास भएको को दस्तुर कति?" | Conditional fee | KTM_FIN_001 | `KTM_FIN_001_section_9` |
| Q032 | "ज्येष्ठ नागरिक लाई सामाजिक सुरक्षा भत्ता कति रुपैयाँ हो?" | Amount lookup | BKT_FIN_005 | `BKT_FIN_005_section_3` |
| Q033 | "पूर्ण अपाङ्गता (रातो कार्ड) भएका लाई भत्ता रकम कति?" | Amount lookup | BKT_FIN_005 | `BKT_FIN_005_section_4` |
| Q034 | "एकल महिला लाई सामाजिक सुरक्षा भत्ता कति दिइन्छ?" | Amount lookup | BKT_FIN_005 | `BKT_FIN_005_section_3` |
| Q035 | "भक्तपुर मा घर बहाल रकम प्रत्येक कति वर्षमा कति percent बढ्छ?" | Temporal + numeric | BKT_MUN_003 | `BKT_MUN_003_section_12` |
| Q036 | "बहाल कर अग्रिम रूपमा बुझाए छुट पाइन्छ? advance rebate।" | Policy rule | BKT_MUN_003 | `BKT_MUN_003_section_7` |
| Q037 | "घर बहालमा दिने व्यक्तिको दायित्व कहाँ उल्लेख छ? landlord duty।" | Clause locate | BKT_MUN_003 | `BKT_MUN_003_section_4` |
| Q038 | "सवारी दर्ता गर्दा विदेशबाट आयात गरेको भए कुन document चाहिन्छ?" | Conditional docs | BKT_MUN_007 | `BKT_MUN_007_chunk_2` |
| Q039 | "करारमा कर्मचारी छनोट मा लिखित र मौखिक परीक्षाको अंक सीमा कति?" | Numeric extraction (corrupted) | BKT_MUN_004 | `BKT_MUN_004_chunk_2` |
| Q040 | "करार कर्मचारी को शैक्षिक योग्यता बापत कति अंक दिइन्छ?" | Numeric extraction (corrupted) | BKT_MUN_004 | `BKT_MUN_004_chunk_2` |
| Q041 | "नगर विपद् व्यवस्थापन समिति को काम, कर्तव्य र अधिकार के हो?" | Clause locate | BKT_MUN_008 | `BKT_MUN_008_section_2` |
| Q042 | "भक्तपुर नक्सापास दस्तुर पक्की घर (RCC) प्रति वर्गफिट कति?" | Numeric fee | BKT_FIN_003 | `BKT_FIN_003_section_41` |
| Q043 | "भक्तपुर मा दैनिक पार्किङ बस/ट्रक को दस्तुर कति हो?" | Fee lookup | BKT_FIN_003 | `BKT_FIN_003_section_32` |
| Q044 | "व्यापार व्यवसाय नभएको सिफारिस लिन कुन कागजात चाहिन्छ?" | Document list | KTM_MUN_002 | `KTM_MUN_002_section_6` |
| Q045 | "जन्म दर्ता गर्दा कति दिन भित्र र कुन कागजात पेश गर्नुपर्छ?" | Temporal + docs | KTM_MUN_002 | `KTM_MUN_002_section_26` |
| Q046 | "विवाह दर्ता लाई दुलाहा दुलही ले के के प्रमाण ल्याउनुपर्छ?" | Document list | KTM_MUN_002 | `KTM_MUN_002_section_27` |
| Q047 | "व्यक्तिगत घटना (जन्म, मृत्यु, विवाह) दर्ता गर्ने ऐन कहिले को हो?" | Metadata locate | KTM_MUN_005 | `KTM_MUN_005_section_1` |
| Q048 | "भवन निर्माण प्रमाणीकरण को प्रक्रिया कहाँ उल्लेख छ? building certification।" | Clause locate | KTM_MUN_001 | `KTM_MUN_001_section_1` |
| Q049 | "कवाडी (scrap) व्यवसाय को व्यवसाय कर कति हो?" | Category rate | KTM_FIN_002 | `KTM_FIN_002_section_58` |
| Q050 | "विज्ञापन सेवा एजेन्सी को व्यवसाय कर कति लाग्छ?" | Category rate | KTM_FIN_002 | `KTM_FIN_002_section_57` |
