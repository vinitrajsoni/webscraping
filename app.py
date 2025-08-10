from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect("cases.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number TEXT,
            status TEXT,
            parties TEXT,
            next_date TEXT,
            last_date TEXT,
            court_no TEXT,
            search_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()


def save_to_db(case_data):
    conn = sqlite3.connect("cases.db")
    cursor = conn.cursor()
    for row in case_data:
        cursor.execute('''
            INSERT INTO cases (case_number, status, parties, next_date, last_date, court_no, search_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (row[0], row[1], row[2], row[3], row[4], row[5], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def fetch_history():
    conn = sqlite3.connect("cases.db")
    cursor = conn.cursor()
    cursor.execute("SELECT case_number, status, parties, next_date, last_date, court_no, search_time FROM cases ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


# --- Playwright scraper ---
def fetch_case(case_type, case_number, year):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://delhihighcourt.nic.in/app/get-case-type-status", timeout=60000)

        # Fill form
        page.select_option("#case_type", label=case_type)
        page.fill("#case_number", case_number)
        page.select_option("#case_year", year)

        # Auto-fill captcha
        try:
            captcha_value = page.inner_text("#captcha-code", timeout=5000).strip()
        except PlaywrightTimeoutError:
            browser.close()
            return {"error": "Captcha not found on page."}
        
        page.fill("#captchaInput", captcha_value)

        # Submit form
        page.click("#search")

        # Wait for table data
        try:
            page.wait_for_function(
                """() => {
                    const row = document.querySelector("#caseTable tbody tr td");
                    return row && !row.innerText.includes("No data available in table");
                }""",
                timeout=15000
            )
        except PlaywrightTimeoutError:
            browser.close()
            return {"error": "Case table did not load in time."}

        # Extract data
        rows = page.query_selector_all("#caseTable tbody tr")
        case_data = []
        base_url = "https://delhihighcourt.nic.in/"

        for row in rows:
            cols = row.query_selector_all("td")

            if len(cols) >= 4:
                case_info_text = cols[1].inner_text().replace("Orders", "").strip()

                orders_link_tag = cols[1].query_selector("a")
                if orders_link_tag:
                    href = orders_link_tag.get_attribute("href")
                    if href:
                        case_info_text += f" ({href if href.startswith('http') else base_url + href.lstrip('/')})"

                parties = cols[2].inner_text().strip()
                col3_text = cols[3].inner_text()

                next_date_match = re.search(r"NEXT DATE:\s*([\d/]+)", col3_text, re.IGNORECASE)
                last_date_match = re.search(r"Last Date:\s*([\d/]+)", col3_text, re.IGNORECASE)
                court_no_match = re.search(r"COURT NO:?\s*([0-9A-Za-z]+)", col3_text, re.IGNORECASE)

                next_date = next_date_match.group(1) if next_date_match else ""
                last_date = last_date_match.group(1) if last_date_match else ""
                court_no = court_no_match.group(1) if court_no_match else ""

                case_data.append([
                    cols[0].inner_text().strip(),
                    case_info_text,
                    parties,
                    next_date,
                    last_date,
                    court_no
                ])

        browser.close()
        return case_data


# --- API Routes ---
@app.route("/case-search", methods=["POST"])
def case_search():
    data = request.json
    case_type = data.get("case_type")
    case_number = data.get("case_number")
    year = data.get("year")

    if not case_type or not case_number or not year:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        result = fetch_case(case_type, case_number, year)
        if isinstance(result, dict) and "error" in result:
            return jsonify({"error": result["error"]}), 404
        if not result:
            return jsonify({"error": "Data not found"}), 404

        save_to_db(result)  # Save fetched cases to DB
        return jsonify({"case_details": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/case-history", methods=["GET"])
def case_history():
    try:
        history = fetch_history()
        return jsonify({"history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
