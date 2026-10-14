"""
audit_company_gui.py — Playwright Audit for companies.html and triage.html.
Verifies zero console errors, DOM rendering, interactive filters, search, and navigation.
"""

import sys
import os
import http.server
import socketserver
import threading
import time
from playwright.sync_api import sync_playwright

PORT = 8899
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress server noise


def run_server():
    with socketserver.TCPServer(("127.0.0.1", PORT), QuietHandler) as httpd:
        httpd.serve_forever()


def audit():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    print(">>> Starting Playwright Audit on http://127.0.0.1:8899/...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        # -------------------------------------------------------------
        # 1. Audit companies.html
        # -------------------------------------------------------------
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        companies_url = f"http://127.0.0.1:{PORT}/companies.html"
        print(f"\n[Test 1] Navigating to {companies_url}...")
        resp = page.goto(companies_url)
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        page.wait_for_timeout(1000)

        # Assert no JS errors
        print(f"  Console errors: {len(console_errors)}")
        if console_errors:
            print("  ⚠️ Errors found:", console_errors)
        assert len(console_errors) == 0, "Console errors on companies.html!"

        # Check KPIs
        total_kpi = page.locator("#kpi-total").inner_text()
        workday_kpi = page.locator("#kpi-workday").inner_text()
        greenhouse_kpi = page.locator("#kpi-greenhouse").inner_text()
        ashby_kpi = page.locator("#kpi-ashby").inner_text()
        print(f"  KPIs -> Total: {total_kpi}, Workday: {workday_kpi}, Greenhouse: {greenhouse_kpi}, Ashby: {ashby_kpi}")
        assert int(total_kpi) > 0, "Total companies KPI should be > 0"

        # Check Table Rows
        rows = page.locator("#tableBody tr").count()
        print(f"  Table rows rendered: {rows}")
        assert rows == int(total_kpi), f"Expected {total_kpi} rows, got {rows}"

        # Test Search Filter
        print("  Testing search input with 'Amgen'...")
        page.fill("#searchInput", "Amgen")
        page.wait_for_timeout(200)
        filtered_rows = page.locator("#tableBody tr").count()
        print(f"  Filtered rows for 'Amgen': {filtered_rows}")
        assert filtered_rows == 1, f"Expected 1 row for Amgen, got {filtered_rows}"
        assert "Amgen" in page.locator("#tableBody").inner_text()

        # Clear search
        page.fill("#searchInput", "")
        page.wait_for_timeout(200)

        # Test Platform Filter
        print("  Testing platform filter with 'Workday'...")
        page.select_option("#platformFilter", "Workday")
        page.wait_for_timeout(200)
        workday_rows = page.locator("#tableBody tr").count()
        print(f"  Filtered rows for 'Workday': {workday_rows}")
        assert workday_rows == int(workday_kpi), f"Expected {workday_kpi} Workday rows, got {workday_rows}"

        # Reset filter
        page.select_option("#platformFilter", "ALL")

        # Test Navigation to triage.html
        print("  Testing navigation link to triage.html...")
        page.click("a[href='triage.html']")
        page.wait_for_url("**/triage.html*")
        print(f"  Navigated successfully to: {page.url}")

        # -------------------------------------------------------------
        # 2. Audit triage.html
        # -------------------------------------------------------------
        triage_errors = []
        page.on("console", lambda msg: triage_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: triage_errors.append(str(exc)))

        page.wait_for_timeout(1000)
        print(f"\n[Test 2] Auditing triage.html on {page.url}...")
        print(f"  Console errors: {len(triage_errors)}")
        assert len(triage_errors) == 0, f"Console errors on triage.html: {triage_errors}"

        # Check triage nav tab
        company_tab = page.locator("a[href='companies.html']")
        assert company_tab.count() >= 1, "Company Directory navigation link missing in triage.html"
        print("  Company Directory link verified in triage.html.")

        # Check existing triage KPIs
        triage_total = page.locator("#kpi-total").inner_text()
        print(f"  Triage KPI Total: {triage_total}")
        assert int(triage_total) > 0, "Triage jobs total should be > 0"

        # Click back to companies.html
        company_tab.first.click()
        page.wait_for_url("**/companies.html*")
        print(f"  Seamless roundtrip navigation verified: back at {page.url}")

        page.close()
        browser.close()

    print("\n[SUCCESS] ALL PLAYWRIGHT AUDIT TESTS PASSED WITH 100% SUCCESS!")


if __name__ == "__main__":
    audit()
