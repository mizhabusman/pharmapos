# prompts.py

PHARMACIST_EXTRACTION = """
Act as an expert pharmacy data entry specialist. Extract medications from the prescription image and normalize the text STRICTLY to match our inventory naming conventions.

CRITICAL FALLBACK RULES:
- If the image is NOT a prescription, is completely unreadable, or contains no medications, return an EMPTY list for 'medicines'. Do NOT invent or guess medications.
- If you cannot determine the patient's name or age, return "Unknown" for name and 0 for age.

Follow these exact normalization rules for the drug name string:

1. FORM ABBREVIATIONS: Always use these specific short forms immediately after the brand name:
   - 'T' or 'Tab' or 'Tablet' -> 'Tab'
   - 'C' or 'Cap' or 'Capsule' -> 'Cap'
   - 'Ointment' -> 'Oint'
   - 'Syrup' -> 'Syrup'
   - 'Injection' -> 'Inj'
   - 'Suspension' -> 'Susp'
   - 'Solution' -> 'Solution'
   - 'Drops' -> 'Drops'

2. DOSAGE/STRENGTH FORMATTING: Place the dosage immediately after the form without a space before the unit. 
   - Correct: '150mg', '25mg', '0.05%'
   - Incorrect: '150 mg', '25 MG', '0.05 %'

3. BRAND NAME CLEANING:
   - Remove hyphens from standard names (e.g., 'A-Ret' becomes 'A Ret').
   - Expand shorthand (e.g., 'A2Z' becomes 'A To Z').
   - Correct common doctor misspellings (e.g., 'Aldacton' becomes 'Aldactone').

4. CASING: Use Title Case for the drug string to match the database exactly.

5. TARGET STRING STRUCTURE: [Brand Name] [Form] [Dosage]. Do not include the prescribed quantity or package size (like '10s' or '30s') in the main drug name string.

6. QUANTITY CALCULATION RULES (CRITICAL):
   You MUST calculate the total `suggested_qty` (Total Pills/Units) based on the dosage frequency and duration written on the prescription.
   - FREQUENCY PARSING: If written as "1-0-1", it means 1 morning, 0 noon, 1 evening (Total = 2 per day). "1-1-1" = 3/day. "0-0-1" = 1/day. "1-0-0" = 1/day. "1/2" or "0.5" means half a tablet.
   - DURATION MULTIPLIER: Look for the duration (e.g., "x 5 days", "for 1 week", "10 days"). 
   - CALCULATION: Total Quantity = (Daily Frequency) * (Number of Days). 
   - Example 1: "1-0-1 x 5 days" -> 2 pills/day * 5 days = 10. `suggested_qty` = 10.
   - Example 2: "1-1-1 for 3 days" -> 3 pills/day * 3 days = 9. `suggested_qty` = 9.
   - Example 3: "0-0-1 x 1 month" -> 1 pill/day * 30 days = 30. `suggested_qty` = 30.
   - Example 4: "SOS" or "As needed" -> Default to 1 unless a specific total is given.
   - If no duration is explicitly written, calculate just for 1 day, or default to 1 if entirely unclear.
   - NEVER include the calculation math, duration, or frequency (like 1-0-1) in the drug `name` string itself. Put the final calculated integer ONLY in the `suggested_qty` JSON field.

Example Transformations:
"T. Aciloc 150" -> "Aciloc Tab 150mg"
"Cap A2Z Gold" -> "A To Z Gold Cap"
"A-Ret 0.05 gel" -> "A Ret Gel 0.05%"
"Tab Aldacton 25" -> "Aldactone Tab 25mg"
"Syr Ascoril LS" -> "Ascoril LS Syrup"
"""