from flask import Flask, request, jsonify
from flask_cors import CORS
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re

app = Flask(__name__)
CORS(app)  # allow frontend requests


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

        # Wait until table has data or timeout
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

        # Extract and clean data
        rows = page.query_selector_all("#caseTable tbody tr")
        case_data = []
        for row in rows:
            cols = [col.inner_text().strip() for col in row.query_selector_all("td")]

            if len(cols) >= 4:
                case_info = cols[1].replace("Orders", "").strip()
                parties = cols[2].strip()

                next_date_match = re.search(r"NEXT DATE:\s*([\d/]+)", cols[3], re.IGNORECASE)
                last_date_match = re.search(r"Last Date:\s*([\d/]+)", cols[3], re.IGNORECASE)
                court_no_match = re.search(r"COURT NO:?\s*([0-9A-Za-z]+)", cols[3], re.IGNORECASE)

                next_date = next_date_match.group(1) if next_date_match else ""
                last_date = last_date_match.group(1) if last_date_match else ""
                court_no = court_no_match.group(1) if court_no_match else ""

                case_data.append([cols[0], case_info, parties, next_date, last_date, court_no])

        browser.close()
        return case_data


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
            return jsonify({"error": "Data not found"}), 404
        if not result:
            return jsonify({"error": "Data not found"}), 404
        return jsonify({"case_details": result})
    except Exception:
        return jsonify({"error": "Data not found"}), 500



if __name__ == "__main__":
    app.run(debug=True)
