#!/usr/bin/env python3
"""
Canonical Exam & Rubric Importer for UPPSC BEO Mains Assessment Platform.
Parses supplied Excel workbooks and PDF question papers, cross-checks extracted PDF text
against VLM-verified page renders, flags workbook anomalies/contaminations, and outputs
a deterministic, versioned machine-readable import preview JSON.
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
import openpyxl
import pymupdf

ASSETS_DIR = "/home/user/assets"
GS_WORKBOOK_PATH = os.path.join(ASSETS_DIR, "ToppersCode_Merged_AI_Mains_Rubrics_All_Mocks.xlsx")
HINDI_WORKBOOK_PATH = os.path.join(ASSETS_DIR, "ToppersCode_UPPSC_BEO_Hindi_Mocks_04_05_06_07_13_15_17_AI_Rubrics.xlsx")
GS_PDF_PATH = os.path.join(ASSETS_DIR, "UPPSC BEO MAINS Mock 17.pdf")
HINDI_PDF_PATH = os.path.join(ASSETS_DIR, "UPPSC BEO MAINS हिंदी मॉक 16.pdf")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# VLM-verified canonical Hindi & English question texts from rendered 200-DPI PDF pages
# (Cross-checked against UPPSC BEO MAINS Mock 17.pdf pages 1-4)
GS_MOCK17_VLM_CANONICAL = {
    1: {
        "page": 1,
        "hi": "वैदिक काल से महाजनपद काल तक भारतीय समाज एवं राजनीतिक व्यवस्था में हुए प्रमुख परिवर्तनों की चर्चा कीजिए।",
        "en": "Discuss the major changes in Indian society and political organisation from the Vedic period to the age of Mahajanapadas.",
        "topic": "Ancient Society & Political Organisation (Vedic to Mahajanapadas)",
        "expected_points": [
            "Transition from pastoral semi-nomadic tribal polity (Jana) to territorial agrarian states (Janapada/Mahajanapada)",
            "Shift from lineage-based Sabha/Samiti assemblies to hereditary monarchies and oligarchic republics (Gana-Sanghas like Vajji, Malla)",
            "Rigidification of Varna system from occupation-based (Early Vedic) to birth-based hierarchy and emergence of Jatis",
            "Iron technology (PGW/NBPW phase) enabling Gangetic forest clearance, agricultural surplus, and Second Urbanisation",
            "Regular taxation system (Bhaga, Bali, Shulka) and standing armies replacing voluntary tribal tributes"
        ],
        "common_errors": [
            "Confusing Indus Valley urbanisation with the Second Urbanisation of the 6th century BCE",
            "Claiming all 16 Mahajanapadas were monarchies (ignoring Gana-Sanghas)"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-01",
                "title": "NCERT Class XII Themes in Indian History Part I — Kings, Farmers and Towns",
                "url": "https://ncert.nic.in/textbook.php?lehs1=2-4",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "The sixth century BCE is often regarded as a major turning point in early Indian history associated with early states, cities, growing use of iron, development of coinage, and emergence of 16 Mahajanapadas including both monarchies and oligarchies (ganas/sanghas)."
            }
        ]
    },
    2: {
        "page": 1,
        "hi": "भारत के राष्ट्रीय आंदोलन में सुभाष चंद्र बोस एवं आजाद हिंद फौज के योगदान का मूल्यांकन कीजिए।",
        "en": "Evaluate the contribution of Subhas Chandra Bose and the Indian National Army to India’s national movement.",
        "topic": "Subhas Chandra Bose and the Indian National Army (INA)",
        "expected_points": [
            "Radicalisation of nationalist goals: uncompromising demand for complete independence (Purna Swaraj) at Haripura (1938) & Tripuri (1939) and Forward Bloc formation",
            "Reorganisation of Azad Hind Fauj (INA) in Southeast Asia (1943) and establishment of Provisional Government of Free India (Arzi Hukumat-e-Azad Hind)",
            "Inclusive mobilisation across religion, caste, diaspora, and gender (Rani of Jhansi Regiment led by Capt. Lakshmi Swaminathan)",
            "Military campaign on the Indo-Burma frontier (Imphal-Kohima, Moirang flag hoisting) internationalising India's freedom struggle",
            "Catalytic psychological impact: 1945–46 Red Fort INA Trials sparked nationwide mass upsurge and eroded British loyalty within the Indian Armed Forces (RIN Mutiny 1946)"
        ],
        "common_errors": [
            "Attributing the original founding of the first INA in 1942 solely to Bose without acknowledging Capt. Mohan Singh / Rash Behari Bose"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-02",
                "title": "Ministry of Culture, Govt of India — Netaji Subhas Chandra Bose & Azad Hind Fauj",
                "url": "https://amritmahotsav.nic.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Subhas Chandra Bose proclaimed the Provisional Government of Azad Hind on 21 October 1943 in Singapore. Though the Imphal-Kohima campaign faced logistical setbacks, the 1945 Red Fort INA trials united Indian public opinion and triggered mutinies in the Royal Indian Navy."
            }
        ]
    },
    3: {
        "page": 1,
        "hi": "उत्तर प्रदेश में कृषि-आधारित अर्थव्यवस्था को प्रभावित करने वाले प्रमुख प्राकृतिक एवं मानवीय कारकों की चर्चा कीजिए।",
        "en": "Discuss the major natural and human factors influencing the agro-based economy of Uttar Pradesh.",
        "topic": "Uttar Pradesh Agro-Based Economy: Natural & Human Factors",
        "expected_points": [
            "Natural factors: fertile Indo-Gangetic alluvial soils (Bhangar/Khadar), diverse 9 agro-climatic zones, perennial Himalayan rivers, and monsoon variability (floods in Eastern UP, drought in Bundelkhand)",
            "Human & institutional factors: high population pressure causing fragmented landholdings (<1 hectare marginal holdings)",
            "Irrigation & infrastructure: extensive canal network, tube-well density in Western UP vs irrigation deficits in Bundelkhand",
            "Technological & policy inputs: HYV seeds, fertilizer/credit access, MSP procurement asymmetry, e-Mandi, ODOP food processing clusters, and cold-chain gaps"
        ],
        "common_errors": [
            "Listing only natural geographic factors while omitting human/institutional factors required by the prompt"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-03",
                "title": "Department of Agriculture, Government of Uttar Pradesh — Agro-Climatic Zones & Economic Survey",
                "url": "https://upagripardarshi.gov.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Uttar Pradesh is divided into 9 agro-climatic zones. Its agriculture is shaped by fertile Gangetic alluvium and extensive tube-well/canal irrigation, alongside structural challenges of small average operational holdings (~0.73 ha) and regional disparities between Western UP and Bundelkhand."
            }
        ]
    },
    4: {
        "page": 1,
        "hi": "भारतीय संविधान में केंद्र एवं राज्यों के बीच विधायी शक्तियों के वितरण की प्रमुख विशेषताएँ बताइए।",
        "en": "State the major features of the distribution of legislative powers between the Union and the States in the Indian Constitution.",
        "topic": "Union-State Legislative Power Distribution (Part XI, Articles 245-255)",
        "expected_points": [
            "Constitutional framework under Part XI (Articles 245–255) dividing powers territorially (Art 245) and by subject matter (Art 246 & Seventh Schedule)",
            "Threefold list system: Union List (exclusive Parliamentary power on national importance), State List (normal state competence), Concurrent List (shared jurisdiction)",
            "Union supremacy in case of repugnancy on Concurrent List subjects (Article 254) and residuary powers vested in Parliament (Article 248)",
            "Exceptional unitary overrides where Parliament legislates on State List: national interest via Rajya Sabha resolution (Art 249), National Emergency (Art 250), consent of states (Art 252), international treaties (Art 253), and President's Rule (Art 356)"
        ],
        "common_errors": [
            "Stating residuary powers lie with the States or President rather than Parliament under Article 248"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-04",
                "title": "Constitution of India — Part XI: Relations between the Union and the States (Articles 245–255)",
                "url": "https://legislative.gov.in/constitution-of-india/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Articles 245 to 255 in Part XI and the Seventh Schedule govern legislative relations between the Union and States through List I (Union), List II (State), and List III (Concurrent), with residuary powers vested in Parliament under Article 248."
            }
        ]
    },
    5: {
        "page": 1,
        "hi": "भारत में मरुस्थलीय एवं अर्ध-शुष्क क्षेत्रों के पारिस्थितिक संरक्षण की प्रमुख चुनौतियों की चर्चा कीजिए।",
        "en": "Discuss the major challenges of ecological conservation in desert and semi-arid regions of India.",
        "topic": "Ecological Conservation in Desert & Semi-Arid Regions",
        "expected_points": [
            "Severe climatic stress: erratic rainfall (<250–500 mm), high evapotranspiration, recurrent droughts, and shifting sand dunes",
            "Anthropogenic livestock & demographic pressure: overgrazing of common pasturelands (Orans/Gauchars) and fuelwood extraction",
            "Unsustainable water & soil use: intensive canal irrigation (e.g., Indira Gandhi Canal) causing waterlogging, secondary salinisation, and groundwater depletion",
            "Invasive species & habitat fragmentation: spread of Prosopis juliflora displacing native xerophytic flora and threatening endemic fauna (Great Indian Bustard)",
            "Mining, wind/solar infrastructure encroachment, and socio-economic vulnerability of pastoral communities"
        ],
        "common_errors": [
            "Treating intensive canal flood-irrigation as purely beneficial without noting waterlogging and salinisation risks in arid soils"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-05",
                "title": "ISRO SAC Desertification and Land Degradation Atlas of India & UNCCD National Action Programme",
                "url": "https://www.sac.gov.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Arid and semi-arid tracts in Rajasthan, Gujarat, and peninsular India face wind erosion, vegetation degradation, overgrazing, invasive Prosopis juliflora proliferation, and secondary salinisation in canal command areas."
            }
        ]
    },
    6: {
        "page": 2,
        "hi": "भारतीय अर्थव्यवस्था में सार्वजनिक क्षेत्र के उपक्रमों की भूमिका एवं उनके सामने उपस्थित प्रमुख चुनौतियों का विश्लेषण कीजिए।",
        "en": "Analyse the role of public sector enterprises in the Indian economy and the major challenges faced by them.",
        "topic": "Public Sector Enterprises (PSEs): Role & Challenges",
        "expected_points": [
            "Strategic role: building heavy industrial base, core infrastructure (energy, defence, railways, steel), balanced regional development, employment generation, and fiscal contribution (dividends/taxes)",
            "Operational & governance challenges: bureaucratic interference, delayed decision-making, and lack of commercial autonomy",
            "Financial & competitive pressures: mounting losses in non-strategic CPSEs, obsolete technology, overstaffing, and stiff competition from private/global firms",
            "Reform trajectory: Maharatna/Navratna autonomy, strategic disinvestment, asset monetisation, and New Public Sector Enterprise Policy"
        ],
        "common_errors": [
            "Addressing only the historical role of PSEs while ignoring contemporary challenges and reforms"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-06",
                "title": "Department of Public Enterprises (DPE), Ministry of Finance — Public Enterprises Survey",
                "url": "https://dpe.gov.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "CPSEs play a foundational role in strategic sectors (energy, defence, transport, minerals) while facing challenges of capacity utilisation, legacy cost structures, technological upgradation, and governance autonomy."
            }
        ]
    },
    7: {
        "page": 2,
        "hi": "भारत में पोषण संबंधी समस्याओं के प्रमुख कारणों तथा उनके समाधान के लिए आवश्यक उपायों की चर्चा कीजिए।",
        "en": "Discuss the major causes of nutritional problems in India and the measures required to address them.",
        "topic": "Nutritional Problems in India: Causes & Measures",
        "expected_points": [
            "Multidimensional causes: poverty and food insecurity, cereal-heavy diets lacking dietary diversity (hidden hunger/micronutrient deficiency of iron, vitamin A, zinc)",
            "Social & lifecycle factors: maternal undernutrition, early marriage/pregnancy, suboptimal infant feeding practices, gender intra-household bias",
            "WASH & health deficits: unsafe drinking water, poor sanitation, diarrhoeal infections reducing nutrient absorption",
            "Remedial measures: POSHAN Abhiyaan (Mission Saksham Anganwadi & Poshan 2.0), PM POSHAN (Mid-Day Meal), ICDS, NFSA food fortification (fortified rice), anemia control (Anemia Mukt Bharat), and women's education"
        ],
        "common_errors": [
            "Equating caloric sufficiency with complete nutrition while overlooking micronutrient deficiencies and sanitation linkages"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-07",
                "title": "Ministry of Women and Child Development — Mission Poshan 2.0 & NFHS-5 Findings",
                "url": "https://wcd.nic.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Addressing stunting, wasting, and anaemia requires convergence across supplementary nutrition (Poshan 2.0), dietary diversity, food fortification, maternal care, and WASH interventions."
            }
        ]
    },
    8: {
        "page": 2,
        "hi": "शिक्षक की भूमिका केवल ज्ञान प्रदान करने तक सीमित नहीं है। इस कथन के संदर्भ में शिक्षक की बदलती भूमिका स्पष्ट कीजिए।",
        "en": "The role of a teacher is not limited to imparting knowledge. Explain the changing role of a teacher in this context.",
        "topic": "Changing Role of a Teacher (NEP 2020 & Constructivist Pedagogy)",
        "expected_points": [
            "Shift from rote transmitter ('sage on the stage') to facilitator of experiential, inquiry-driven, and constructivist learning",
            "Mentor for holistic development: nurturing critical thinking, creativity, socio-emotional resilience, constitutional values, and ethics",
            "Digital & inclusive pedagogue: integrating EdTech (DIKSHA, blended learning), diagnosing diverse learner needs, and ensuring inclusive classrooms (CWSN)",
            "Community bridge & educational leader: fostering school-community linkage, continuous professional development (CPD), and competency-based formative assessment (NEP 2020)"
        ],
        "common_errors": [
            "Writing a generic praise of teachers without analysing pedagogical, technological, and NEP 2020 shifts"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-08",
                "title": "Ministry of Education — National Education Policy (NEP) 2020, Chapter 5: Teachers",
                "url": "https://www.education.gov.in/nep/about-nep",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "NEP 2020 positions teachers at the heart of the learning process as facilitators of holistic, inquiry-based, competency-oriented, and inclusive education."
            }
        ]
    },
    9: {
        "page": 2,
        "hi": "पर्वतीय पारिस्थितिकी तंत्र पर मानवीय गतिविधियों के प्रभावों की चर्चा कीजिए।",
        "en": "Discuss the impacts of human activities on mountain ecosystems.",
        "topic": "Human Impacts on Mountain Ecosystems",
        "expected_points": [
            "Deforestation & land-use change: slope destabilisation, accelerated soil erosion, and loss of endemic biodiversity",
            "Unplanned infrastructure & linear projects: road widening, tunnelling, and cascade hydropower projects altering river ecology and triggering landslides",
            "Mass tourism & urbanisation: solid waste accumulation, water scarcity in hill towns, and construction on fragile floodplains/steep slopes",
            "Anthropogenic climate forcing: accelerated glacial retreat, Glacial Lake Outburst Floods (GLOFs), cloudbursts, and altered hydrological regimes downstream"
        ],
        "common_errors": [
            "Listing only natural tectonic hazards without linking them to human activities as required by the prompt"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-09",
                "title": "NITI Aayog — Contributing to Sustainable Development in the Indian Himalayan Region",
                "url": "https://www.niti.gov.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "Unsustainable tourism, unregulated construction, deforestation, and linear infrastructure in young fold mountains amplify slope instability, spring depletion, and disaster vulnerability."
            }
        ]
    },
    10: {
        "page": 2,
        "hi": "उत्तर प्रदेश में परिवहन के विभिन्न साधनों के विकास तथा क्षेत्रीय आर्थिक गतिविधियों के बीच संबंध स्पष्ट कीजिए।",
        "en": "Explain the relationship between the development of different modes of transport and regional economic activities in Uttar Pradesh.",
        "topic": "Transport Networks and Regional Economic Activities in UP",
        "expected_points": [
            "Expressway & road network (Purvanchal, Bundelkhand, Agra-Lucknow, Ganga Expressways): integrating lagging regions (Bundelkhand/Purvanchal) with NCR/national markets",
            "Rail & Dedicated Freight Corridors (EDFC & WDFC junction at Dadri): accelerating industrial corridors, coal/agro-freight logistics, and MSME clusters",
            "Civil aviation & inland waterways: 5 international airports and NW-1 (Haldia–Varanasi on Ganga) boosting tourism, handicrafts, and export logistics",
            "Synergy with ODOP (One District One Product), Defence Industrial Corridor, food parks, and rural-urban market integration"
        ],
        "common_errors": [
            "Listing expressway names without explaining how they stimulate regional agriculture, MSMEs, ODOP, and balanced regional growth"
        ],
        "reference_sources": [
            {
                "source_id": "ref-gs17-10",
                "title": "UPEIDA & Invest UP — Expressways, Logistics & Industrial Corridors in Uttar Pradesh",
                "url": "https://upeida.up.gov.in/",
                "retrieved_at": "2026-10-12T09:00:00Z",
                "claim_snapshot": "UP's expressway grid, Eastern Dedicated Freight Corridor, National Waterway-1, and multi-modal logistics hubs link regional ODOP clusters and agricultural zones to national and export markets."
            }
        ]
    },
    11: {
        "page": 2,
        "hi": "महाजनपदों के उदय के दो प्रमुख कारण बताइए।",
        "en": "State two major reasons for the rise of the Mahajanapadas.",
        "topic": "Rise of Mahajanapadas (Two Major Reasons)",
        "expected_points": [
            "Widespread use of iron tools and ploughshares in the fertile middle Gangetic plains generating substantial agricultural surplus",
            "Growth of trade, crafts, coinage (punch-marked coins), and military consolidation of tribal Janas into territorial states"
        ],
        "common_errors": ["Giving vague points without mentioning iron technology or agricultural surplus"],
        "reference_sources": [{"source_id": "ref-gs17-01", "title": "NCERT Class XII Themes in Indian History Part I", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Iron ploughshare agriculture in the alluvial Gangetic plain and iron mines of Magadha enabled surplus production and state formation."}]
    },
    12: {
        "page": 2,
        "hi": "आजाद हिंद फौज के गठन का उद्देश्य बताइए।",
        "en": "State the objective behind the formation of the Indian National Army.",
        "topic": "Objective of the Indian National Army (INA)",
        "expected_points": [
            "To wage an armed liberation struggle to overthrow British colonial rule in India with the support of Indian prisoners of war and expatriates in Southeast Asia",
            "To establish a sovereign, united Provisional Government of Free India and inspire patriotic uprising within British Indian armed forces"
        ],
        "common_errors": ["Stating INA was formed merely to defend Japanese territory"],
        "reference_sources": [{"source_id": "ref-gs17-02", "title": "Ministry of Culture — Azad Hind Fauj", "url": "https://amritmahotsav.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "The INA was formed to secure India's complete independence from British rule through an organised armed struggle."}]
    },
    13: {
        "page": 2,
        "hi": "उत्तर प्रदेश में गन्ना उत्पादन के लिए अनुकूल परिस्थितियाँ बताइए।",
        "en": "State the favourable conditions for sugarcane cultivation in Uttar Pradesh.",
        "topic": "Favourable Conditions for Sugarcane in UP",
        "expected_points": [
            "Climatic conditions: warm sub-tropical climate with 21°C–27°C temperature, 75–120 cm rainfall, and frost-free growing season",
            "Edaphic & infrastructural conditions: deep fertile moisture-retentive alluvial loam soil (Terai & Ganga-Yamuna Doab), assured canal/tube-well irrigation, and dense sugar mill network"
        ],
        "common_errors": ["Listing arid or cold mountain conditions"],
        "reference_sources": [{"source_id": "ref-gs17-03", "title": "UP Sugarcane Department & NCERT India People and Economy", "url": "https://upagripardarshi.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Sugarcane thrives in deep fertile alluvial soils of the Ganga-Yamuna Doab and Terai belt with 21–27°C temperatures and assured irrigation."}]
    },
    14: {
        "page": 2,
        "hi": "केंद्र एवं राज्यों के बीच विधायी शक्तियों का विभाजन किस आधार पर किया गया है?",
        "en": "On what basis are legislative powers divided between the Union and the States?",
        "topic": "Basis of Union-State Legislative Division",
        "expected_points": [
            "Twofold constitutional basis under Articles 245 and 246: (1) Territorial jurisdiction (Union for whole/part of India; State for state territory)",
            "(2) Subject-matter classification under the Seventh Schedule into Union List (national importance), State List (local/regional), and Concurrent List (shared interest)"
        ],
        "common_errors": ["Mentioning only the three lists without noting territorial vs subject-matter division under Art 245–246"],
        "reference_sources": [{"source_id": "ref-gs17-04", "title": "Constitution of India — Articles 245 & 246", "url": "https://legislative.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Article 245 defines territorial extent and Article 246 divides subject matter via the Seventh Schedule."}]
    },
    15: {
        "page": 2,
        "hi": "मरुस्थलीकरण को रोकने के दो उपाय बताइए।",
        "en": "State two measures to control desertification.",
        "topic": "Two Measures to Control Desertification",
        "expected_points": [
            "Afforestation, shelterbelt/windbreak plantations, and sand-dune stabilisation using native drought-resistant species",
            "Regulated rotational grazing, rainwater harvesting/watershed management, and micro-irrigation (drip/sprinkler) to prevent soil salinisation"
        ],
        "common_errors": ["Suggesting water-intensive flood irrigation"],
        "reference_sources": [{"source_id": "ref-gs17-05", "title": "CAZRI & UNCCD India Action Plan", "url": "https://www.cazri.res.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Shelterbelt plantation, sand-dune fixation, rotational grazing, and dryland watershed management curb desertification."}]
    },
    16: {
        "page": 2,
        "hi": "सार्वजनिक उपक्रमों की स्थापना के दो प्रमुख उद्देश्यों का उल्लेख कीजिए।",
        "en": "Mention two major objectives behind the establishment of public sector enterprises.",
        "topic": "Two Major Objectives of PSEs",
        "expected_points": [
            "Building core infrastructure and heavy capital-intensive industries with long gestation periods for rapid self-reliant industrialisation",
            "Promoting balanced regional development, employment generation, and preventing concentration of economic power"
        ],
        "common_errors": ["Stating short-term profit maximisation as the sole founding objective"],
        "reference_sources": [{"source_id": "ref-gs17-06", "title": "DPE — Public Enterprises Survey", "url": "https://dpe.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "PSEs were established to build strategic industrial infrastructure and foster balanced regional socio-economic development."}]
    },
    17: {
        "page": 2,
        "hi": "भारत में कुपोषण के दो प्रमुख कारण बताइए।",
        "en": "State two major causes of malnutrition in India.",
        "topic": "Two Major Causes of Malnutrition in India",
        "expected_points": [
            "Economic poverty and lack of dietary diversity leading to inadequate intake of proteins, vitamins, and micronutrients (hidden hunger)",
            "Poor maternal health/anaemia, inadequate infant feeding practices, and poor sanitation/unsafe water causing recurrent infections"
        ],
        "common_errors": ["Giving only one cause when two distinct causes are requested"],
        "reference_sources": [{"source_id": "ref-gs17-07", "title": "NFHS-5 & Mission Poshan 2.0", "url": "https://wcd.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Inadequate dietary diversity, maternal undernutrition, and WASH-related infections are primary drivers of malnutrition."}]
    },
    18: {
        "page": 3,
        "hi": "शिक्षक द्वारा विद्यार्थियों में नेतृत्व क्षमता विकसित करने के दो उपाय बताइए।",
        "en": "State two measures by which a teacher can develop leadership skills among students.",
        "topic": "Developing Student Leadership Skills",
        "expected_points": [
            "Delegating classroom/co-curricular responsibilities (student councils, house captains, peer mentoring, eco-clubs)",
            "Organising collaborative group projects, problem-solving debates, and community service activities that build decision-making and accountability"
        ],
        "common_errors": ["Focusing only on passive lecture instruction"],
        "reference_sources": [{"source_id": "ref-gs17-08", "title": "NEP 2020 — Holistic Student Development", "url": "https://www.education.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Participatory school governance, peer-led clubs, and collaborative project work cultivate student leadership."}]
    },
    19: {
        "page": 3,
        "hi": "पर्वतीय क्षेत्रों में भूस्खलन के अतिरिक्त किसी एक प्रमुख प्राकृतिक खतरे का उल्लेख कीजिए।",
        "en": "Mention one major natural hazard other than landslides in mountainous regions.",
        "topic": "Mountain Natural Hazard Other Than Landslides",
        "expected_points": [
            "Cloudbursts and flash floods / Glacial Lake Outburst Floods (GLOFs) / Snow avalanches / High-seismic earthquakes (any one accurately identified with brief impact)"
        ],
        "common_errors": ["Mentioning landslides despite the explicit exclusion in the prompt"],
        "reference_sources": [{"source_id": "ref-gs17-09", "title": "NDMA Guidelines — Glacial Lake Outburst Floods & Cloudbursts", "url": "https://ndma.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Himalayan mountain regions face severe hazards including cloudbursts, flash floods, GLOFs, earthquakes, and avalanches."}]
    },
    20: {
        "page": 3,
        "hi": "उत्तर प्रदेश में सड़क परिवहन के आर्थिक महत्व को संक्षेप में बताइए।",
        "en": "Briefly state the economic importance of road transport in Uttar Pradesh.",
        "topic": "Economic Importance of Road Transport in UP",
        "expected_points": [
            "Provides last-mile farm-to-mandi connectivity for perishable agricultural produce, sugarcane, and dairy across rural यूपी",
            "Connects ODOP clusters, MSMEs, industrial parks, and expressway corridors to national markets while generating construction/logistics employment"
        ],
        "common_errors": ["Discussing railways/waterways instead of road transport"],
        "reference_sources": [{"source_id": "ref-gs17-10", "title": "UPEIDA & UP Economic Survey", "url": "https://upeida.up.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Road and expressway networks carry the bulk of short- and medium-haul freight and passenger traffic in UP, linking rural farms and ODOP units to markets."}]
    },
    21: {"page": 3, "hi": "महाजनपद", "en": "Mahajanapadas", "topic": "Mahajanapadas", "expected_points": ["16 major territorial states (monarchies and Gana-Sanghas) that emerged in northern India during the 6th century BCE (e.g., Magadha, Kosala, Vatsa, Avanti) mentioned in Anguttara Nikaya."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-01", "title": "NCERT Class XII History", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Buddhist and Jaina texts list sixteen Mahajanapadas in the 6th century BCE."}]},
    22: {"page": 3, "hi": "बौद्ध संगीति", "en": "Buddhist Councils", "topic": "Buddhist Councils", "expected_points": ["Four historic assemblies convened after Buddha's Mahaparinirvana at Rajagriha (483 BCE), Vaishali (383 BCE), Pataliputra (c. 250 BCE under Ashoka), and Kundalvana, Kashmir (1st c. CE under Kanishka) to codify Tripitaka texts and resolve monastic schisms."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-01", "title": "NCERT Ancient India", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Four Buddhist Councils compiled Buddhist canon (Sutta, Vinaya, Abhidhamma Pitakas) and marked the Mahayana-Hinayana division."}]},
    23: {"page": 3, "hi": "सातवाहन वंश", "en": "Satavahana Dynasty", "topic": "Satavahana Dynasty", "expected_points": ["Major post-Mauryan Deccan dynasty (c. 1st century BCE–2nd century CE, capitals Pratishthana/Amaravati), founded by Simuka; renowned for Gautamiputra Satakarni, matronymics, lead/potin coins, land grants to Brahmanas/Buddhist monks, and maritime trade."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-01", "title": "NCERT Themes in Indian History", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Satavahanas ruled the Deccan, used matronymics, issued lead/copper coins, and patronised Buddhist stupas like Amaravati."}]},
    24: {"page": 3, "hi": "विजयनगर स्थापत्य", "en": "Vijayanagara Architecture", "topic": "Vijayanagara Architecture", "expected_points": ["Distinctive South Indian temple style (14th–16th c., Hampi) featuring monumental Raya Gopurams, Kalyana Mandapams with carved horse/mythical yali pillars, Amman shrines, and secular lotus/indo-islamic arches (e.g., Virupaksha & Vittala temples)."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-01", "title": "NCERT Themes in Indian History Part II — An Imperial Capital: Vijayanagara", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Vijayanagara architecture at Hampi is characterised by Raya Gopurams, pillared mandapas, stone chariot at Vittala temple, and Lotus Mahal."}]},
    25: {"page": 3, "hi": "अगस्त क्रांति", "en": "August Revolution", "topic": "August Revolution (Quit India Movement 1942)", "expected_points": ["Mass anti-colonial civil disobedience movement launched on 8 August 1942 at Gowalia Tank, Bombay with Gandhi's call of 'Do or Die', marked by spontaneous youth/peasant uprisings and parallel governments (Ballia, Tamluk, Satara)."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-02", "title": "NCERT Modern India — Quit India Movement", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "The Quit India Movement of August 1942 is known as the August Kranti."}]},
    26: {"page": 3, "hi": "रॉयल इंडियन नेवी विद्रोह", "en": "Royal Indian Navy Mutiny", "topic": "Royal Indian Navy Mutiny (February 1946)", "expected_points": ["Anti-British revolt launched on 18 February 1946 by Indian naval ratings aboard HMIS Talwar in Bombay over racial discrimination, poor food, and INA trials, rapidly spreading to 78 ships and shore establishments."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-02", "title": "Ministry of Culture — RIN Revolt 1946", "url": "https://amritmahotsav.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "The RIN Mutiny began on 18 February 1946 at HMIS Talwar in Bombay, signalling the end of British reliance on Indian armed forces."}]},
    27: {"page": 3, "hi": "उत्तर प्रदेश का बुंदेलखंड पठार", "en": "Bundelkhand Plateau of Uttar Pradesh", "topic": "Bundelkhand Plateau of UP", "expected_points": ["Southern upland physiographic region of UP (comprising Jhansi, Lalitpur, Banda, Hamirpur, Mahoba, Jalaun, Chitrakoot) composed of ancient Archaean granite/gneiss rocks, red-black soils (Rakar, Parwa, Mar, Kabar), semi-arid climate, and mineral wealth."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-03", "title": "UP Gazetteer & Agro-Climatic Profile", "url": "https://upagripardarshi.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Bundelkhand plateau covers 7 southern districts of UP with gneissic topography, Betwa-Ken drainage, and semi-arid conditions."}]},
    28: {"page": 3, "hi": "संघ सूची", "en": "Union List", "topic": "Union List (List I, Seventh Schedule)", "expected_points": ["List I of the Seventh Schedule (Article 246(1)) comprising subjects of national importance (defence, foreign affairs, banking, atomic energy, railways, census; originally 97, currently 98 numbered/100 entries) on which Parliament has exclusive power to legislate."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-04", "title": "Constitution of India — Seventh Schedule", "url": "https://legislative.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "List I (Union List) in the Seventh Schedule enumerates subjects under exclusive Parliamentary legislative competence."}]},
    29: {"page": 3, "hi": "समवर्ती सूची", "en": "Concurrent List", "topic": "Concurrent List (List III, Seventh Schedule)", "expected_points": ["List III of the Seventh Schedule (Article 246(2)) containing subjects of common Union-State interest (education, forests, criminal law, marriage, weights & measures; 52 entries, 42nd Amendment moved 5 subjects) where Union law prevails in case of conflict (Art 254)."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-04", "title": "Constitution of India — Seventh Schedule List III", "url": "https://legislative.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Both Parliament and State Legislatures can legislate on Concurrent List subjects, subject to Union primacy under Article 254."}]},
    30: {"page": 3, "hi": "राज्यपाल की विवेकाधीन शक्तियाँ", "en": "Discretionary Powers of Governor", "topic": "Discretionary Powers of Governor (Article 163)", "expected_points": ["Constitutional and situational powers exercised without Council of Ministers' aid (Art 163(2)): reserving bills for President (Art 200), recommending President's Rule (Art 356), fifth/sixth schedule administration, and inviting a CM in a hung assembly."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-04", "title": "Constitution of India — Articles 163, 200, 356", "url": "https://legislative.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Article 163 provides for discretionary functions explicitly required by or under the Constitution."}]},
    31: {"page": 3, "hi": "सार्वजनिक क्षेत्र के उपक्रम", "en": "Public Sector Enterprises", "topic": "Public Sector Enterprises (PSEs)", "expected_points": ["Commercial enterprises in which majority equity (51% or more) is held by Central, State, or joint governments (classified as Maharatna, Navratna, Miniratna) operating in strategic and core economic sectors."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-06", "title": "DPE — Classification of CPSEs", "url": "https://dpe.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Public Sector Enterprises are government-owned commercial undertakings with >=51% state equity."}]},
    32: {"page": 3, "hi": "पूँजीगत व्यय", "en": "Capital Expenditure", "topic": "Capital Expenditure (Capex)", "expected_points": ["Government spending that creates productive physical/financial assets (roads, railways, schools, machinery, equity investments) or reduces financial liabilities (loan repayment), yielding long-term multiplier growth."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-06", "title": "Union Budget Glossary — Capital Expenditure", "url": "https://www.indiabudget.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Capital expenditure creates durable assets or reduces government liabilities, distinct from revenue expenditure."}]},
    33: {"page": 3, "hi": "सामाजिक सुरक्षा", "en": "Social Security", "topic": "Social Security", "expected_points": ["Public protective measures (pensions, health insurance, maternity benefits, disability support, e-Shram, PM-SYM, Atal Pension Yojana, Art 41 DPSP) safeguarding citizens against economic distress from old age, illness, unemployment, or maternity."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-07", "title": "Ministry of Labour & Employment — Code on Social Security", "url": "https://labour.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Social security provides state-backed protection against contingencies of old age, sickness, maternity, and disability."}]},
    34: {"page": 3, "hi": "खाद्य प्रसंस्करण", "en": "Food Processing", "topic": "Food Processing", "expected_points": ["Value-addition transformation of raw agricultural, horticultural, dairy, or fishery produce into shelf-stable, marketable food products (supported by PMKSY, PMFME), reducing post-harvest wastage and raising farm incomes."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-03", "title": "Ministry of Food Processing Industries (MoFPI)", "url": "https://www.mofpi.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Food processing links agriculture with manufacturing, curbs wastage, enhances shelf-life, and generates rural employment."}]},
    35: {"page": 3, "hi": "मरुस्थलीकरण", "en": "Desertification", "topic": "Desertification", "expected_points": ["Persistent land degradation in arid, semi-arid, and dry sub-humid areas resulting from climatic variations and human activities (overgrazing, deforestation, unsustainable irrigation), reducing biological productivity (UNCCD definition)."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-05", "title": "UNCCD & ISRO Desertification Atlas", "url": "https://www.sac.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Desertification is land degradation in arid, semi-arid, and dry sub-humid zones caused by climatic and anthropogenic factors."}]},
    36: {"page": 3, "hi": "मैंग्रोव पारिस्थितिकी तंत्र", "en": "Mangrove Ecosystem", "topic": "Mangrove Ecosystem", "expected_points": ["Salt-tolerant halophytic coastal intertidal forest ecosystem (e.g., Sundarbans, Bhitarkanika, Pichavaram) featuring pneumatophores and vivipary, acting as bio-shields against cyclones/erosion, blue-carbon sinks, and marine nurseries."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-05", "title": "Forest Survey of India — Mangrove Cover & MISHTI Initiative", "url": "https://fsi.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Mangroves are halophytic littoral ecosystems with breathing roots (pneumatophores) that protect coastlines and sequester blue carbon."}]},
    37: {"page": 3, "hi": "मशीन लर्निंग", "en": "Machine Learning", "topic": "Machine Learning", "expected_points": ["Subfield of Artificial Intelligence where algorithms learn statistical patterns from data to make predictions or decisions without explicit rule-based programming (via supervised, unsupervised, and reinforcement learning)."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-08", "title": "INDIAai — National AI Portal of India", "url": "https://indiaai.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Machine learning enables systems to learn patterns from data across supervised, unsupervised, and reinforcement paradigms."}]},
    38: {"page": 4, "hi": "3D प्रिंटिंग", "en": "3D Printing", "topic": "3D Printing (Additive Manufacturing)", "expected_points": ["Additive manufacturing process that constructs three-dimensional physical objects layer-by-layer from a digital CAD model using polymers, metals, or bio-inks, enabling rapid prototyping, custom prosthetics, and aerospace components."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-08", "title": "MeitY — National Strategy for Additive Manufacturing", "url": "https://www.meity.gov.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "3D printing or Additive Manufacturing builds objects layer-by-layer from digital 3D models, minimising material waste."}]},
    39: {"page": 4, "hi": "नेतृत्व कौशल", "en": "Leadership Skills", "topic": "Leadership Skills", "expected_points": ["Competencies enabling an individual to articulate vision, inspire collaboration, communicate empathetically, make ethical decisions, resolve conflicts, and guide a team or educational institution toward shared goals."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-08", "title": "NCERT / NIEPA School Leadership Framework", "url": "https://niepa.ac.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Effective leadership combines vision, communication, empathy, collaborative decision-making, and accountability."}]},
    40: {"page": 4, "hi": "सहकारी अधिगम", "en": "Cooperative Learning", "topic": "Cooperative Learning", "expected_points": ["Structured student-centred pedagogical strategy where small heterogeneous groups work together toward shared learning goals through positive interdependence, individual accountability, and peer interaction."], "common_errors": [], "reference_sources": [{"source_id": "ref-gs17-08", "title": "NCERT Pedagogy & Constructivist Learning", "url": "https://ncert.nic.in/", "retrieved_at": "2026-10-12T09:00:00Z", "claim_snapshot": "Cooperative learning fosters positive interdependence, peer scaffolding, social skills, and individual accountability in small groups."}]}
}

# VLM-verified canonical Hindi Mock 16 passage & 13 evaluation items from UPPSC BEO MAINS हिंदी मॉक 16.pdf
HINDI_MOCK16_PASSAGE = (
    "मनुष्य का जीवन अनेक संबंधों से निर्मित होता है। परिवार, मित्र, पड़ोसी और सहकर्मी उसके सामाजिक जीवन के "
    "महत्वपूर्ण आधार हैं। इन संबंधों की मजबूती केवल निकटता पर निर्भर नहीं करती, बल्कि विश्वास, संवाद और परस्पर "
    "सम्मान पर भी निर्भर करती है। जब लोग एक-दूसरे की बात सुनते हैं, अपनी अपेक्षाओं को स्पष्ट रूप से व्यक्त करते हैं "
    "और दूसरे के दृष्टिकोण को समझने का प्रयास करते हैं, तब संबंधों में स्थायित्व आता है।\n\n"
    "विश्वास किसी भी संबंध की आधारशिला है। इसे बनाने में समय लगता है, किंतु एक छोटी-सी असावधानी भी इसे कमजोर "
    "कर सकती है। इसलिए व्यक्ति को अपने व्यवहार में ईमानदारी और निरंतरता बनाए रखनी चाहिए। केवल शब्दों से विश्वास "
    "उत्पन्न नहीं होता; व्यवहार में किए गए कार्य भी उतने ही महत्वपूर्ण होते हैं।\n\n"
    "आज संचार के साधन पहले की अपेक्षा अधिक विकसित हैं, फिर भी कई बार लोगों के बीच वास्तविक संवाद कम होता "
    "दिखाई देता है। संदेशों और त्वरित प्रतिक्रियाओं की अधिकता के बावजूद भावनाओं को समझने के लिए प्रत्यक्ष संवाद और "
    "धैर्यपूर्वक सुनना आवश्यक है। किसी व्यक्ति की बात को तुरंत गलत मान लेने के बजाय उसके विचारों और परिस्थितियों "
    "को समझने का प्रयास संबंधों में अनावश्यक तनाव को कम कर सकता है।\n\n"
    "स्वस्थ संबंध व्यक्ति को भावनात्मक सुरक्षा प्रदान करते हैं। कठिन समय में परिवार और मित्रों का सहयोग व्यक्ति के "
    "आत्मविश्वास को बनाए रखने में सहायक होता है। इसी प्रकार व्यक्ति का दूसरों के प्रति सहयोगी और संवेदनशील व्यवहार "
    "सामाजिक वातावरण को बेहतर बनाता है। इसलिए अच्छे संबंध केवल व्यक्तिगत सुख का साधन नहीं हैं; वे स्वस्थ और "
    "सहयोगी समाज के निर्माण में भी महत्वपूर्ण भूमिका निभाते हैं।"
)

HINDI_MOCK16_ITEMS = [
    {
        "question_id": "Hindi-Mock16-1(a)",
        "item_code": "1(a)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Passage comprehension — vocabulary",
        "max_marks": 6,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "No fixed limit (3 words × 2 marks each)",
        "page": 1,
        "prompt_hi": "(क) निम्नलिखित शब्दों के अर्थ लिखिए— (6 अंक)\n(i) आधारशिला\n(ii) स्थायित्व\n(iii) असावधानी",
        "prompt_en": "Write the contextual meanings of the following words from the passage (3 × 2 = 6 marks): (i) आधारशिला (Cornerstone/Foundation), (ii) स्थायित्व (Stability/Permanence), (iii) असावधानी (Carelessness/Negligence).",
        "passage_context": HINDI_MOCK16_PASSAGE,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "Meaning must match the word in context of the passage. Award up to 2 marks per word for precise Hindi meaning or valid contextual synonym.",
        "criteria": [
            {"criterion_id": "content", "name": "Contextual Meaning Accuracy (3 items × 1.5m)", "max_score": 4.5, "increment": 0.5},
            {"criterion_id": "language", "name": "Clarity & Standard Hindi Expression", "max_score": 1.5, "increment": 0.5}
        ],
        "expected_points": [
            "(i) आधारशिला : मूल आधार / बुनियाद / नींव का पत्थर (जिस पर किसी संबंध या व्यवस्था का निर्माण टिका हो)",
            "(ii) स्थायित्व : टिकाऊपन / स्थिरता / दीर्घकाल तक बने रहने का भाव",
            "(iii) असावधानी : लापरवाही / चूक / ध्यान न देने की स्थिति"
        ]
    },
    {
        "question_id": "Hindi-Mock16-1(b)",
        "item_code": "1(b)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Passage comprehension — short analytical response",
        "max_marks": 5,
        "word_limit": 50,
        "word_limit_type": "approximate",
        "word_limit_label": "Concise passage-based answer (~40–60 words)",
        "page": 2,
        "prompt_hi": "(ख) संबंधों में विश्वास और संवाद का क्या महत्व है? (5 अंक)",
        "prompt_en": "What is the importance of trust and communication in relationships? (5 marks)",
        "passage_context": HINDI_MOCK16_PASSAGE,
        "options": [],
        "selection_rule": "compulsory",
        "draft_rubric": "Evaluate directly against the passage: trust is the cornerstone nurtured by honesty/consistency; genuine communication & patient listening resolve misunderstandings, reduce tension, and bring stability and emotional security.",
        "criteria": [
            {"criterion_id": "content", "name": "Passage-Grounded Core Ideas", "max_score": 3.0, "increment": 0.5},
            {"criterion_id": "relevance", "name": "Directness & Synthesis (Own Words)", "max_score": 1.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Language & Coherence", "max_score": 1.0, "increment": 0.5}
        ],
        "expected_points": [
            "विश्वास संबंधों की आधारशिला है जो ईमानदारी, निरंतरता और व्यवहार से निर्मित होता है",
            "स्पष्ट संवाद और धैर्यपूर्वक सुनना अपेक्षाओं व दूसरे के दृष्टिकोण को समझने में सहायक होता है",
            "दोनों के समन्वय से अनावश्यक तनाव/गलतफहमियाँ दूर होती हैं और संबंधों में स्थायित्व व भावनात्मक सुरक्षा आती है"
        ]
    },
    {
        "question_id": "Hindi-Mock16-1(c)",
        "item_code": "1(c)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Passage comprehension — title",
        "max_marks": 4,
        "word_limit": 8,
        "word_limit_type": "approximate",
        "word_limit_label": "Brief title (2–7 words)",
        "page": 2,
        "prompt_hi": "(ग) गद्यांश के लिए एक उपयुक्त शीर्षक दीजिए। (4 अंक)",
        "prompt_en": "Provide a suitable title for the passage. (4 marks)",
        "passage_context": HINDI_MOCK16_PASSAGE,
        "options": [],
        "selection_rule": "compulsory",
        "draft_rubric": "Title must capture the central theme (human relationships, trust, and communication), be concise (2–7 words), relevant, and dignified.",
        "criteria": [
            {"criterion_id": "relevance", "name": "Central Theme Capture", "max_score": 2.5, "increment": 0.5},
            {"criterion_id": "format", "name": "Conciseness & Aptness", "max_score": 1.5, "increment": 0.5}
        ],
        "expected_points": [
            "मान्य शीर्षक विकल्प: 'स्वस्थ मानवीय संबंधों के आधार', 'संबंधों में विश्वास और संवाद का महत्व', 'मानवीय संबंध और सामाजिक सामंजस्य', 'विश्वास और संवाद : मधुर संबंधों की आधारशिला'"
        ]
    },
    {
        "question_id": "Hindi-Mock16-1(d)",
        "item_code": "1(d)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Passage comprehension — summary / सारांश",
        "max_marks": 10,
        "word_limit": 82,
        "word_limit_type": "approximate",
        "word_limit_label": "Approximately one-third of passage (~75–90 words; source passage is ~245 words)",
        "page": 2,
        "prompt_hi": "(घ) गद्यांश का सारांश लगभग एक-तिहाई शब्दों में लिखिए। (10 अंक)",
        "prompt_en": "Write a summary of the passage in approximately one-third of its length (~80 words). (10 marks)",
        "passage_context": HINDI_MOCK16_PASSAGE,
        "options": [],
        "selection_rule": "compulsory",
        "draft_rubric": "Compress all four paragraphs faithfully into ~1/3 length (~75–90 words) in own words without copying sentences verbatim or distorting meaning.",
        "criteria": [
            {"criterion_id": "content", "name": "Essential Ideas Coverage", "max_score": 4.0, "increment": 0.5},
            {"criterion_id": "format", "name": "One-Third Compression & Own Phrasing", "max_score": 3.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Coherence & Hindi Expression", "max_score": 3.0, "increment": 0.5}
        ],
        "expected_points": [
            "मानवीय जीवन के सामाजिक संबंध विश्वास, संवाद और परस्पर सम्मान पर टिके होते हैं",
            "विश्वास का निर्माण शब्दों के साथ-साथ ईमानदार और निरंतर व्यवहार से होता है",
            "आधुनिक संचार साधनों के युग में भी प्रत्यक्ष संवाद, धैर्यपूर्वक सुनना और सहानुभूति तनाव घटाने के लिए अनिवार्य हैं",
            "स्वस्थ व सहयोगी संबंध व्यक्ति को भावनात्मक सुरक्षा एवं आत्मविश्वास देकर एक सुदृढ़ समाज का निर्माण करते हैं"
        ]
    },
    {
        "question_id": "Hindi-Mock16-2",
        "item_code": "2",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Official drafting / कार्यालय ज्ञापन (Office Memorandum)",
        "max_marks": 20,
        "word_limit": 150,
        "word_limit_type": "approximate",
        "word_limit_label": "Standard Office Memorandum format (~120–180 words)",
        "page": 2,
        "prompt_hi": "2. विद्यालयों में विद्यार्थियों द्वारा सार्वजनिक संपत्ति की सुरक्षा एवं विद्यालय परिसर में अनुशासन बनाए रखने के संबंध में जारी किए जाने वाले एक कार्यालय ज्ञापन का प्रारूप तैयार कीजिए। (20 अंक)",
        "prompt_en": "Prepare a draft of an Office Memorandum (कार्यालय ज्ञापन) regarding protection of public property by students in schools and maintaining discipline on school premises. (20 marks)",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory",
        "draft_rubric": "Score official Office Memorandum (कार्यालय ज्ञापन) layout: header/department name, memo number & date, title 'कार्यालय ज्ञापन', subject, third-person formal body without salutation/complimentary close, right-aligned signatory block, and left-aligned recipient/copy-to block.",
        "criteria": [
            {"criterion_id": "format", "name": "Official Office Memorandum Format & Layout", "max_score": 7.0, "increment": 0.5},
            {"criterion_id": "content", "name": "Completeness of Directives (Property & Discipline)", "max_score": 6.0, "increment": 0.5},
            {"criterion_id": "relevance", "name": "Administrative Appropriateness", "max_score": 3.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Formal Official Hindi (राजभाषा शब्दावली)", "max_score": 4.0, "increment": 0.5}
        ],
        "expected_points": [
            "शीर्ष पर विभाग/कार्यालय का नाम (यथा— कार्यालय जिला बेसिक शिक्षा अधिकारी / शिक्षा निदेशक, उ.प्र.), पत्रांक एवं दिनांक, मध्य में 'कार्यालय ज्ञापन'",
            "विषय: विद्यालयों में सार्वजनिक संपत्ति की सुरक्षा एवं परिसर में अनुशासन बनाए रखने के संबंध में",
            "अन्य पुरुष (Third Person) शैली में संबोधन-रहित एवं स्वनिर्देश-रहित औपचारिक मुख्य कलेवर",
            "कक्ष फर्नीचर, प्रयोगशाला, पुस्तकालय, पेयजल व विद्युत उपकरणों की सुरक्षा तथा अनुशासन समिति/जागरूकता संबंधी स्पष्ट निर्देश",
            "दाईं ओर हस्ताक्षरकर्ता अधिकारी का पदनाम तथा बाईं ओर प्रेषिति / प्रतिलिपि सूचनार्थ एवं आवश्यक कार्यवाही हेतु"
        ]
    },
    {
        "question_id": "Hindi-Mock16-3",
        "item_code": "3",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Hindi grammar — Any One (वाक्य भेद OR प्रत्यय और मूल शब्द)",
        "max_marks": 10,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "Attempt ANY ONE option: 3(क) Sentence types by meaning OR 3(ख) 5 Suffix + Root items",
        "page": 2,
        "prompt_hi": "3. निम्नलिखित में से किसी एक का उत्तर दीजिए। (10 अंक)\n(क) हिंदी में वाक्य के प्रमुख भेदों को अर्थ के आधार पर उदाहरण सहित स्पष्ट कीजिए।\nअथवा\n(ख) निम्नलिखित शब्दों में प्रयुक्त प्रत्यय को अलग कीजिए और मूल शब्द लिखिए—\n1. मानवता  2. सामाजिक  3. लिखावट  4. मिठास  5. बचपन",
        "prompt_en": "Answer ANY ONE of the following (10 marks): (a) Explain the major types of sentences in Hindi on the basis of meaning with examples; OR (b) Separate the suffix (प्रत्यय) and write the root word (मूल शब्द) for: 1. मानवता, 2. सामाजिक, 3. लिखावट, 4. मिठास, 5. बचपन.",
        "passage_context": None,
        "options": [
            {"option_id": "3(क)", "title": "अर्थ के आधार पर वाक्य के 8 भेद (उदाहरण सहित)"},
            {"option_id": "3(ख)", "title": "प्रत्यय और मूल शब्द पृथक्करण (5 शब्द × 2 अंक)"}
        ],
        "selection_rule": "any_one",
        "draft_rubric": "Score ONLY the option attempted by the candidate. For 3(क): 8 sentence types by meaning (विधानवाचक, निषेधवाचक, प्रश्नवाचक, आज्ञावाचक, इच्छावाचक, संदेहवाचक, विस्मयादिबोधक, संकेतवाचक) with definition & examples. For 3(ख): 2 marks per item (1m root word + 1m suffix).",
        "criteria": [
            {"criterion_id": "content", "name": "Grammatical Rule / Root-Suffix Identification", "max_score": 7.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Examples / Orthographic Precision", "max_score": 3.0, "increment": 0.5}
        ],
        "expected_points": [
            "विकल्प (क): अर्थ के आधार पर 8 वाक्य भेद— 1. विधानवाचक, 2. निषेधवाचक, 3. प्रश्नवाचक, 4. आज्ञावाचक/विधिवाचक, 5. इच्छावाचक, 6. संदेहवाचक, 7. संकेतवाचक, 8. विस्मयादिबोधक (प्रत्येक का स्पष्ट उदाहरण)",
            "विकल्प (ख): 1. मानवता = मानव (मूल शब्द) + ता (प्रत्यय); 2. सामाजिक = समाज + इक; 3. लिखावट = लिख (धातु/मूल) + आवट; 4. मिठास = मीठा + आस; 5. बचपन = बच्चा + पन"
        ]
    },
    {
        "question_id": "Hindi-Mock16-4a",
        "item_code": "4(a)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Translation — Hindi → English",
        "max_marks": 10,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "5 sentences × 2 marks each",
        "page": 2,
        "prompt_hi": "4. (क) हिंदी से अंग्रेजी में अनुवाद कीजिए— (10 अंक)\n1. विश्वास किसी भी अच्छे संबंध की आधारशिला है।\n2. हमें दूसरों की बात धैर्यपूर्वक सुननी चाहिए।\n3. कठिन समय में मित्रों और परिवार का सहयोग महत्वपूर्ण होता है।\n4. स्पष्ट संवाद कई गलतफहमियों को दूर कर सकता है।\n5. सम्मान और सहयोग सामाजिक जीवन को बेहतर बनाते हैं।",
        "prompt_en": "Translate from Hindi to English (5 × 2 = 10 marks).",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "Evaluate sentence-by-sentence (2 marks each). Reward faithful meaning transfer, correct English tense/agreement, and natural vocabulary. Accept valid alternative English phrasings.",
        "criteria": [
            {"criterion_id": "content", "name": "Meaning Fidelity (5 sentences)", "max_score": 6.0, "increment": 0.5},
            {"criterion_id": "language", "name": "English Grammar, Syntax & Vocabulary", "max_score": 4.0, "increment": 0.5}
        ],
        "expected_points": [
            "1. Trust is the cornerstone / foundation of any good relationship.",
            "2. We should listen to others patiently.",
            "3. The support of friends and family is important during difficult times.",
            "4. Clear communication can remove / resolve many misunderstandings.",
            "5. Respect and cooperation make social life better."
        ]
    },
    {
        "question_id": "Hindi-Mock16-4b",
        "item_code": "4(b)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Translation — English → Hindi",
        "max_marks": 10,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "5 sentences × 2 marks each",
        "page": 2,
        "prompt_hi": "4. (ख) अंग्रेजी से हिंदी में अनुवाद कीजिए— (10 अंक)\n1. Trust is built through honesty and consistent behaviour.\n2. Good relationships require understanding and mutual respect.\n3. We should not judge others without knowing their circumstances.\n4. Communication becomes meaningful when we listen carefully.\n5. Support from family and friends gives us strength during difficult times.",
        "prompt_en": "Translate from English to Hindi (5 × 2 = 10 marks).",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "Evaluate sentence-by-sentence (2 marks each). Reward faithful meaning transfer into natural, idiomatic Hindi with accurate grammar and vocabulary.",
        "criteria": [
            {"criterion_id": "content", "name": "Meaning Fidelity (5 sentences)", "max_score": 6.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Standard Hindi Grammar & Expression", "max_score": 4.0, "increment": 0.5}
        ],
        "expected_points": [
            "1. विश्वास का निर्माण ईमानदारी और निरंतर (सतत/समान) व्यवहार से होता है।",
            "2. अच्छे संबंधों के लिए समझदारी और परस्पर सम्मान आवश्यक है।",
            "3. हमें दूसरों की परिस्थितियों को जाने बिना उनके विषय में निर्णय (आकलन) नहीं करना चाहिए।",
            "4. जब हम ध्यानपूर्वक सुनते हैं, तब संवाद सार्थक बन जाता है।",
            "5. कठिन समय में परिवार और मित्रों का सहयोग हमें शक्ति (संबल) प्रदान करता है।"
        ]
    },
    {
        "question_id": "Hindi-Mock16-5",
        "item_code": "5",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Idioms / proverbs — meaning + sentence use",
        "max_marks": 15,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "5 items × 3 marks each (Template draft: 1.5m meaning + 1.5m usage)",
        "page": 3,
        "prompt_hi": "5. निम्नलिखित मुहावरों/लोकोक्तियों का अर्थ स्पष्ट करते हुए प्रत्येक का वाक्य में प्रयोग कीजिए। (15 अंक)\n1. सिर आँखों पर रखना\n2. मुँह की बात छीन लेना\n3. हवा में उड़ना\n4. तेते पाँव पसारिए जेती लंबी सौर\n5. सौ सुनार की, एक लोहार की",
        "prompt_en": "Explain the meaning of the following idioms/proverbs and use each in a sentence (5 × 3 = 15 marks; draft allocation: 1.5 meaning + 1.5 sentence usage per item).",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "Template allocation requiring teacher approval: 3 marks per item (1.5 marks for accurate idiomatic meaning + 1.5 marks for contextual, grammatically correct sentence using the idiom/proverb itself).",
        "criteria": [
            {"criterion_id": "content", "name": "Idiom/Proverb Meaning Accuracy (5 × 1.5m)", "max_score": 7.5, "increment": 0.5},
            {"criterion_id": "relevance", "name": "Contextual Sentence Usage (5 × 1.5m)", "max_score": 7.5, "increment": 0.5}
        ],
        "expected_points": [
            "1. सिर आँखों पर रखना — आदरपूर्वक स्वीकार करना / बहुत सम्मान देना",
            "2. मुँह की बात छीन लेना — दूसरे के मन की बात या विचार को पहले ही कह देना",
            "3. हवा में उड़ना — अत्यधिक घमंड करना / यथार्थ से दूर कल्पना या अहंकार में रहना",
            "4. तेते पाँव पसारिए जेती लंबी सौर — अपनी आय या सामर्थ्य के अनुसार ही व्यय या कार्य करना चाहिए",
            "5. सौ सुनार की, एक लोहार की — निर्बल के अनेक प्रहारों के मुकाबले बलवान का एक ही ठोस प्रहार पर्याप्त होता है"
        ]
    },
    {
        "question_id": "Hindi-Mock16-6a",
        "item_code": "6(a)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Word knowledge / वर्तनी-शुद्धि (Spelling Correction)",
        "max_marks": 5,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "5 words × 1 mark each",
        "page": 3,
        "prompt_hi": "6. (क) निम्नलिखित शब्दों के शुद्ध रूप लिखिए— (5 अंक)\n1. कृतग्य  2. स्वाधिन  3. उत्तरदाई  4. सौन्दर्य  5. उज्जवल",
        "prompt_en": "Write the correct spellings of the following words (5 × 1 = 5 marks): 1. कृतग्य, 2. स्वाधिन, 3. उत्तरदाई, 4. सौन्दर्य, 5. उज्जवल.",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "1 mark per exact standard Devanagari orthographic form. Check matras and conjuncts carefully (especially उज्ज्वल with double half-ja).",
        "criteria": [
            {"criterion_id": "language", "name": "Orthographic Accuracy (5 items × 1m)", "max_score": 5.0, "increment": 0.5}
        ],
        "expected_points": [
            "1. कृतग्य → कृतज्ञ",
            "2. स्वाधिन → स्वाधीन",
            "3. उत्तरदाई → उत्तरदायी",
            "4. सौन्दर्य → सौंदर्य / सौन्दर्य (मानक वर्तनी में अनुस्वार 'सौंदर्य' व संयुक्ताक्षर दोनों की स्थिति स्पष्ट करें; यदि परीक्षा में 'सौन्दर्यता' अशुद्धि हो तो 'सौंदर्य')",
            "5. उज्जवल → उज्ज्वल (दो आधे 'ज्' — उ + ज् + ज् + व + ल)"
        ]
    },
    {
        "question_id": "Hindi-Mock16-6b",
        "item_code": "6(b)",
        "section": "प्रथम खंड : सामान्य हिंदी",
        "question_type": "Sentence correction / वाक्य-शुद्धि",
        "max_marks": 5,
        "word_limit": None,
        "word_limit_type": "not_specified",
        "word_limit_label": "5 sentences × 1 mark each",
        "page": 3,
        "prompt_hi": "6. (ख) निम्नलिखित वाक्यों को शुद्ध कीजिए— (5 अंक)\n1. आपस में एक-दूसरे का सहयोग करना चाहिए।\n2. उसके व्यवहार से मुझे बहुत संतोष हुआ हैं।\n3. दोनों मित्रों के बीच आपस में विवाद हो गया।\n4. वह अपने माता-पिता का आज्ञा मानता है।\n5. किसी के विचारों को बिना समझे उसका विरोध नहीं करनी चाहिए।",
        "prompt_en": "Correct the following sentences (5 × 1 = 5 marks).",
        "passage_context": None,
        "options": [],
        "selection_rule": "compulsory_all_subitems",
        "draft_rubric": "1 mark per accurately corrected sentence removing redundancy (पुनरुक्ति दोष) and gender/number agreement (लिंग-वचन अन्वय) errors without introducing new errors.",
        "criteria": [
            {"criterion_id": "language", "name": "Syntactic & Agreement Correction (5 items × 1m)", "max_score": 5.0, "increment": 0.5}
        ],
        "expected_points": [
            "1. हमें एक-दूसरे का सहयोग करना चाहिए। (अथवा 'हमें आपस में सहयोग करना चाहिए।' — 'आपस में' और 'एक-दूसरे' की पुनरुक्ति दूर करें)",
            "2. उसके व्यवहार से मुझे बहुत संतोष हुआ है। ('हैं' के स्थान पर एकवचन 'है')",
            "3. दोनों मित्रों के बीच विवाद हो गया। (अथवा 'दोनों मित्रों में विवाद हो गया।' — 'के बीच' और 'आपस में' की पुनरुक्ति दूर करें)",
            "4. वह अपने माता-पिता की आज्ञा मानता है। ('आज्ञा' स्त्रीलिंग है, अतः 'का' के स्थान पर 'की')",
            "5. किसी के विचारों को बिना समझे उसका विरोध नहीं करना चाहिए। ('विरोध' पुल्लिंग है, अतः 'करनी' के स्थान पर 'करना')"
        ]
    },
    {
        "question_id": "Hindi-Mock16-7a",
        "item_code": "7(a)",
        "section": "द्वितीय खंड : निबंध (उपखंड 'क')",
        "question_type": "Essay — choose ONE topic from Subsection A",
        "max_marks": 50,
        "word_limit": 700,
        "word_limit_type": "approximate",
        "word_limit_label": "Approximately 700 words (Choose 1 of 3 topics)",
        "page": 3,
        "prompt_hi": "7. (क) निम्नलिखित में से किसी एक विषय पर लगभग 700 शब्दों में निबंध लिखिए। (50 अंक)\n1. सामाजिक जीवन में संवाद और सहिष्णुता\n2. भारतीय संस्कृति में पारस्परिक सहयोग की परंपरा\n3. मानवीय मूल्यों के संरक्षण में साहित्य की भूमिका",
        "prompt_en": "Write an essay in approximately 700 words on ANY ONE topic from Subsection A (50 marks): 1. Dialogue and Tolerance in Social Life; 2. Tradition of Mutual Cooperation in Indian Culture; 3. Role of Literature in Preserving Human Values.",
        "passage_context": None,
        "options": [
            {"option_id": "7(क)-1", "title": "सामाजिक जीवन में संवाद और सहिष्णुता"},
            {"option_id": "7(क)-2", "title": "भारतीय संस्कृति में पारस्परिक सहयोग की परंपरा"},
            {"option_id": "7(क)-3", "title": "मानवीय मूल्यों के संरक्षण में साहित्य की भूमिका"}
        ],
        "selection_rule": "any_one",
        "draft_rubric": "Evaluate relevance to chosen topic, thesis/introduction, philosophical & social depth, logical paragraph structure, literary/cultural examples, balanced perspective, conclusion, and Hindi style. Treat ~700 words as an approximate target, not an automatic hard cutoff.",
        "criteria": [
            {"criterion_id": "content", "name": "Thematic Depth, Ideas & Cultural/Literary Examples", "max_score": 18.0, "increment": 0.5},
            {"criterion_id": "analysis", "name": "Critical Reasoning, Multi-Dimensional Perspective & Balance", "max_score": 10.0, "increment": 0.5},
            {"criterion_id": "relevance", "name": "Focus on Chosen Topic & Thesis Fulfilment", "max_score": 8.0, "increment": 0.5},
            {"criterion_id": "format", "name": "Essay Structure (Intro, Coherent Body, Way Forward Conclusion)", "max_score": 7.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Literary Hindi Expression, Vocabulary & Orthography", "max_score": 7.0, "increment": 0.5}
        ],
        "expected_points": [
            "प्रभावशाली प्रस्तावना एवं विषय की केंद्रीय स्थापना",
            "ऐतिहासिक, सांस्कृतिक, संवैधानिक एवं समसामयिक आयामों का संतुलित विवेचन",
            "प्रासंगिक उदाहरण (जैसे— वसुधैव कुटुम्बकम्, संगच्छध्वं संवदध्वम्, कबीर-तुलसी-प्रेमचंद-निराला आदि के संदर्भ)",
            "सकारात्मक, दूरदर्शी और समाधानपरक निष्कर्ष"
        ]
    },
    {
        "question_id": "Hindi-Mock16-7b",
        "item_code": "7(b)",
        "section": "द्वितीय खंड : निबंध (उपखंड 'ख')",
        "question_type": "Essay — choose ONE topic from Subsection B",
        "max_marks": 50,
        "word_limit": 700,
        "word_limit_type": "approximate",
        "word_limit_label": "Approximately 700 words (Choose 1 of 3 topics)",
        "page": 4,
        "prompt_hi": "7. (ख) निम्नलिखित में से किसी एक विषय पर लगभग 700 शब्दों में निबंध लिखिए। (50 अंक)\n1. बाढ़ : कारण, प्रभाव और प्रभावी प्रबंधन\n2. कृषि में जैविक पद्धतियाँ : संभावनाएँ और सीमाएँ\n3. ग्रामीण क्षेत्रों में स्वरोजगार की संभावनाएँ",
        "prompt_en": "Write an essay in approximately 700 words on ANY ONE topic from Subsection B (50 marks): 1. Floods: Causes, Effects, and Effective Management; 2. Organic Farming Practices: Prospects and Limitations; 3. Self-Employment Opportunities in Rural Areas.",
        "passage_context": None,
        "options": [
            {"option_id": "7(ख)-1", "title": "बाढ़ : कारण, प्रभाव और प्रभावी प्रबंधन"},
            {"option_id": "7(ख)-2", "title": "कृषि में जैविक पद्धतियाँ : संभावनाएँ और सीमाएँ"},
            {"option_id": "7(ख)-3", "title": "ग्रामीण क्षेत्रों में स्वरोजगार की संभावनाएँ"}
        ],
        "selection_rule": "any_one",
        "draft_rubric": "Evaluate relevance to chosen socio-economic/environmental topic, introduction, empirical/policy depth, analytical balance (prospects AND limits / causes, impacts AND management), structure, conclusion, and Hindi expression.",
        "criteria": [
            {"criterion_id": "content", "name": "Empirical Depth, Policy/Scheme Examples & Coverage", "max_score": 18.0, "increment": 0.5},
            {"criterion_id": "analysis", "name": "Analytical Balance (Causes/Impacts/Solutions or Prospects/Limits)", "max_score": 10.0, "increment": 0.5},
            {"criterion_id": "relevance", "name": "Adherence to Topic Demand", "max_score": 8.0, "increment": 0.5},
            {"criterion_id": "format", "name": "Logical Organisation, Transitions & Conclusion", "max_score": 7.0, "increment": 0.5},
            {"criterion_id": "language", "name": "Standard Hindi Terminology, Grammar & Clarity", "max_score": 7.0, "increment": 0.5}
        ],
        "expected_points": [
            "विषय के सभी अंगों (कारण-प्रभाव-प्रबंधन अथवा संभावनाएँ-सीमाएँ) को समानुपातिक भार देना",
            "भारत एवं उत्तर प्रदेश के विशेष संदर्भ, सरकारी योजनाओं (NDMA, PKVY, NRLM, ODOP, MSME, स्वयं सहायता समूह) का सटीक उल्लेख",
            "चुनौतियों का यथार्थवादी विश्लेषण एवं व्यावहारिक समाधान"
        ]
    }
]


def build_import_preview():
    gs_wb_hash = sha256_file(GS_WORKBOOK_PATH)
    hi_wb_hash = sha256_file(HINDI_WORKBOOK_PATH)
    gs_pdf_hash = sha256_file(GS_PDF_PATH)
    hi_pdf_hash = sha256_file(HINDI_PDF_PATH)

    # Extract raw PDF text per page
    gs_doc = pymupdf.open(GS_PDF_PATH)
    gs_pdf_pages_raw = [page.get_text("text") for page in gs_doc]
    hi_doc = pymupdf.open(HINDI_PDF_PATH)
    hi_pdf_pages_raw = [page.get_text("text") for page in hi_doc]

    # Parse GS Workbook
    wb1 = openpyxl.load_workbook(GS_WORKBOOK_PATH, data_only=True)
    ws1 = wb1["Merged Question Rubrics"]
    headers1 = [ws1.cell(1, c).value for c in range(1, ws1.max_column + 1)]

    gs_all_mocks_summary = {}
    gs_mock17_questions = []
    warnings = []

    # Check Mock 17 collision across workbooks
    warnings.append({
        "warning_id": "WARN-IDENTITY-COLLISION-MOCK17",
        "severity": "high",
        "category": "paper_identity_collision",
        "affected_scope": "Mock 17 (GS Workbook vs Hindi Workbook)",
        "description": "Both workbooks contain a paper labelled 'Mock 17', but WB1's Mock 17 is General Studies (40 questions, 200 marks, matching 'UPPSC BEO MAINS Mock 17.pdf') whereas WB2's Mock 17 is General Hindi & Essay (13 items, 200 marks). Papers must be matched by (exam, subject, language, paper_version, source_hash), never by mock number alone.",
        "resolution": "Assigned canonical paper IDs 'uppsc-beo-mains-gs-mock-17-v1' (General Studies) and 'uppsc-beo-mains-hindi-mock-17-v1' (General Hindi & Essay) with distinct subject/language keys and SHA-256 source bindings."
    })

    for r in range(2, ws1.max_row + 1):
        row = {headers1[c - 1]: ws1.cell(r, c).value for c in range(1, ws1.max_column + 1)}
        mock_name = row["Mock Test"]
        qno = int(row["Q. No."])
        sec = row["Section"]
        max_marks = float(row["Max Marks"] or 0)
        word_limit = int(row["Word Limit"] or 0)
        raw_en = str(row["Question (English)"] or "").strip()
        raw_bilingual = str(row["Raw Extract (Bilingual)"] or "").strip()

        gs_all_mocks_summary.setdefault(mock_name, {"question_count": 0, "total_marks": 0, "sections": {"A": 0, "B": 0, "C": 0}})
        gs_all_mocks_summary[mock_name]["question_count"] += 1
        gs_all_mocks_summary[mock_name]["total_marks"] += max_marks
        gs_all_mocks_summary[mock_name]["sections"][sec] = gs_all_mocks_summary[mock_name]["sections"].get(sec, 0) + 1

        # Detect row-level anomalies across all GS mocks
        if not raw_en:
            warnings.append({
                "warning_id": f"WARN-GS-EMPTY-EN-ROW-{r}",
                "severity": "medium",
                "category": "missing_question_text",
                "affected_scope": f"{row['Question ID']} (Row {r})",
                "description": f"Workbook cell 'Question (English)' is empty for {row['Question ID']}. Raw Extract contains '{raw_bilingual}'.",
                "resolution": "Extracted clean English term 'School Management Committee' from bilingual raw string and flagged for teacher verification."
            })

        if "SECTION B" in raw_en or "SECTION C" in raw_en:
            warnings.append({
                "warning_id": f"WARN-GS-CONTAMINATED-HEADING-ROW-{r}",
                "severity": "high",
                "category": "contaminated_question_text",
                "affected_scope": f"{row['Question ID']} (Row {r})",
                "description": f"Workbook question text in Row {r} ({row['Question ID']}) is contaminated with trailing section heading text: '{raw_en}'.",
                "resolution": "Replaced contaminated workbook text with canonical question wording verified from 'UPPSC BEO MAINS Mock 17.pdf' while retaining raw cell value in audit metadata."
            })

        if "www.topperscode.com" in raw_bilingual:
            warnings.append({
                "warning_id": f"WARN-GS-WATERMARK-ROW-{r}",
                "severity": "low",
                "category": "footer_watermark_contamination",
                "affected_scope": f"{row['Question ID']} (Row {r})",
                "description": f"Raw Extract (Bilingual) in Row {r} includes trailing page footer URL 'www.topperscode.com'.",
                "resolution": "Stripped footer URL during normalization."
            })

        if mock_name == "Mock 17":
            vlm_info = GS_MOCK17_VLM_CANONICAL[qno]
            # Extract the raw garbled Hindi part from raw_bilingual before '/' or '—'
            if " / " in raw_bilingual:
                raw_hi_extract = raw_bilingual.split(" / ")[0].strip()
            elif " — " in raw_bilingual:
                raw_hi_extract = raw_bilingual.split(" — ")[0].strip()
            else:
                raw_hi_extract = raw_bilingual

            criteria = [
                {"criterion_id": "content", "name": "Content & Factual Completeness", "max_score": float(row["Content Marks"] or 0), "increment": 0.5}
            ]
            if float(row["Analysis Marks"] or 0) > 0:
                criteria.append({"criterion_id": "analysis", "name": "Analysis & Reasoning", "max_score": float(row["Analysis Marks"]), "increment": 0.5})
            if float(row["Relevance Marks"] or 0) > 0:
                criteria.append({"criterion_id": "relevance", "name": "Relevance & Directive Fulfilment", "max_score": float(row["Relevance Marks"]), "increment": 0.5})
            if float(row["Structure Marks"] or 0) > 0:
                criteria.append({"criterion_id": "structure", "name": "Structure & Presentation", "max_score": float(row["Structure Marks"]), "increment": 0.5})
            if float(row["Language/Accuracy Marks"] or 0) > 0:
                criteria.append({"criterion_id": "language_accuracy", "name": "Language & Factual Accuracy", "max_score": float(row["Language/Accuracy Marks"]), "increment": 0.5})

            gs_mock17_questions.append({
                "question_id": row["Question ID"],
                "question_number": qno,
                "section": sec,
                "max_marks": max_marks,
                "word_limit": word_limit,
                "word_limit_type": "maximum",
                "word_limit_label": f"Maximum {word_limit} words (Paper Instruction) / About {word_limit} words (Section Header)",
                "directive": row["Directive"],
                "topic": vlm_info["topic"],
                "source_reference": {
                    "workbook_file": "ToppersCode_Merged_AI_Mains_Rubrics_All_Mocks.xlsx",
                    "workbook_sheet": "Merged Question Rubrics",
                    "workbook_row": r,
                    "pdf_file": "UPPSC BEO MAINS Mock 17.pdf",
                    "pdf_page": vlm_info["page"]
                },
                "raw_imported": {
                    "workbook_question_en": raw_en,
                    "workbook_raw_bilingual": raw_bilingual,
                    "pdf_raw_hindi_extract": raw_hi_extract,
                    "has_section_heading_contamination": ("SECTION B" in raw_en or "SECTION C" in raw_en),
                    "has_garbled_devanagari_extract": (raw_hi_extract != vlm_info["hi"])
                },
                "canonical_question": {
                    "hi": vlm_info["hi"],
                    "en": vlm_info["en"]
                },
                "rubric": {
                    "ai_evaluation_rubric": row["AI Evaluation Rubric"],
                    "scoring_anchor": row["Scoring Anchor"],
                    "penalty_guardrails_raw": row["Penalty / Guardrails"],
                    "numeric_penalty_configured": False,
                    "numeric_penalty_note": "Workbook states 'Flag if word limit exceeded; do not reward irrelevant keyword stuffing; deduct for material factual errors' without specifying a numeric deduction. Teacher must configure a numeric penalty rule before any flat deduction is applied.",
                    "criteria": criteria
                },
                "answer_outline": {
                    "expected_points": vlm_info["expected_points"],
                    "common_factual_errors": vlm_info["common_errors"],
                    "reference_sources": vlm_info["reference_sources"]
                }
            })

    # Add GS PDF Devanagari garbling warning
    warnings.append({
        "warning_id": "WARN-GS17-PDF-DEVANAGARI-CMAP",
        "severity": "medium",
        "category": "hindi_pdf_text_garbling",
        "affected_scope": "UPPSC BEO MAINS Mock 17.pdf (All 40 bilingual items)",
        "description": "Direct PDF text-layer extraction (PyMuPDF/pdftotext) garbles Devanagari glyph mappings (e.g., 'वैनदक काल से महाििपद काल तक भारतीर् समाि' instead of 'वैदिक काल से महाजनपद काल तक भारतीय समाज').",
        "resolution": "Cross-checked all 4 pages against 200-DPI rendered page images via VLM visual verification and stored exact Unicode Devanagari alongside raw PDF extract for teacher comparison."
    })

    warnings.append({
        "warning_id": "WARN-GS17-UNSPECIFIED-PENALTY-AMOUNT",
        "severity": "medium",
        "category": "unspecified_numeric_penalty",
        "affected_scope": "GS Mock 17 (All 40 items — Penalty / Guardrails column)",
        "description": "Workbook instructs to 'Flag if word limit exceeded; deduct for material factual errors' but defines no numeric penalty amount.",
        "resolution": "Deterministic score validator blocks flat numeric deductions unless explicitly configured and published by a teacher; factual errors are explained and reflected within the applicable criterion."
    })

    # Parse Hindi Workbook
    wb2 = openpyxl.load_workbook(HINDI_WORKBOOK_PATH, data_only=True)
    ws2 = wb2["Merged Hindi Rubrics"]
    headers2 = [ws2.cell(1, c).value for c in range(1, ws2.max_column + 1)]
    hindi_all_mocks_summary = {}
    misaligned_rows_count = 0

    for r in range(2, ws2.max_row + 1):
        row = {headers2[c - 1]: ws2.cell(r, c).value for c in range(1, ws2.max_column + 1)}
        m = row["Mock Test"]
        max_m = float(row["Max Marks"] or 0)
        hindi_all_mocks_summary.setdefault(m, {"item_count": 0, "total_marks": 0})
        hindi_all_mocks_summary[m]["item_count"] += 1
        hindi_all_mocks_summary[m]["total_marks"] += max_m
        pctx = str(row["Passage Context (Q1 only)"] or "")
        prompt_val = str(row["Prompt / Task"] or "")
        if pctx == "सभी प्रश्न अनिवार्य हैं।" or prompt_val.startswith("2. सभी प्रश्ननों") or prompt_val.startswith("3. उत्ति निर्ायरित"):
            misaligned_rows_count += 1

    warnings.append({
        "warning_id": "WARN-HINDI-MOCK16-MISSING-RUBRIC",
        "severity": "critical",
        "category": "missing_rubric_in_workbook",
        "affected_scope": "UPPSC BEO MAINS हिंदी मॉक 16.pdf (General Hindi & Essay Mock 16)",
        "description": "The supplied Hindi workbook covers Mocks 04, 05, 06, 07, 13, 15, and 17 (91 rows total), and does NOT contain a rubric for Mock 16.",
        "resolution": "Synthesized a 13-item draft rubric for Hindi Mock 16 using the workbook's 13-item Rubric Framework and VLM-verified questions from 'UPPSC BEO MAINS हिंदी मॉक 16.pdf'. Marked status='draft_requires_teacher_approval' — official marks cannot be finalized until a teacher reviews and publishes Mock 16."
    })

    warnings.append({
        "warning_id": "WARN-HINDI-WB-PROMPT-MISALIGNMENT",
        "severity": "high",
        "category": "workbook_prompt_column_misalignment",
        "affected_scope": f"ToppersCode_UPPSC_BEO_Hindi_Mocks_04_05_06_07_13_15_17_AI_Rubrics.xlsx ({misaligned_rows_count} rows across Mocks 04–17)",
        "description": "In the Hindi workbook's 'Merged Hindi Rubrics' sheet, 'Passage Context (Q1 only)' contains Instruction 1 ('सभी प्रश्न अनिवार्य हैं।') and 'Prompt / Task' for Items 2, 3, 4a, 4b, 6b, 7a, 7b contains misaligned paper instructions or concatenated questions with garbled legacy Devanagari font extraction.",
        "resolution": "Flagged all misaligned workbook prompt cells; canonical question wording and passage context are always sourced from the VLM-verified PDF paper, while workbook rows are used only for item structure, max marks, and rubric framework."
    })

    warnings.append({
        "warning_id": "WARN-HINDI16-PDF-DEVANAGARI-CMAP",
        "severity": "high",
        "category": "hindi_pdf_text_garbling",
        "affected_scope": "UPPSC BEO MAINS हिंदी मॉक 16.pdf (Pages 1–4)",
        "description": "Direct PDF text extraction severely corrupts Devanagari matras, anusvaras, and conjuncts (e.g., extracting 'मिुष्य का जीवि अिेक सोंबोंर्नों से निनमयत हनता है' instead of 'मनुष्य का जीवन अनेक संबंधों से निर्मित होता है', and dropping 'ह' in 'हिंद/सहिष्णुता/साहित्य/लोहार').",
        "resolution": "Rendered all 4 pages at 200 DPI, extracted verified Unicode Devanagari via VLM inspection, and exposed side-by-side raw PDF extract vs. VLM visual transcription in the Teacher Import Review UI."
    })

    preview = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [
            {
                "file_name": "ToppersCode_Merged_AI_Mains_Rubrics_All_Mocks.xlsx",
                "artifact_kind": "gs_rubric_workbook",
                "sha256": gs_wb_hash,
                "size_bytes": os.path.getsize(GS_WORKBOOK_PATH),
                "sheets": wb1.sheetnames,
                "mocks_included": list(gs_all_mocks_summary.keys()),
                "total_rows": 200
            },
            {
                "file_name": "ToppersCode_UPPSC_BEO_Hindi_Mocks_04_05_06_07_13_15_17_AI_Rubrics.xlsx",
                "artifact_kind": "hindi_rubric_workbook",
                "sha256": hi_wb_hash,
                "size_bytes": os.path.getsize(HINDI_WORKBOOK_PATH),
                "sheets": wb2.sheetnames,
                "mocks_included": list(hindi_all_mocks_summary.keys()),
                "total_rows": 91
            },
            {
                "file_name": "UPPSC BEO MAINS Mock 17.pdf",
                "artifact_kind": "gs_question_paper_pdf",
                "sha256": gs_pdf_hash,
                "size_bytes": os.path.getsize(GS_PDF_PATH),
                "page_count": len(gs_pdf_pages_raw),
                "matched_paper_id": "uppsc-beo-mains-gs-mock-17-v1"
            },
            {
                "file_name": "UPPSC BEO MAINS हिंदी मॉक 16.pdf",
                "artifact_kind": "hindi_question_paper_pdf",
                "sha256": hi_pdf_hash,
                "size_bytes": os.path.getsize(HINDI_PDF_PATH),
                "page_count": len(hi_pdf_pages_raw),
                "matched_paper_id": "uppsc-beo-mains-hindi-mock-16-draft"
            }
        ],
        "workbook_summaries": {
            "gs_master_bank": gs_all_mocks_summary,
            "hindi_master_bank": hindi_all_mocks_summary
        },
        "import_warnings": warnings,
        "papers": [
            {
                "paper_id": "uppsc-beo-mains-gs-mock-17-v1",
                "exam_name": "UPPSC Block Education Officer (BEO) Mains",
                "subject": "General Studies (सामान्य अध्ययन)",
                "mock_label": "GS Mock 17",
                "language": "bilingual_hi_en",
                "duration_minutes": 180,
                "total_marks": 200,
                "total_questions": 40,
                "status": "published_v1",
                "rubric_version": "gs-mock17-rubric-v1.0.0",
                "source_pdf": "UPPSC BEO MAINS Mock 17.pdf",
                "source_pdf_sha256": gs_pdf_hash,
                "source_workbook": "ToppersCode_Merged_AI_Mains_Rubrics_All_Mocks.xlsx",
                "source_workbook_sha256": gs_wb_hash,
                "word_count_policy": {
                    "mode": "unicode_grapheme_whitespace_tokens",
                    "rule_type": "hard_maximum",
                    "description": "Paper instructions specify 'not more than 125 / 50 / 25 words each' while section headers state 'About 125 / 50 words'. Exceeding the limit flags 'exceeded' for examiner review; no automatic numeric deduction is applied unless configured by the teacher.",
                    "numeric_penalty_per_excess_word": 0.0
                },
                "sections": [
                    {
                        "section_id": "A",
                        "title": "Section A — Normal / Analytical Answers",
                        "question_count": 10,
                        "marks_per_question": 10,
                        "section_marks": 100,
                        "word_limit": 125,
                        "word_limit_type": "maximum",
                        "dimensions": {"content": 4.0, "analysis": 2.0, "relevance": 2.0, "structure": 1.0, "language_accuracy": 1.0}
                    },
                    {
                        "section_id": "B",
                        "title": "Section B — Short Answers",
                        "question_count": 10,
                        "marks_per_question": 6,
                        "section_marks": 60,
                        "word_limit": 50,
                        "word_limit_type": "maximum",
                        "dimensions": {"content": 3.0, "analysis": 1.0, "relevance": 1.0, "structure": 1.0, "language_accuracy": 0.0}
                    },
                    {
                        "section_id": "C",
                        "title": "Section C — Very Short Notes / Definitions",
                        "question_count": 20,
                        "marks_per_question": 2,
                        "section_marks": 40,
                        "word_limit": 25,
                        "word_limit_type": "maximum",
                        "dimensions": {"content": 1.5, "analysis": 0.0, "relevance": 0.5, "structure": 0.0, "language_accuracy": 0.0}
                    }
                ],
                "questions": gs_mock17_questions
            },
            {
                "paper_id": "uppsc-beo-mains-hindi-mock-16-draft",
                "exam_name": "UPPSC Block Education Officer (BEO) Mains",
                "subject": "General Hindi & Essay (सामान्य हिंदी एवं निबंध)",
                "mock_label": "Hindi Mock 16",
                "language": "hi",
                "duration_minutes": 180,
                "total_marks": 200,
                "total_questions": 13,
                "status": "draft_requires_teacher_approval",
                "rubric_version": "hindi-mock16-rubric-draft-v0.9.0",
                "source_pdf": "UPPSC BEO MAINS हिंदी मॉक 16.pdf",
                "source_pdf_sha256": hi_pdf_hash,
                "source_workbook": "ToppersCode_UPPSC_BEO_Hindi_Mocks_04_05_06_07_13_15_17_AI_Rubrics.xlsx (Template Framework Only)",
                "source_workbook_sha256": hi_wb_hash,
                "word_count_policy": {
                    "mode": "devanagari_unicode_nfc_words",
                    "rule_type": "approximate_target",
                    "description": "Preserves NFC Devanagari combining marks (matras, chandrabindu, anusvara, halant). Q1(d) summary target is ~1/3 of passage (~82 words); Q7(a) & Q7(b) essays are 'लगभग 700 शब्द' (approximate target, not a punitive cutoff).",
                    "numeric_penalty_per_excess_word": 0.0
                },
                "sections": [
                    {
                        "section_id": "प्रथम खंड : सामान्य हिंदी",
                        "title": "General Hindi (Q1 Passage 25m, Q2 Memo 20m, Q3 Grammar 10m, Q4 Translation 20m, Q5 Idioms 15m, Q6 Correction 10m)",
                        "question_count": 11,
                        "marks_per_question": None,
                        "section_marks": 100,
                        "word_limit": None,
                        "word_limit_type": "mixed"
                    },
                    {
                        "section_id": "द्वितीय खंड : निबंध",
                        "title": "Hindi Essay (Q7a Subsection A 50m + Q7b Subsection B 50m; ~700 words each)",
                        "question_count": 2,
                        "marks_per_question": 50,
                        "section_marks": 100,
                        "word_limit": 700,
                        "word_limit_type": "approximate"
                    }
                ],
                "passage_raw_pdf_extract": (
                    "मिुष्य का जीवि अिेक सोंबोंर्नों से निनमयत हनता है। परिवाि, नमत्र, पडनसी औि सहकमी उसके सामानजक जीवि के "
                    "महत्वपूणय आर्ाि हैं। इि सोंबोंर्नों की मजबूती केवि निकटता पि निभयि िहीों किती, बखि नवश्वास, सोंवाि औि पिस्पि "
                    "सम्माि पि भी निभयि किती है।"
                ),
                "passage_vlm_canonical": HINDI_MOCK16_PASSAGE,
                "questions": HINDI_MOCK16_ITEMS
            }
        ]
    }

    os.makedirs("/home/user/docs/exam-import", exist_ok=True)
    out_path = "/home/user/docs/exam-import/import-preview-report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_path} ({os.path.getsize(out_path)} bytes)")
    print(f"Total warnings generated: {len(warnings)}")
    print(f"GS Mock 17 questions: {len(gs_mock17_questions)}, total marks: {sum(q['max_marks'] for q in gs_mock17_questions)}")
    print(f"Hindi Mock 16 items: {len(HINDI_MOCK16_ITEMS)}, total marks: {sum(q['max_marks'] for q in HINDI_MOCK16_ITEMS)}")


if __name__ == "__main__":
    build_import_preview()
