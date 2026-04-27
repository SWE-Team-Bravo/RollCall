"""E2E tests for the Generate Semester Schedule UI on the Event Management page.

Runs its own Streamlit server on port 15085 to avoid conflicting with the
session-scoped server in test_attendance_submission.py.
"""

import os
import subprocess
from pathlib import Path
from time import sleep, time

import pytest
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENV = _REPO_ROOT / ".venv"
_STREAMLIT = str(
    _VENV / ("Scripts/streamlit.exe" if os.name == "nt" else "bin/streamlit")
)

URL = "http://localhost:15085"
EVENT_MGMT_URL = f"{URL}/Event_Management"

pytestmark = pytest.mark.e2e


# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_options():
    options = webdriver.ChromeOptions()
    if os.environ.get("CI"):
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    return options


def _wait_for_server(timeout=20):
    start = time()
    while time() - start <= timeout:
        try:
            if requests.get(URL, timeout=0.5).status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        sleep(0.2)
    return False


def _wait(label, browser, timeout, condition, fail_msg):
    try:
        result = WebDriverWait(browser, timeout).until(condition)
        return result
    except TimeoutException:
        raise TimeoutException(f"{label}: {fail_msg}")


@pytest.fixture(scope="module")
def streamlit_server():
    process = subprocess.Popen(
        [
            _STREAMLIT,
            "run",
            "Home.py",
            "--server.headless",
            "true",
            "--server.port",
            "15085",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(_REPO_ROOT),
    )
    sleep(5)
    if not _wait_for_server():
        process.terminate()
        pytest.skip("Streamlit server did not start within 20 seconds")
    yield
    process.terminate()


@pytest.fixture
def browser(streamlit_server):
    driver = webdriver.Chrome(options=_make_options())
    driver.get(URL)
    yield driver
    driver.quit()


def _login_as_admin(browser):
    _wait(
        "login.username",
        browser,
        15,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"),
        "username input not found",
    ).send_keys("admin1@rollcall.local")
    _wait(
        "login.password",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"),
        "password input not found",
    ).send_keys("password")
    _wait(
        "login.button",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"),
        "login button not found",
    ).click()


def _go_to_event_management(browser):
    _login_as_admin(browser)
    _wait(
        "login.complete",
        browser,
        15,
        lambda d: d.find_element(By.XPATH, "//button[.//*[contains(text(), 'Logout')]]"),
        "logout button not found after login",
    )
    browser.get(EVENT_MGMT_URL)
    _wait(
        "nav.event_mgmt",
        browser,
        15,
        lambda d: "Event Management" in d.find_element(By.TAG_NAME, "body").text,
        "Event Management page did not load",
    )


def _open_generate_expander(browser):
    expander = _wait(
        "expander.generate",
        browser,
        15,
        lambda d: d.find_element(
            By.XPATH,
            "//*[contains(text(), 'Generate Semester Schedule')]",
        ),
        "Generate Semester Schedule expander not found",
    )
    expander.click()
    _wait(
        "expander.content_ready",
        browser,
        10,
        EC.element_to_be_clickable(
            (By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]")
        ),
        "Preview Schedule button not clickable after opening expander",
    )


# ── tests ─────────────────────────────────────────────────────────────────────


def test_event_management_page_loads(browser):
    _go_to_event_management(browser)
    body = browser.find_element(By.TAG_NAME, "body").text
    assert "Event Management" in body


def test_generate_semester_schedule_expander_exists(browser):
    _go_to_event_management(browser)
    _wait(
        "expander.exists",
        browser,
        15,
        lambda d: d.find_element(
            By.XPATH,
            "//*[contains(text(), 'Generate Semester Schedule')]",
        ),
        "Generate Semester Schedule expander not found",
    )


def test_generate_expander_opens_and_shows_date_range_label(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.date_range",
        browser,
        10,
        lambda d: "Semester date range" in d.find_element(By.TAG_NAME, "body").text,
        "Semester date range label not found after opening expander",
    )


def test_generate_expander_shows_pt_start_time_label(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.pt_start",
        browser,
        10,
        lambda d: "PT Start Time" in d.find_element(By.TAG_NAME, "body").text,
        "PT Start Time label not found",
    )


def test_generate_expander_shows_pt_end_time_label(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.pt_end",
        browser,
        10,
        lambda d: "PT End Time" in d.find_element(By.TAG_NAME, "body").text,
        "PT End Time label not found",
    )


def test_generate_expander_shows_llab_start_time_label(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.llab_start",
        browser,
        10,
        lambda d: "LLAB Start Time" in d.find_element(By.TAG_NAME, "body").text,
        "LLAB Start Time label not found",
    )


def test_generate_expander_shows_llab_end_time_label(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.llab_end",
        browser,
        10,
        lambda d: "LLAB End Time" in d.find_element(By.TAG_NAME, "body").text,
        "LLAB End Time label not found",
    )


def test_generate_expander_shows_timezone_selector(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.timezone",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "div[data-testid='stSelectbox']"),
        "Timezone selectbox not found",
    )


def test_generate_expander_shows_holidays_section(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "label.holidays",
        browser,
        10,
        lambda d: "Holidays" in d.find_element(By.TAG_NAME, "body").text,
        "Holidays section label not found",
    )


def test_generate_expander_shows_add_date_button(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "button.add_date",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Add date')]]"
        ),
        "Add date button not found",
    )


def test_generate_expander_shows_preview_button(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "button.preview",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]"
        ),
        "Preview Schedule button not found",
    )


def test_generate_expander_shows_no_holidays_caption_initially(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)
    _wait(
        "caption.no_holidays",
        browser,
        10,
        lambda d: "No holidays added" in d.find_element(By.TAG_NAME, "body").text,
        "No holidays added caption not found initially",
    )


def test_clicking_preview_shows_event_count(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)

    preview_btn = _wait(
        "button.preview_click",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]"
        ),
        "Preview Schedule button not found",
    )
    preview_btn.click()

    _wait(
        "preview.result",
        browser,
        15,
        lambda d: (
            "events" in d.find_element(By.TAG_NAME, "body").text
            and (
                "will be created" in d.find_element(By.TAG_NAME, "body").text
                or "No events" in d.find_element(By.TAG_NAME, "body").text
            )
        ),
        "Preview result did not appear after clicking Preview Schedule",
    )


def test_preview_shows_generate_schedule_button_after_click(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)

    preview_btn = _wait(
        "button.preview_for_gen",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]"
        ),
        "Preview Schedule button not found",
    )
    preview_btn.click()

    _wait(
        "button.generate_appears",
        browser,
        15,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Generate Schedule')]]"
        ),
        "Generate Schedule button did not appear after preview",
    )


def test_preview_shows_table_with_date_column(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)

    _wait(
        "button.preview_for_table",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]"
        ),
        "Preview Schedule button not found",
    ).click()

    _wait(
        "table.date_column",
        browser,
        15,
        lambda d: d.find_element(By.CSS_SELECTOR, "div[data-testid='stDataFrame']"),
        "Preview dataframe not found after clicking Preview",
    )


def test_preview_warning_message_shown_before_generate(browser):
    _go_to_event_management(browser)
    _open_generate_expander(browser)

    _wait(
        "button.preview_for_warning",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Preview Schedule')]]"
        ),
        "Preview Schedule button not found",
    ).click()

    _wait(
        "warning.shown",
        browser,
        15,
        lambda d: "cannot be undone" in d.find_element(By.TAG_NAME, "body").text,
        "Warning message about irreversibility not shown",
    )
