## Part 5 — Question Commands & Application Responses (Agent 3: Question Command Agent)

Each itinerary below received the same **15-question session** -- one real question per category-diverse probe (justification, contingency, alternatives, expansion, practicalities, suitability, plus one edge-case honesty probe), run against the **unmodified itinerary Agent 2 built in Phase 1** (no edits applied), through the app's actual Gemini-backed intent classifier (`phase4/intent_classifier.py`) and explanation engine (`phase4/explain_engine.py`, which itself performs real RAG lookups against Phase 1's ChromaDB) -- not simulated. Every question names a venue that is actually on that itinerary.

### Itinerary 1: Food-only city crawl — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Janpath New Mini Market for Day 1? | EXPLAIN | True | Janpath New Mini Market is one of Delhi's best-known street-shopping stretches, offering a variety of goods like handicrafts, silver jewellery, and souvenirs. Its position between Connaught Place and the museum district also makes it an easy walking add-on for visitors. |
| 2 | justification | Why is Indian Accent scheduled in the morning instead of another time of day? | EXPLAIN | True | The provided sources do not contain any information about Indian Accent or why it would be scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Janpath New Mini Market, Indian Accent, Khan Market, Andhra Bhawan Canteen, Nando's, Bukhara. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer this question as the provided sources do not contain any information about what happens if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Khan Market is closed for a public holiday? | EXPLAIN | True | The provided text does not contain information about what happens to your plan if Khan Market is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Lajpat Nagar Central Market on Day 2? | EXPLAIN | True | If you are looking for alternative shopping areas, the three main markets in the nearby Delhi area are Khanna Market, Khan Market, and Meherchand Market. Additionally, you can visit the historic street market square of Chandni Chowk in Old Delhi. |
| 7 | alternatives | If Dilli Haat turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Janpath New Mini Market that isn't on the itinerary? | EXPLAIN | True | Near the Janpath market area, you can visit the state emporia complex on nearby Baba Kharak Singh Marg for fixed-price government-certified handicrafts. Additionally, the Handloom House (Handloom Haat) located behind the Janpath market showcases hand-woven fabrics from around the country. |
| 10 | practicalities | How much does it cost to visit Janpath New Mini Market? | EXPLAIN | True | It costs nothing to visit the Janpath market area, as the entry fee is completely free. Visitors can explore the stalls and shop for items like handicrafts, jewelry, and textiles, though you should expect to bargain on prices. |
| 11 | practicalities | What's the best time of day to visit Janpath New Mini Market? | EXPLAIN | True | The best time to visit the Janpath market is in the late afternoon. Additionally, the ideal months to go are between October and March to comfortably enjoy the open-air stalls. |
| 12 | practicalities | How do I get from Karim's to Janpath New Mini Market? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain any information about Karim's or how to travel from it to the Janpath New Mini Market. |
| 13 | suitability | Is Janpath New Mini Market suitable for elderly travellers? | EXPLAIN | True | The Janpath Market features open-air street stalls with bargaining as standard practice. Its position makes it an easy walking add-on for visitors, with the Janpath Metro Station exiting directly onto the market stretch. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Indian Accent within walking distance of my hotel? | EXPLAIN | True | The provided source excerpts do not mention Indian Accent or its location relative to your hotel. |

### Itinerary 2: History-only deep dive — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected due to its proximity to the Nizamuddin Dargah, as burial near the celebrated Sufi saint Nizamuddin Auliya was considered auspicious. Additionally, as a UNESCO World Heritage Site and the first grand garden-tomb on the Indian subcontinent, it offers a stunning introduction to Mughal architecture that directly influenced the design of the Taj Mahal. |
| 2 | justification | Why is Masala House scheduled in the morning instead of another time of day? | EXPLAIN | True | I'm sorry, but the provided information does not mention Masala House or why it would be scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Masala House, Purana Qila, Nathu Sweets, Karim's, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer this question because the provided text does not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM. |
| 6 | alternatives | What are some alternatives to Guru Kirpa Restaurant on Day 2? | EXPLAIN | True | Instead of Guru Kirpa Restaurant, you can check out Karim's near Jama Masjid, known for its slow-cooked Mughlai signatures like mutton korma and kebabs. Other food options in Old Delhi include the historic Old Kheer Shop, Old Famous Jalebi Wala, Old Ameer Mithai Wala, Pandit Ji Parathe Wale, and Ghantewala. |
| 7 | alternatives | If बाबू राम देवी दयाल turns out to be too crowded, what else could I do instead? | EXPLAIN | True | Based on the provided sources, there is no mention of "बाबू राम देवी दयाल" or any alternative options related to it. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you can find the Dina-panah Citadel (also known as Purana Qila or Old Fort), which Humayun found in 1538. Additionally, the site is close to the Nizamuddin Dargah, the mausoleum of the celebrated Sufi saint Nizamuddin Auliya. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | Visiting Humayun's Tomb costs approximately ₹35 to ₹40 for Indian nationals and around ₹550 to ₹600 for foreign nationals, while children under 15 enter for free. Please note that the site museum may be ticketed separately, and it is a good idea to verify the exact fees locally. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time of day to visit Humayun's Tomb is early morning or during the golden hour before sunset. Additionally, October through March is recommended as the best time of year to visit. |
| 12 | practicalities | How do I get from Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala to Qutab Minar? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain information on how to get from Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala to Qutab Minar. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb features a main tomb enclosure with a pathway leading up to it from the main western entrance, dotted with several smaller monuments. The site includes a Persian charbagh garden with water channels, restored gateways, pavilions, and an interpretation centre at the entrance. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Dilli Haat within walking distance of my hotel? | EXPLAIN | True | The provided excerpts do not mention your hotel or its location, so it is not possible to determine if Dilli Haat is within walking distance. |

### Itinerary 3: Nature-only escape — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is scheduled around morning because one of its signature dishes, nihari, is traditionally a breakfast dish, and the restaurant opens around 9:00 AM. Additionally, for travel itineraries, it slots directly after a visit to the nearby Jama Masjid. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Deer park, The Golden Dragon, Saket District Park. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided excerpts do not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I'm sorry, but the provided information does not mention Indian Accent or what happens to your plan if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to chai point on Day 2? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 7 | alternatives | If Sunder Nursery turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Karim's to Indian Accent? | EXPLAIN | True | The provided excerpts do not contain instructions or information on how to travel from Karim's to Indian Accent. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Deer park within walking distance of my hotel? | EXPLAIN | True | The provided sources do not contain any information about the location of your hotel or whether Deer Park is within walking distance. |

### Itinerary 4: Shopping-only spree — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Chandni Chowk for Day 1? | EXPLAIN | True | Chandni Chowk is one of the oldest and busiest markets in Delhi, established in 1650 by the Mughal Emperor Shah Jahan and designed by his daughter Jahanara. Historically, it was once the grandest Indian market and a significant route for Mughal imperial processions, hosting grand displays of emperors and their entourages. Additionally, the bazaar gained renown for its thriving silver trade, earning it the moniker Silver Street. |
| 2 | justification | Why is Nazeer Foods scheduled in the morning instead of another time of day? | EXPLAIN | True | I cannot answer your question as the provided sources do not mention Nazeer Foods or why it is scheduled at a particular time of day. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Chandni Chowk, Nazeer Foods, V3S Mall, Asharti BBQ Nights, Moti Mahal, Dilli Haat. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided sources do not contain information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if V3S Mall is closed for a public holiday? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 6 | alternatives | What are some alternatives to Barbeque Nation on Day 2? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 7 | alternatives | If Lajpat Nagar Central Market turns out to be too crowded, what else could I do instead? | EXPLAIN | True | You can explore alternative shopping markets in the area like Khanna Market, Khan Market, and Meherchand Market, or visit Chandni Chowk, one of India's largest wholesale markets. Additionally, you can check out nearby places of interest such as the Sai Baba Temple of Lodhi Road, the 16th-century Tomb of Sikander Lodhi in Lodhi Gardens, the India Habitat Centre, or the historic Red Fort. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Chandni Chowk that isn't on the itinerary? | EXPLAIN | True | Near Chandni Chowk, you can visit interesting spots like Dariba Kalan and Gali paranthe walee. Additional nearby sites include the Shri Digambar Jain Lal Mandir Bird Hospital, Shri Shiv Navgrah Mandir Dham, and Shri Gauri Shankar Mandir. |
| 10 | practicalities | How much does it cost to visit Asharti BBQ Nights? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain any information about the cost or existence of Asharti BBQ Nights. |
| 11 | practicalities | What's the best time of day to visit Moti Mahal? | EXPLAIN | True | Moti Mahal was a twin building located at the northern edge of the Red Fort that was demolished during or shortly after the 1857 rebellion. Because it no longer exists, there is no visiting time available for it. |
| 12 | practicalities | How do I get from Make My Lagan to Moti Mahal Delux? | EXPLAIN | True | I am sorry, but the provided sources do not contain any information about how to travel from Make My Lagan to Moti Mahal Delux. |
| 13 | suitability | Is Dilli Haat suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Chandni Chowk within walking distance of my hotel? | EXPLAIN | True | I am unable to answer whether Chandni Chowk is within walking distance of your hotel, as the provided information does not mention your hotel's location. |

### Itinerary 5: Religion-only pilgrimage — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Jama Masjid for Day 1? | EXPLAIN | True | Jama Masjid was chosen because it is one of the largest mosques in India, commissioned by Mughal emperor Shah Jahan, and its position facing the Red Fort anchors the historic core of Old Delhi. |
| 2 | justification | Why is Gurdwara Bangla Sahib scheduled in the morning instead of another time of day? | EXPLAIN | True | Early morning is recommended for visiting Gurdwara Bangla Sahib so you can experience the prayers. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Jama Masjid, Gurdwara Bangla Sahib, Pizza Hut, Gurdwara Rakab Ganj Sahib, Punjab Grill, Gokulam. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided sources do not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Pizza Hut is closed for a public holiday? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 6 | alternatives | What are some alternatives to Kalkaji Mandir on Day 2? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 7 | alternatives | If Sri Sri Radha Parthasarathi Mandir turns out to be too crowded, what else could I do instead? | EXPLAIN | True | You can visit Swaminarayan Akshardham, which features a central dome with murtis of deities like Radha-Krishna, alongside exhibits, a large-format theatre, a boat ride, and a musical fountain. Alternatively, you can visit Gurudwara Bangla Sahib, a prominent Sikh gurudwara featuring a sacred tank, continuous prayer recitations, and a community kitchen serving free vegetarian meals. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Jama Masjid that isn't on the itinerary? | EXPLAIN | True | Jama Masjid is surrounded by the vibrant bazaars and food lanes of the walled city. Additionally, visitors can climb the southern minaret for panoramic views over Old Delhi. |
| 10 | practicalities | How much does it cost to visit Jama Masjid? | EXPLAIN | True | Entering Jama Masjid is free. However, if you wish to take photos or videos, it costs approximately ₹200–₹300, and climbing the southern minaret costs about ₹100. |
| 11 | practicalities | What's the best time of day to visit Jama Masjid? | EXPLAIN | True | The best time to visit Jama Masjid is during the early morning or late afternoon, as well as between October and March. You should plan to avoid Friday midday for your visit. |
| 12 | practicalities | How do I get from Thalairaj Biryani to California Burrito? | EXPLAIN | True | The provided excerpts do not contain any information about Thalairaj Biryani or California Burrito, so there are no details available to explain how to travel between them. |
| 13 | suitability | Is Jama Masjid suitable for elderly travellers? | EXPLAIN | True | Jama Masjid is located about 300 to 500 meters (a 5-minute walk) from the nearest metro station and can be accessed using cycle-rickshaws or autos. While the mosque features a large courtyard and gates, visitors can also climb the ticketed southern minaret for views over Old Delhi. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is St Luke's church within walking distance of my hotel? | EXPLAIN | True | I cannot answer whether St Luke's church is within walking distance of your hotel, as the provided information does not mention St Luke's church or your hotel. |

### Itinerary 6: History + Food — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected due to its close proximity to the Nizamuddin Dargah, as burial near the celebrated Sufi saint was considered auspicious. Additionally, it is the first grand garden-tomb on the Indian subcontinent, serving as a UNESCO World Heritage Site that set a precedent for future Mughal architecture, including the Taj Mahal. |
| 2 | justification | Why is Gulati scheduled in the morning instead of another time of day? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Gulati, Indian Accent, Khan Market, Indian Coffee House, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer your question as the provided sources do not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | The provided source excerpts do not contain any information about Indian Accent or what happens to your plan if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Guru Kirpa Restaurant on Day 2? | EXPLAIN | True | You can try Karim restaurant near Jama Masjid, established in 1913, or visit the old kheer shop in Chandni Chowk for dessert. Other options include the Old Famous Jalebi Wala for jalebis and Old Ameer Mithai Wala for samosas, pakoras, and grilled sandwiches. |
| 7 | alternatives | If Karim's turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If Karim's is too crowded, you can visit the Old Kheer Shop in Chandni Chowk for a dessert delight, or try the famous jalebis at the Old Famous Jalebi Wala, which has been established for over 140 years. You can also head to Old Ameer Mithai Wala near Jama Masjid, which offers samosas, pakoras, and modified grilled sandwiches with a legacy of over 100 years. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you can visit the Dina-panah Citadel (also known as Purana Qila or Old Fort), which Humayun found in 1538. Additionally, the nearby Nizamuddin Dargah shrine complex sits within the dense Nizamuddin Basti, where the lanes are lined with flower sellers, kebab shops, and historic structures. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | To visit Humayun's Tomb, the entry fee is approximately ₹35 to ₹40 for Indian nationals and about ₹550 to ₹600 for foreign nationals. Children under 15 years of age can enter for free, though please note that the site museum may be ticketed separately. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time to visit Humayun's Tomb is either early in the morning or during the golden hour before sunset. Additionally, the ideal months to plan your trip are between October and March. |
| 12 | practicalities | How do I get from Chandni Chowk to Humayun's Tomb? | EXPLAIN | True | To get to Humayun's Tomb, the nearest metro station is Hazrat Nizamuddin on the Pink Line, which is about 1.2 to 1.5 kilometers or an 18-minute walk away (or a short auto ride). You can also take a bus to the Dargah Nizamuddin or Humayun's Tomb stops on Mathura Road, or catch an auto directly from Mathura Road. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb is a UNESCO World Heritage Site featuring a main tomb enclosure set within a restored Persian garden, with several smaller monuments dotting the pathway leading up to it from the main western entrance. The best time to visit is during the cooler months from October through March, and either early in the morning or during the golden hour before sunset. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Gulati within walking distance of my hotel? | EXPLAIN | True | The provided excerpts do not mention Gulati or the location of your hotel, so it is not possible to determine if it is within walking distance. |

### Itinerary 7: Culture + Art — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is The Habitat Hub scheduled in the morning instead of another time of day? | EXPLAIN | True | Based on the provided excerpts, there is no mention of "The Habitat Hub" or why it might be scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, The Habitat Hub, Safdarjung's Tomb, Good Earth, Fat Lulu's, Raj Ghat. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided text does not contain information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Safdarjung's Tomb is closed for a public holiday? | EXPLAIN | True | Safdarjung's Tomb is open daily from sunrise to sunset, and you should verify details locally. |
| 6 | alternatives | What are some alternatives to Shri Krishna Daba on Day 2? | EXPLAIN | True | The provided excerpts do not contain information about alternatives to Shri Krishna Daba or itineraries for Day 2. |
| 7 | alternatives | If Red Fort turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If the Red Fort gets too crowded, you can explore the museums and galleries located inside the colonial-era barracks within the complex. You can also visit the historic commercial spine of Old Delhi, Chandni Chowk, which sits right outside the fort's Lahori Gate. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Moti Mahal to Asharti BBQ Nights? | EXPLAIN | True | The Moti Mahal was a twin building at the northern edge of the Red Fort that was demolished during or shortly after the 1857 rebellion. The provided source excerpts do not contain any information about Asharti BBQ Nights or directions on how to travel there. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Nehru Park within walking distance of my hotel? | EXPLAIN | True | The provided excerpts do not mention your hotel or its distance to Nehru Park. |

### Itinerary 8: Architecture + History + Shopping — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected due to its close proximity to the Nizamuddin Dargah, as burial near the revered Sufi saint was considered auspicious. Additionally, as the first grand garden-tomb on the Indian subcontinent and a UNESCO World Heritage Site, it set a major architectural precedent that directly influenced the design of the Taj Mahal. |
| 2 | justification | Why is Nathu Sweets scheduled in the morning instead of another time of day? | EXPLAIN | True | The provided sources do not explain why Nathu Sweets is scheduled in the morning. However, the market's operating timings run approximately from 8:00 AM to 10:30 PM daily, and the best time to visit the market overall is during late afternoon snack hours. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Nathu Sweets, Purana Qila, Masala House, Khan Market, Indian Accent. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I am sorry, but the provided source excerpts do not contain any information about what happens or what you should do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM. |
| 6 | alternatives | What are some alternatives to Red Fort on Day 2? | EXPLAIN | True | The provided sources do not contain any information about alternatives to the Red Fort on Day 2. |
| 7 | alternatives | If Guru Kirpa Restaurant turns out to be too crowded, what else could I do instead? | EXPLAIN | True | I cannot help you with that, as the provided sources do not contain any information about Guru Kirpa Restaurant. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you can find the Dina-panah Citadel (also known as Purana Qila or Old Fort), which Humayun found in 1538. Additionally, the site is located close to the Nizamuddin Dargah, the mausoleum of the celebrated Sufi saint Nizamuddin Auliya, situated within the dense Nizamuddin Basti. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | The entry fee for Indian nationals is approximately ₹35 to ₹40, while foreign nationals pay around ₹550 to ₹600. Children under 15 can enter for free, though the site museum may be ticketed separately. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time to visit Humayun's Tomb is during the early morning or in the golden hour right before sunset. It is also recommended to visit between October and March. |
| 12 | practicalities | How do I get from Chandni Chowk to Sunehri Masjid? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain information on how to get from Chandni Chowk to Sunehri Masjid. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb is a UNESCO World Heritage Site featuring a main tomb enclosure set within a restored Persian garden, with several smaller monuments dotting the pathway from the main entrance. The site includes an interpretation centre and site museum at the entrance, and offers paid parking for visitors arriving by vehicle. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Gumbad Cafe within walking distance of my hotel? | EXPLAIN | True | I am sorry, but the provided information does not mention the Gumbad Cafe or its location relative to your hotel. |

### Itinerary 9: Family + Nature — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is scheduled in the morning because its signature dish, nihari, is traditionally a breakfast item, and the restaurant opens around 9:00 AM. Additionally, itineraries typically slot a visit here directly after touring the nearby Jama Masjid. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Raj Ghat, Shiv Di Hatti, Nehru Park. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer your question as the provided sources do not contain any information about rain on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I am sorry, but the provided information does not contain any details about Indian Accent or what happens to your plan if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Purana Delhi Darbar on Day 2? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain any information about Purana Delhi Darbar or alternatives for Day 2. |
| 7 | alternatives | If Sunder Nursery turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Karim's to Indian Accent? | EXPLAIN | True | To get there, the quickest way is to simply type the name of the restaurant into maps first. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Raj Ghat within walking distance of my hotel? | EXPLAIN | True | I cannot answer whether Raj Ghat is within walking distance of your hotel, as the provided sources do not contain information about your hotel or its location. |

### Itinerary 10: Food + Shopping + Culture — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Janpath New Mini Market for Day 1? | EXPLAIN | True | Janpath is chosen because its position between Connaught Place and the museum district makes it an easy walking add-on for visitors. Additionally, it hosts one of Delhi's best-known street-shopping stretches, featuring handicrafts, silver and tribal jewellery, embroidered textiles, leather goods, and souvenirs. |
| 2 | justification | Why is Indian Accent scheduled in the morning instead of another time of day? | EXPLAIN | True | Based on the provided information, there is no mention of Indian Accent being scheduled in the morning or at any other time of day. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Janpath New Mini Market, Indian Accent, India Gate, Pindi restaurant Delhi, Have more, Karim's. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided source excerpts do not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if India Gate is closed for a public holiday? | EXPLAIN | True | India Gate is open 24 hours as a public space, though it tends to be very crowded on weekends and national holidays. |
| 6 | alternatives | What are some alternatives to Saint James' Anglican Church on Day 2? | EXPLAIN | True | Alternative locations to explore nearby include the historic Lothian Cemetery, the Nili Chhatri Temple, Ghalib ki Haveli, and the Partition Museum. |
| 7 | alternatives | If Red Fort turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If you want to avoid the crowds at the Red Fort, you can visit the various museums and galleries located within its complex, which are housed in colonial-era barracks. Alternatively, you can explore the historic commercial spine of Old Delhi at Chandni Chowk, which is located right near the fort's Lahori Gate. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Janpath New Mini Market that isn't on the itinerary? | EXPLAIN | True | Near Janpath, you can find the state emporia complex on nearby Baba Kharak Singh Marg, which offers fixed-price government-certified handicrafts. Additionally, Handloom House is located on Janpath behind the Janpath market to showcase hand-woven fabrics from around the country. |
| 10 | practicalities | How much does it cost to visit Janpath New Mini Market? | EXPLAIN | True | Visiting the Janpath market area is completely free of charge, as there is no entry fee. However, any purchases you make on items like handicrafts, jewelry, and clothing will depend on your personal shopping and bargaining. |
| 11 | practicalities | What's the best time of day to visit Janpath New Mini Market? | EXPLAIN | True | The best time to visit Janpath Market is during the late afternoon. Additionally, the months between October and March are recommended for visiting its open-air stalls. |
| 12 | practicalities | How do I get from Chandni Chowk to Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala? | EXPLAIN | True | The provided excerpts do not contain information on how to get to Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala from Chandni Chowk. |
| 13 | suitability | Is Janpath New Mini Market suitable for elderly travellers? | EXPLAIN | True | The Janpath Market features open-air street stalls that require walking, and many stalls are closed or have reduced hours on Sundays. For a more comfortable experience, elderly travelers can visit the nearby state emporia complex on Baba Kharak Singh Marg or the Cottage Emporium, which offer fixed-price, government-certified handicrafts in air-conditioned comfort. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Bukhara within walking distance of my hotel? | EXPLAIN | True | The provided text does not contain information about Bukhara or your hotel's location, so it is impossible to determine if it is within walking distance. |

### Itinerary 11: Religion + History — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected due to its proximity to the Nizamuddin Dargah, as burial near the celebrated Sufi saint Nizamuddin Auliya was considered auspicious. Additionally, as the first grand garden-tomb on the Indian subcontinent, it set a major precedent for subsequent Mughal architecture and directly influenced the design of the Taj Mahal. |
| 2 | justification | Why is Masala House scheduled in the morning instead of another time of day? | EXPLAIN | True | Based on the provided sources, there is no mention of Masala House or why it would be scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Masala House, Purana Qila, Nathu Sweets, Karim's, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | Temperatures moderate during the monsoon season from June to September, but it remains humid. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM (or 9:00 AM to 17:00). |
| 6 | alternatives | What are some alternatives to Indian Accent on Day 2? | EXPLAIN | True | Based on the provided excerpts, there is no mention of Indian Accent or any restaurant alternatives for Day 2. |
| 7 | alternatives | If Bhola dhaba turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If you want an alternative, you can visit the historic Karim restaurant near Jama Masjid, established in 1913. You could also check out the old kheer shop in Chandni Chowk, which has been open since 1880, or try Old Ameer Mithai Wala near Jama Masjid for samosas and pakoras. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you will find the Dina-panah Citadel (also known as Purana Qila or Old Fort), which Humayun found in 1538. Additionally, the site is located close to the Nizamuddin Dargah, the mausoleum of the celebrated Sufi saint Nizamuddin Auliya, situated within the dense Nizamuddin Basti. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | Visiting Humayun's Tomb costs approximately ₹35 to ₹40 for Indian nationals and around ₹550 to ₹600 for foreign nationals, while children under 15 enter for free. Please note that the site museum may be ticketed separately. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time to visit Humayun's Tomb is during the early morning or during the golden hour just before sunset. Additionally, the ideal months to plan your visit are from October to March. |
| 12 | practicalities | How do I get from Big Chill Restaurant to Humayun's Tomb? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain information on how to get to Humayun's Tomb from the Big Chill Restaurant. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb is a UNESCO World Heritage Site featuring a main tomb enclosure with several smaller monuments dotting the pathway leading up to it from the main western entrance. The site includes a Persian charbagh garden with water channels, and visitors can walk from the nearest metro station (Hazrat Nizamuddin) in about 18 minutes or take an auto. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Masala House within walking distance of my hotel? | EXPLAIN | True | I'm sorry, but the provided information does not mention where your hotel is located or anything about Masala House. |

### Itinerary 12: Art + Culture + Food — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is scheduled around morning because one of its signature dishes, the nihari, is traditionally a breakfast dish. Additionally, the restaurant's opening time is approximately 9:00 AM, and its location slots it directly after a morning visit to the Jama Masjid. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Nathu Sweets, Red Fort, Guru Kirpa Restaurant. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I am sorry, but the provided information does not contain details about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I'm sorry, but the provided information does not contain details about Indian Accent or what happens if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Chandni Chowk on Day 2? | EXPLAIN | True | The provided source excerpts do not contain any information about alternatives to Chandni Chowk or plans for Day 2. |
| 7 | alternatives | If Saint James' Anglican Church turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If Saint James' Anglican Church is too crowded, you can visit the nearby Lothian Cemetery, which is located southeast of the church and contains the graves of fallen British soldiers. Alternatively, you can explore the Nili Chhatri Temple, Ghalib ki Haveli, or the Partition Museum. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Chaska Ram to Bukhara? | EXPLAIN | True | I am sorry, but the provided information does not contain details on how to travel from Chaska Ram to Bukhara. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Lajpat Nagar Central Market within walking distance of my hotel? | EXPLAIN | True | I cannot answer your question about whether the Lajpat Nagar Central Market is within walking distance of your hotel, as the provided sources do not contain any information about your hotel's location. |

### Itinerary 13: Nature + Family + Shopping — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is scheduled in the morning because its signature dish, nihari, is traditionally a breakfast item, and the restaurant's daily hours begin around 9:00 AM. Additionally, itinerary planning often slots the visit directly after a stop at the nearby Jama Masjid. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Lajpat Nagar Central Market, Barbeque Nation, Dilli Haat. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer this question as the provided sources do not contain information about rain on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I cannot answer your question because the provided text does not contain any information about Indian Accent or what happens if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Make My Lagan on Day 2? | EDIT | N/A | Not routed to explain() -- classified as EDIT, not EXPLAIN. |
| 7 | alternatives | If Sunder Nursery turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Karim's to Indian Accent? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain instructions on how to travel from Karim's to Indian Accent. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Lajpat Nagar Central Market within walking distance of my hotel? | EXPLAIN | True | I am unable to answer whether Lajpat Nagar Central Market is within walking distance of your hotel, as the provided information does not mention your hotel's location. |

### Itinerary 14: Architecture + Religion — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Jama Masjid for Day 1? | EXPLAIN | True | Jama Masjid is one of the largest mosques in India, featuring striking red sandstone and white marble architecture with a massive courtyard. Its position facing the Red Fort anchors the historic core of Old Delhi, making it a wonderful starting point for exploring the surrounding bazaars and food lanes. |
| 2 | justification | Why is Masala House scheduled in the morning instead of another time of day? | EXPLAIN | True | Based on the provided sources, there is no mention of Masala House or any schedule for it. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Jama Masjid, Masala House, Purana Qila, Nathu Sweets, Gulati, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided source excerpts do not contain any information about what happens if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM. |
| 6 | alternatives | What are some alternatives to Guru Kirpa Restaurant on Day 2? | EXPLAIN | True | For alternative places to eat in Delhi, you can visit the historic Karim restaurant near Jama Masjid, established in 1913. Other great options include the old kheer shop in Chandni Chowk, the Old Famous Jalebi Wala, and Old Ameer Mithai Wala near Jama Masjid, which offers samosas, pakoras, and grilled sandwiches. |
| 7 | alternatives | If Moti Masjid turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If it's too crowded, you can visit Jama Masjid, one of the largest mosques in India commissioned by Emperor Shah Jahan. Alternatively, you can head to Hazrat Nizamuddin Dargah, a revered Sufi shrine complex that features evening qawwali devotional music sessions. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Jama Masjid that isn't on the itinerary? | EXPLAIN | True | Jama Masjid is surrounded by the vibrant bazaars and food lanes of the walled city of Old Delhi. Visitors can also climb the southern minaret to enjoy panoramic views over the area. |
| 10 | practicalities | How much does it cost to visit Jama Masjid? | EXPLAIN | True | Entry to Jama Masjid is free, but there are separate charges for certain activities. If you wish to take photographs or videos, it costs approximately ₹200–₹300, and climbing the southern minaret costs about ₹100. |
| 11 | practicalities | What's the best time of day to visit Jama Masjid? | EXPLAIN | True | The best time to visit Jama Masjid is during the early morning or late afternoon, between the months of October and March. It is also recommended to avoid visiting on Friday midday. |
| 12 | practicalities | How do I get from Gumbad Cafe to बाबू राम देवी दयाल? | EXPLAIN | True | I'm sorry, but the provided information does not contain any details about the Gumbad Cafe or बाबू राम देवी दयाल. |
| 13 | suitability | Is Jama Masjid suitable for elderly travellers? | EXPLAIN | True | Jama Masjid features three great gates and a large courtyard, and visitors can also climb the southern minaret, but it does require walking through the surrounding bazaars and food lanes of Old Delhi. The nearest metro station is about a 300 to 500-meter walk away, though cycle-rickshaws and autos are available. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Dilli Haat within walking distance of my hotel? | EXPLAIN | True | I am unable to answer whether Dilli Haat is within walking distance of your hotel, as my information does not include the location of your hotel. |

### Itinerary 15: History + Culture + Architecture + Food — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected for its proximity to the Nizamuddin Dargah, as burial near the revered Sufi saint Nizamuddin Auliya was considered auspicious. Additionally, it is the first grand garden-tomb on the Indian subcontinent, featuring a Persian charbagh and setting a precedent for subsequent Mughal architecture like the Taj Mahal. |
| 2 | justification | Why is Nathu Sweets scheduled in the morning instead of another time of day? | EXPLAIN | True | The provided excerpts do not schedule Nathu Sweets in the morning; instead, they recommend visiting the market during late afternoon snack hours. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Nathu Sweets, Indian Accent, Khan Market, India Gate, Masala House. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | The provided source excerpts do not contain any information about what to do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I am sorry, but the provided information does not contain any details about Indian Accent or what happens to your plan if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Red Fort on Day 2? | EXPLAIN | True | The provided source excerpts do not contain any information about alternatives to the Red Fort on Day 2. |
| 7 | alternatives | If Guru Kirpa Restaurant turns out to be too crowded, what else could I do instead? | EXPLAIN | True | I cannot answer your question because the provided sources do not contain any information about Guru Kirpa Restaurant. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you can find the Dina-panah Citadel (also known as Purana Qila or Old Fort), which Humayun found in 1538. Additionally, the site is located close to the Nizamuddin Dargah, the mausoleum of the celebrated Sufi saint Nizamuddin Auliya. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | Visiting Humayun's Tomb costs approximately ₹35 to ₹40 for Indian nationals and roughly ₹550 to ₹600 for foreign nationals. Children under 15 can enter for free, though the site museum may require a separate ticket. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time to visit Humayun's Tomb is during the early morning or in the golden hour right before sunset. Additionally, the ideal months for a visit are between October and March. |
| 12 | practicalities | How do I get from Karim's to Partition Museum? | EXPLAIN | True | To reach your location, the quickest way is to simply type the name of the destination into your maps. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb is set within a large garden complex featuring restored pathways and an interpretation center at the entrance. The recommended visit duration is 1.5 to 2 hours, and the best time to visit is during the cooler months from October to March or during the early morning and golden hours. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Chandni Chowk within walking distance of my hotel? | EXPLAIN | True | I'm sorry, but the provided information does not mention where your hotel is located or how far it is from Chandni Chowk. |

### Itinerary 16: Shopping + Food — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Bukhara for Day 1? | EXPLAIN | True | The provided source excerpts do not contain any information about Bukhara or why it was picked for Day 1. |
| 2 | justification | Why is Buddh Bazar scheduled in the morning instead of another time of day? | EXPLAIN | True | Based on the provided excerpts, there is no mention of a Buddh Bazar or any reasons for it being scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Bukhara, Buddh Bazar, Karim's, V3S Mall, Chandni Chowk, Janpath New Mini Market. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer this question as the provided sources do not contain information about rain on Day 1. |
| 5 | contingency | What happens to my plan if Karim's is closed for a public holiday? | EXPLAIN | True | I'm sorry, but the provided sources do not contain any information about what happens to your plan if Karim's is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Indian Accent on Day 2? | EXPLAIN | True | The provided source excerpts do not contain any information about Indian Accent or dining alternatives for Day 2. |
| 7 | alternatives | If Khan Market turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If Khan Market is too crowded, you can visit other local shopping markets in the area such as Khanna Market or Meherchand Market. You can also explore nearby places of interest like Lodhi Gardens, India Gate, the Sai Baba Temple of Lodhi Road, or the India Habitat Centre. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Bukhara that isn't on the itinerary? | EXPLAIN | True | Based on the provided information, there are no details available about Bukhara or what might be located near it. |
| 10 | practicalities | How much does it cost to visit Karim's? | EXPLAIN | True | There is no entry fee to visit Karim's restaurant. A typical meal generally costs approximately ₹300 to ₹600 per person. |
| 11 | practicalities | What's the best time of day to visit Karim's? | EXPLAIN | True | The best time to visit Karim's is for lunch on weekdays. Alternatively, evenings during Ramzan are recommended if you want to experience the special night food scene in the surrounding lanes. |
| 12 | practicalities | How do I get from Andhra Bhawan Canteen to Indian Coffee House? | EXPLAIN | True | The provided source excerpts do not contain any information about the Andhra Bhawan Canteen or the Indian Coffee House. |
| 13 | suitability | Is Karim's suitable for elderly travellers? | EXPLAIN | True | Karim's occupies a cluster of simple dining rooms around a courtyard kitchen in a lane facing Jama Masjid's Gate No. 1, and you should expect queues at weekend lunch and dinner. Visitors can reach it by a 300–400 meter walk from the Jama Masjid Metro Station, by taking a cycle-rickshaw in the lanes, or by bus. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Bukhara within walking distance of my hotel? | EXPLAIN | True | Based on the information provided, there is no mention of Bukhara or whether it is within walking distance of your hotel. |

### Itinerary 17: Family + Culture + History — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Humayun's Tomb for Day 1? | EXPLAIN | True | Humayun's Tomb was chosen because its site on the banks of the Yamuna River was selected due to its proximity to the Nizamuddin Dargah, as being buried near the celebrated Sufi saint Nizamuddin Auliya was considered auspicious. Additionally, as the first grand garden-tomb on the Indian subcontinent and a UNESCO World Heritage Site, it set a precedent for subsequent Mughal architecture like the Taj Mahal. |
| 2 | justification | Why is Masala House scheduled in the morning instead of another time of day? | EXPLAIN | True | The provided sources do not contain any information about "Masala House" or the scheduling of visits for it. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Humayun's Tomb, Masala House, Purana Qila, Nathu Sweets, Karim's, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer your question as the provided sources do not contain any information about what happens or what you should do if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM. |
| 6 | alternatives | What are some alternatives to Shri Krishna Daba on Day 2? | EXPLAIN | True | The provided sources do not contain any information about Shri Krishna Daba or alternatives for Day 2. |
| 7 | alternatives | If Raj Ghat turns out to be too crowded, what else could I do instead? | EXPLAIN | True | If Raj Ghat is too crowded, you can visit the prominent Sikh gurudwara, Gurudwara Bangla Sahib, which is open around the clock and features a community kitchen and sacred tank. Alternatively, you can explore historical sites like Najaf Khan's Tomb and Safdarjung's Tomb, or visit museums such as Gandhi Smriti and the Prime Ministers' Museum & Library. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Humayun's Tomb that isn't on the itinerary? | EXPLAIN | True | Near Humayun's Tomb, you can find the Dha-panah Citadel (also known as Purana Qila or Old Fort) and the nearby Hazrat Nizamuddin Dargah, which is the shrine of the revered Sufi saint Nizamuddin Auliya. The dense Nizamuddin Basti surrounding the shrine also features historic structures, flower sellers, and kebab shops. |
| 10 | practicalities | How much does it cost to visit Humayun's Tomb? | EXPLAIN | True | The entry fee for Indian nationals is approximately ₹35 to ₹40, while for foreign nationals it is around ₹550 to ₹600. Children under 15 can enter for free, and please note that the site museum may be ticketed separately. |
| 11 | practicalities | What's the best time of day to visit Humayun's Tomb? | EXPLAIN | True | The best time to visit Humayun's Tomb is during the early morning or in the golden hour right before sunset. Additionally, October through March is recommended as the best time of year to visit. |
| 12 | practicalities | How do I get from Moti Mahal to Asharti BBQ Nights? | EXPLAIN | True | Based on the provided information, the Moti Mahal was a twin building at the northern edge of the Red Fort that was demolished during or shortly after the 1857 rebellion. There are no details available in the source excerpts regarding Asharti BBQ Nights or directions on how to travel between these two locations. |
| 13 | suitability | Is Humayun's Tomb suitable for elderly travellers? | EXPLAIN | True | Humayun's Tomb is set within a large garden complex featuring restored pathways and an entrance interpretation centre, with a recommended visit duration of 1.5 to 2 hours. The best time to visit is during the cooler months from October through March, and either early in the morning or during the golden hour before sunset. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Qutab Minar within walking distance of my hotel? | EXPLAIN | True | I cannot answer whether Qutab Minar is within walking distance of your hotel, as the provided sources do not mention your hotel or the location of Qutab Minar. |

### Itinerary 18: Nature + Art — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is scheduled in the morning because its signature dish, nihari, is traditionally a breakfast item, and the restaurant opens around 9:00 AM. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Raj Ghat, Shiv Di Hatti, Nehru Park. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | Temperatures moderate during the monsoon season from June to September, but it remains humid. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | I'm sorry, but the provided information does not contain details about Indian Accent or what happens to your plan if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Purana Delhi Darbar on Day 2? | EXPLAIN | True | The provided excerpts do not contain any information about Purana Delhi Darbar or alternatives to it on Day 2. |
| 7 | alternatives | If Sunder Nursery turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Karim's to Indian Accent? | EXPLAIN | True | The provided source excerpts do not contain instructions or directions on how to travel from Karim's to Indian Accent. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Raj Ghat within walking distance of my hotel? | EXPLAIN | True | I cannot tell if Raj Ghat is within walking distance of your hotel, as the provided sources do not mention your hotel or the distance to Raj Ghat. |

### Itinerary 19: Religion + Architecture + Culture — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Jama Masjid for Day 1? | EXPLAIN | True | Jama Masjid is one of the largest mosques in India, featuring red sandstone and white marble, two 40-metre-high minarets, and a courtyard that holds around 25,000 worshippers. Its position facing the Red Fort anchors the historic core of Old Delhi, and it is surrounded by the lively bazaars and food lanes of the walled city. |
| 2 | justification | Why is Masala House scheduled in the morning instead of another time of day? | EXPLAIN | True | The provided text does not contain any information about Masala House or why it is scheduled in the morning. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Jama Masjid, Masala House, Purana Qila, Nathu Sweets, Gulati, Red Fort. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I am sorry, but the provided excerpts do not contain any information about what to do or what happens if it rains on Day 1. |
| 5 | contingency | What happens to my plan if Purana Qila is closed for a public holiday? | EXPLAIN | True | Purana Qila is generally open daily from approximately 7:00 AM to 5:00 PM. |
| 6 | alternatives | What are some alternatives to The Habitat Hub on Day 2? | EXPLAIN | True | Based on the provided excerpts, there are no mentions of "The Habitat Hub" or any alternatives specifically designated for Day 2. |
| 7 | alternatives | If Guppy turns out to be too crowded, what else could I do instead? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Jama Masjid that isn't on the itinerary? | EXPLAIN | True | Jama Masjid is surrounded by the vibrant bazaars and food lanes of the walled city of Old Delhi. Visitors can also climb the southern minaret for panoramic views over the area. |
| 10 | practicalities | How much does it cost to visit Jama Masjid? | EXPLAIN | True | General entry to Jama Masjid is free, but there are charges if you wish to climb the southern minaret (approximately ₹100) or take photographs and videos (approximately ₹200–₹300). |
| 11 | practicalities | What's the best time of day to visit Jama Masjid? | EXPLAIN | True | The best time to visit Jama Masjid is during the early morning or late afternoon between October and March. You should also plan to avoid visiting on Friday midday. |
| 12 | practicalities | How do I get from St Luke's church to Jama Masjid? | EXPLAIN | True | To get to Jama Masjid, you can take the metro to the Jama Masjid station on the Violet Line, which is about a 5-minute walk away. You can also take a bus to the Jama Masjid bus stop on Netaji Subhash Marg, use cycle-rickshaws throughout Old Delhi, or take an auto to Netaji Subhash Marg. |
| 13 | suitability | Is Jama Masjid suitable for elderly travellers? | EXPLAIN | True | Jama Masjid features three great gates, a large courtyard, and a southern minaret that visitors can climb, but it may require some walking. The nearest metro station is about 300 to 500 meters or a 5-minute walk away, though cycle-rickshaws and autos are also available to help navigate the area. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Masala House within walking distance of my hotel? | EXPLAIN | True | I'm sorry, but the provided information does not mention Masala House or where your hotel is located. |

### Itinerary 20: Food + History + Nature + Shopping — question session

| # | Category | Question | Intent | Grounded | App Answer |
|---|---|---|---|---|---|
| 1 | justification | Why did you pick Sunder Nursery for Day 1? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 2 | justification | Why is Karim's scheduled in the morning instead of another time of day? | EXPLAIN | True | Karim's is a great spot to visit in the morning because it opens around 9:00 AM, and it serves nihari, which is traditionally a breakfast dish. It also slots directly into itineraries right after a visit to Jama Masjid. |
| 3 | justification | Why did you pick this place? | EXPLAIN | False | Which place are you asking about? Your itinerary includes: Sunder Nursery, Karim's, Indian Accent, Nathu Sweets, Lajpat Nagar Central Market, Dilli Haat. |
| 4 | contingency | What if it rains on Day 1? | EXPLAIN | True | I cannot answer your question because the provided source excerpts do not contain any information about rain on Day 1. |
| 5 | contingency | What happens to my plan if Indian Accent is closed for a public holiday? | EXPLAIN | True | The provided excerpts do not contain any information about a restaurant named Indian Accent or what happens if it is closed for a public holiday. |
| 6 | alternatives | What are some alternatives to Kalamata on Day 2? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 7 | alternatives | If Bukhara turns out to be too crowded, what else could I do instead? | EXPLAIN | True | The provided excerpts do not contain any information about Bukhara. |
| 8 | expansion | What other activities can I do on Day 2 if I have extra time? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 9 | expansion | Is there anything interesting near Sunder Nursery that isn't on the itinerary? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 10 | practicalities | How much does it cost to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 11 | practicalities | What's the best time of day to visit Sunder Nursery? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 12 | practicalities | How do I get from Dawat Khana Restaurant to Raj Ghat? | EXPLAIN | True | Based on the provided source excerpts, there is no information explaining how to travel from Dawat Khana Restaurant to Raj Ghat. |
| 13 | suitability | Is Sunder Nursery suitable for elderly travellers? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 14 | suitability | Is this itinerary suitable for a family with young kids? | EXPLAIN | False | I don't have a verified source for this — treat it as a general suggestion. |
| 15 | edge_case | Is Chandni Chowk within walking distance of my hotel? | EXPLAIN | True | The provided excerpts do not contain any information about your hotel or its distance to Chandni Chowk. |
