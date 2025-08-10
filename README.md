# 🏛️ Delhi High Court — Case Search API (Logic)

---

## 📌 How It Works

### **1️⃣ Receives User Request**
- **Endpoint:** `POST /case-search`
- **Input Format (JSON):**
  - **Case Type** *(e.g., "W.P.(C)")*
  - **Case Number**
  - **Year**
- **Validation:**  
  If any required field is **missing**, the API responds **immediately with an error** ❌.

---

### **2️⃣ Automates the Court Website Search**
- Uses **Playwright** to launch a **headless Chromium browser**.
- Navigates to the **Delhi High Court Case Search page**.
- Fills the **search form** with the provided case details.
- Reads and enters the **captcha value** *(only when shown as plain text)*.

---

### **3️⃣ Extracts Case Details**
- **Form Submission:**  
  Submits the form and waits for the **results table** to load.
- **Timeout Handling:**  
  If no results appear within the timeout, returns an **error** ⚠️.
- **Extracted Fields:**
  - 📄 Serial Number
  - 📂 Case Info *(cleaned)*
  - 👥 Parties Involved
  - 📅 Next Hearing Date
  - 📅 Last Hearing Date
  - 🏢 Court Number

---

### **4️⃣ Responds with Structured JSON**
- Closes the **browser** after scraping.
- Sends a **clean JSON** response containing all extracted details.
- If no data is found, returns:  
  `"Data not found"` 🚫

---

💡 **Example JSON Output:**
```json
{
  "serial_number": "1",
  "case_info": "W.P.(C) 1234/2024",
  "parties": "ABC vs XYZ",
  "next_hearing": "2024-09-12",
  "last_hearing": "2024-08-01",
  "court_number": "Court 5"
}
