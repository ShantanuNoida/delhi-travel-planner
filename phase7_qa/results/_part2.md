## Part 2 — Edit Commands & Application Responses (Agent 3: Edit Command Agent)

Each itinerary below received the same **15-command editing session, applied cumulatively** (each command acts on the itinerary state left by the previous one, exactly like a real back-and-forth editing conversation) -- run for real through the app's actual Gemini-backed intent classifier and edit engine, not simulated.

### Itinerary 1: Food-only city crawl — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Andhra Bhawan Canteen to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Bukhara to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Nando's → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Couldn't find a suitable replacement for that swap. |
| 6 | Swap Day 2 afternoon for a history spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Bukhara from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Bukhara' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Pindi restaurant Delhi, Good Earth to free up time. |

### Itinerary 2: History-only deep dive — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Karim's → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Napoli Pizza → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Removed Red Fort from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Masala House, Lama Kitchen Himalayan Cook House, बाबू राम देवी दयाल to free up time. |

### Itinerary 3: Nature-only escape — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed The Golden Dragon to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Couldn't find a suitable replacement for that swap. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Deer park → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Deer park from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Deer park' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Indian Accent to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, chai point to free up time. |

### Itinerary 4: Shopping-only spree — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nazeer Foods to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Barbeque Nation to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Moti Mahal → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Dilli Haat → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Dilli Haat from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Dilli Haat' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Asharti BBQ Nights to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Make My Lagan, Xero Degrees to free up time. |

### Itinerary 5: Religion-only pilgrimage — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Pizza Hut to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Thalairaj Biryani to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Gokulam → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | REJECTED | That would push day 3 over the 8.0h budget. I can replace an existing stop instead, or move this to another day — want me to do that? |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a family stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Kalkaji Mandir from Day 2. | EDIT / remove / day 2 / all | OK | Removed Kalkaji Mandir from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Punjab Grill to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant, Thalairaj Biryani, Nathus Sweets to free up time. |

### Itinerary 6: History + Food — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Gulati to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Indian Coffee House → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Red Fort → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a culture spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Red Fort' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, Chaska Ram to free up time. |

### Itinerary 7: Culture + Art — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed The Habitat Hub to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | Made it more relaxed — removed Celebration Restaurant to free up time. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Shri Krishna Daba to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Fat Lulu's → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Roast 'N' Currie → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Raj Ghat from Day 2. | EDIT / remove / day 2 / all | OK | Removed Raj Ghat from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Good Earth to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed The Habitat Hub, Shri Krishna Daba, Roast 'N' Currie to free up time. |

### Itinerary 8: Architecture + History + Shopping — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Indian Accent → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Red Fort → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Red Fort' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Nathu Sweets, बाबू राम देवी दयाल to free up time. |

### Itinerary 9: Family + Nature — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Shiv Di Hatti to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Couldn't find a suitable replacement for that swap. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Raj Ghat → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Raj Ghat from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Raj Ghat' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Indian Accent to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, Purana Delhi Darbar to free up time. |

### Itinerary 10: Food + Shopping + Culture — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Pindi restaurant Delhi to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Have more → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Bukhara → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a history spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Karim's from Day 2. | EDIT / remove / day 2 / all | OK | Removed Karim's from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Pindi restaurant Delhi, The Golden Dragon, Guru Kirpa Restaurant to free up time. |

### Itinerary 11: Religion + History — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Indian Accent to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Karim's → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Red Fort → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a family stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Red Fort' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's to free up time. |

### Itinerary 12: Art + Culture + Food — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Nathu Sweets → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Bukhara → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a history spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Removed Red Fort from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, The Golden Dragon, Chaska Ram to free up time. |

### Itinerary 13: Nature + Family + Shopping — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Barbeque Nation to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Couldn't find a suitable replacement for that swap. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Lajpat Nagar Central Market → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Lajpat Nagar Central Market from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Lajpat Nagar Central Market' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Indian Accent to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, Make My Lagan to free up time. |

### Itinerary 14: Architecture + Religion — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Gulati → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Napoli Pizza → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a family stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Removed Red Fort from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Xero Degrees, Lama Kitchen Himalayan Cook House, Gumbad Cafe to free up time. |

### Itinerary 15: History + Culture + Architecture + Food — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Guru Kirpa Restaurant to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Masala House → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Bukhara → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a nature spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Removed Red Fort from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Nathu Sweets, Dilli 6, Guru Kirpa Restaurant to free up time. |

### Itinerary 16: Shopping + Food — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Buddh Bazar to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Andhra Bhawan Canteen to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Chandni Chowk → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Indian Accent → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a history spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Janpath New Mini Market from Day 2. | EDIT / remove / day 2 / all | OK | Removed Janpath New Mini Market from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed V3S Mall to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Gulati, Krishna Dhaba to free up time. |

### Itinerary 17: Family + Culture + History — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Shri Krishna Daba to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Karim's → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | OK | Swapped: Thalairaj Biryani → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Removed Red Fort from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Masala House, California Burrito, Asharti BBQ Nights to free up time. |

### Itinerary 18: Nature + Art — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Shiv Di Hatti to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Couldn't find a suitable replacement for that swap. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Raj Ghat → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Raj Ghat from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Raj Ghat' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Indian Accent to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Karim's, Purana Delhi Darbar to free up time. |

### Itinerary 19: Religion + Architecture + Culture — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Masala House to free up time. |
| 2 | Day 2 feels too packed — take one thing out of the evening. | EDIT / relax / day 2 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed The Habitat Hub to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Gulati → Shanker's International Doll Museum. |
| 5 | Swap the Day 2 morning plan to something outdoors. | EDIT / swap / day 2 / morning | OK | Swapped: Red Fort → Humayun's Tomb. |
| 6 | Swap Day 2 afternoon for a food spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a family stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Red Fort from Day 2. | EDIT / remove / day 2 / all | OK | Couldn't find anything matching 'Red Fort' to remove. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Nathu Sweets to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 4 more relaxed. | EDIT / relax / day 4 / all | REJECTED | Day 4 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Guppy, Aka Gaka to free up time. |

### Itinerary 20: Food + History + Nature + Shopping — edit session

| # | Command | Classified (edit_type / day / slot) | Result | App Response |
|---|---|---|---|---|
| 1 | Make Day 1 more relaxed. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Karim's to free up time. |
| 2 | Day 3 feels too packed — take one thing out of the evening. | EDIT / relax / day 3 / evening | OK | This day is already light — nothing to remove. |
| 3 | Day 2 is a lot — can you lighten it up somehow? | EDIT / relax / day 2 / all | OK | Made it more relaxed — removed Kalamata to free up time. |
| 4 | Swap the Day 1 evening plan to something indoors. | EDIT / swap / day 1 / evening | OK | Swapped: Nathu Sweets → Shanker's International Doll Museum. |
| 5 | Swap the Day 3 morning plan to something outdoors. | EDIT / swap / day 3 / morning | REJECTED | That would push day 3 over the 8.0h budget. I can replace an existing stop instead, or move this to another day — want me to do that? |
| 6 | Swap Day 2 afternoon for a culture spot instead. | EDIT / swap / day 2 / afternoon | OK | Couldn't find a suitable replacement for that swap. |
| 7 | Replace the Day 1 evening stop with Connaught Place. | EDIT / swap / day 1 / evening | OK | I don't have a real, mappable record of Connaught Place in my data (it's absent from the OpenStreetMap extract this planner uses) — I can't honestly add it. Khan Market or Janpath are real, verified alternatives nearby if you'd like one of those instead. |
| 8 | Add one famous local food place to Day 1. | EDIT / add / day 1 / all | OK | Couldn't find a new place matching that request. |
| 9 | Add a religion stop somewhere in the trip. | EDIT / add / day all / all | OK | Couldn't find a new place matching that request. |
| 10 | Add Select Citywalk mall to Day 2. | EDIT / add / day 2 / all | OK | Couldn't find a new place matching that request. |
| 11 | Remove Lajpat Nagar Central Market from Day 2. | EDIT / remove / day 2 / all | OK | Removed Lajpat Nagar Central Market from the itinerary. |
| 12 | Remove the boring stop from Day 1. | EDIT / relax / day 1 / all | OK | Made it more relaxed — removed Shanker's International Doll Museum to free up time. |
| 13 | Reduce travel time between stops. | EDIT / reduce_travel / day all / all | OK | Re-clustered your stops to minimize travel time between them. |
| 14 | Make Day 5 more relaxed. | EDIT / relax / day 5 / all | REJECTED | Day 5 doesn't exist in this itinerary. |
| 15 | Make the whole trip more fun. | EDIT / relax / day all / all | OK | Made it more relaxed — removed Shri Krishna Daba, Karim's, Dawat Khana Restaurant to free up time. |
