import os
import pytest
import subprocess
import requests
import requests.adapters
from pathlib import Path
from time import sleep, time
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENV = _REPO_ROOT / ".venv"
_STREAMLIT = str(
    _VENV / ("Scripts/streamlit.exe" if os.name == "nt" else "bin/streamlit")
)

URL = "http://localhost:15084"


# browser options


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
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-save-password-bubble")
    options.add_argument("--window-size=1920,1080")
    return options


# helpers


def _wait_for_server(timeout=15):
    start = time()
    while time() - start <= timeout:
        try:
            if requests.get(URL, timeout=0.5).status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        sleep(0.1)
    return False


def _wait(test, browser, timeout, condition, failMessage):
    try:
        result = WebDriverWait(browser, timeout).until(condition)
        print(test + " Success")
        return result
    except TimeoutException:
        print(test + " Failure - " + failMessage)
        raise


def _login(browser, account="admin1"):
    username = _wait(
        "login.1",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"),
        "couldn't find username input box",
    )
    password = _wait(
        "login.2",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"),
        "couldn't find password input box",
    )
    button = _wait(
        "login.3",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"),
        "couldn't find log in button",
    )
    username.send_keys(f"{account}@rollcall.local")
    password.send_keys("password")
    button.click()


def _go_to_attendance(browser):
    _login(browser, "cadet1")
    attendance = _wait(
        "nav.1",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "a[href='http://localhost:15084/']"),
        "couldn't find the attendance tab label",
    )
    attendance.click()
    _wait(
        "nav.2",
        browser,
        10,
        lambda d: "6-digit event code" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't verify being on the attendance page",
    )


# fixtures

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session", autouse=True)
def streamlit_server():
    process = subprocess.Popen(
        [_STREAMLIT, "run", "Home.py", "--server.headless", "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(_REPO_ROOT),
    )
    sleep(5)
    if not _wait_for_server():
        process.terminate()
        pytest.skip("Streamlit server did not start within 15 seconds")
    yield
    process.terminate()


@pytest.fixture(scope="session", autouse=True)
def active_event():
    """Insert a wide-window PT event so the attendance page never hits st.stop()."""
    try:
        from pymongo import MongoClient
        from config.settings import MONGODB_URI, MONGODB_DB
    except Exception:
        return  # no DB available — skip silently, tests will fail on their own

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
    try:
        client.server_info()
    except Exception:
        return  # MongoDB not reachable

    col = client[MONGODB_DB]["events"]
    now = datetime.now(timezone.utc)
    doc = {
        "event_name": "E2E Test Event",
        "event_type": "pt",
        "start_date": now - timedelta(hours=1),
        "end_date": now + timedelta(hours=2),
        "created_by_user_id": "e2e",
    }
    result = col.insert_one(doc)
    yield
    col.delete_one({"_id": result.inserted_id})
    client.close()


@pytest.fixture
def browser():
    driver = webdriver.Chrome(options=_make_options())
    driver.get(URL)
    yield driver
    driver.quit()


# tests


# Test 1
def test_we_are_on_login_page(browser):
    _wait(
        "Test 1.1",
        browser,
        10,
        lambda d: "Login" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't find the login text",
    )


# Test 2
def test_check_for_username_and_box(browser):
    _wait(
        "Test 2.1",
        browser,
        15,
        lambda d: "Username" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't find the username text",
    )
    _wait(
        "Test 2.2",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"),
        "couldn't find the username input box",
    )


# Test 3
def test_check_for_password_and_box(browser):
    _wait(
        "Test 3.1",
        browser,
        10,
        lambda d: "Password" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't find the password text",
    )
    _wait(
        "Test 3.2",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"),
        "couldn't find the password input box",
    )


# Test 4
def test_check_for_login_button(browser):
    _wait(
        "Test 4.1",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"),
        "couldn't find the sign in button",
    )


# Test 5
def test_log_into_website(browser):
    _login(browser)


# Test 6
def test_move_to_attendance_submission_page(browser):
    _go_to_attendance(browser)


# Test 7
def test_check_for_event_code_input(browser):
    _go_to_attendance(browser)
    _wait(
        "Test 7.1",
        browser,
        10,
        lambda d: "6-digit event code" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't find event code label",
    )
    _wait(
        "Test 7.2",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Event code']"),
        "couldn't find event code text input",
    )


# Test 8
def test_check_for_report_in_button(browser):
    _go_to_attendance(browser)
    _wait(
        "Test 8.1",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Report In')]]"
        ),
        "couldn't find the Report In button",
    )


# Test 9
def test_empty_code_disables_button(browser):
    _go_to_attendance(browser)
    _wait(
        "Test 9.1",
        browser,
        10,
        lambda d: d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Report In')]]"
        ),
        "couldn't find the Report In button",
    )
    _wait(
        "Test 9.2",
        browser,
        10,
        lambda d: (
            d.find_element(
                By.XPATH, "//button[.//*[contains(text(), 'Report In')]]"
            ).get_attribute("disabled")
            is not None
        ),
        "Report In button should be disabled when no code is entered",
    )


# Test 10
def test_invalid_code_shows_error(browser):
    _go_to_attendance(browser)
    code_input = _wait(
        "Test 10.1",
        browser,
        10,
        lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Event code']"),
        "couldn't find event code input",
    )
    code_input.send_keys("000000")
    code_input.send_keys(Keys.TAB)
    _wait(
        "Test 10.2",
        browser,
        10,
        lambda d: "Invalid or expired code" in d.find_element(By.TAG_NAME, "body").text,
        "couldn't find invalid code error message",
    )


# Test 11
def test_checked_in_success_with_valid_code(browser):
    from pymongo import MongoClient
    from config.settings import MONGODB_URI, MONGODB_DB
    from datetime import datetime, timedelta, timezone
    from bson import ObjectId

    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        client.server_info()
    except Exception:
        pytest.skip("MongoDB not reachable")

    db = client[MONGODB_DB]
    event_id = ObjectId()
    code_doc = {
        "code": "999888",
        "event_id": event_id,
        "event_type": "pt",
        "event_date": "2026-04-12",
        "created_by_user_id": ObjectId(),
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "active": True,
    }
    inserted = db["event_codes"].insert_one(code_doc)

    try:
        _login(browser, "cadet1")
        _wait(
            "Test 11.1",
            browser,
            10,
            lambda d: d.find_element(
                By.CSS_SELECTOR, "a[href='http://localhost:15084/']"
            ),
            "couldn't find Attendance nav link",
        ).click()
        _wait(
            "Test 11.2",
            browser,
            10,
            lambda d: "6-digit event code" in d.find_element(By.TAG_NAME, "body").text,
            "couldn't load Attendance page",
        )
        code_input = _wait(
            "Test 11.3",
            browser,
            10,
            lambda d: d.find_element(By.CSS_SELECTOR, "input[aria-label='Event code']"),
            "couldn't find event code input",
        )
        code_input.send_keys("999888")
        code_input.send_keys(Keys.TAB)
        _wait(
            "Test 11.4",
            browser,
            10,
            lambda d: (
                d.find_element(
                    By.XPATH, "//button[.//*[contains(text(), 'Report In')]]"
                ).get_attribute("disabled")
                is None
            ),
            "Report In button never became enabled after entering valid code",
        )
        d = browser
        d.find_element(
            By.XPATH, "//button[.//*[contains(text(), 'Report In')]]"
        ).click()
        _wait(
            "Test 11.5",
            browser,
            10,
            lambda d: (
                "Checked in" in d.find_element(By.TAG_NAME, "body").text
                or "already checked in" in d.find_element(By.TAG_NAME, "body").text
            ),
            "couldn't find checked-in confirmation",
        )
    finally:
        db["event_codes"].delete_one({"_id": inserted.inserted_id})
        db["attendance_records"].delete_many({"event_id": event_id})
        client.close()
