from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from time import sleep, time
import subprocess
import requests.adapters

# Local streamlit URL
url = "http://localhost:8501"

# No popups
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--window-size=1920,1080")
browser = webdriver.Chrome(options = options)

# Waits until a connection has been made with the server before doing selenium stuff
def connect_to_server():
    timer = 15              # 15 second timer
    start = time()     # Finds current time
    
    # Continuously attempts to connect until timer runs out
    while (time() - start <= timer):
        try:
            # Get connection status
            response = requests.get(url, timeout = 0.5)
            
            # Verify connection status
            if(response.status_code == 200):
                print("Connected to server :)")
                return True
            
            # Print status message
            print("Waiting for server to connect :|")

        # Print status message if unable to connect to server
        except requests.exceptions.ConnectionError:
            print("Server not ready yet :(")
    
        sleep(0.1)

    # Print error message if unable to connect to server
    print("Unable to connect to server :(")
    return False

#
### START TESTS
#

# Test 1
def test_we_are_on_login_page():
    try: 
        # lambda is a small function with no name
        # lambda arguments: expression
        WebDriverWait(browser, 10).until(lambda driver: "Login" in driver.find_element(By.TAG_NAME, "body").text)
        print("Test 1 Success ✅")
    except TimeoutException:
        print("Test 1 Failure ❌")  

# Test 2
def check_for_username_and_box():
    try: 
        WebDriverWait(browser, 10).until(lambda driver: "Username" in driver.find_element(By.TAG_NAME, "body").text)
        WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"))
        print("Test 2 Success ✅")
    except TimeoutException:
        print("Test 2 Failure ❌")

# Test 3
def check_for_password_and_box():
    try: 
        WebDriverWait(browser, 10).until(lambda driver: "Password" in driver.find_element(By.TAG_NAME, "body").text)
        WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"))
        print("Test 3 Success ✅")
    except TimeoutException:
        print("Test 3 Failure ❌")

# Test 4
def check_for_login_button():
    try: 
        WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"))
        print("Test 4 Success ✅")
    except TimeoutException:
        print("Test 4 Failure ❌")

# Test 5
def log_into_website():
    try: 
        username = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"))
        password = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"))
        button   = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"))

        username.send_keys("admin1@rollcall.local")
        password.send_keys("password")
        button.click()

        WebDriverWait(browser, 10).until(lambda driver: "Logged in" in driver.find_element(By.TAG_NAME, "body").text)
        print("Test 5 Success ✅")
    except TimeoutException:
        print("Test 5 Failure ❌")

# Test 6
def move_to_attendance_submission_page():
    try:
        attendance = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"))
        attendance.click()
        WebDriverWait(browser, 10).until(lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text)

        print("Test 6 Success ✅")
    except TimeoutException:
        print("Test 6 Failure ❌")

# Test 7
def check_for_attendance_password_and_box():
    try:
        WebDriverWait(browser, 10).until(lambda driver: "Password" in driver.find_element(By.TAG_NAME, "body").text)
        WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"))
        print("Test 7 Success ✅")
    except TimeoutException:
        print("Test 7 Failure ❌")

# Test 8
def check_for_attendance_status():
    try:
        WebDriverWait(browser, 10).until(lambda driver: "Attendance Status: Needs Reported" in driver.find_element(By.TAG_NAME, "body").text)
        print("Test 8 Success ✅")
    except TimeoutException:
        print("Test 8 Failure ❌")

# Test 9
def check_for_report_in_button():
    try:
        WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondary']"))
        print("Test 9 Success ✅")
    except TimeoutException:
        print("Test 9 Failure ❌")

# Test 10
def test_attendance_status_after_button_push_without_password():
    try:
        button = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondary']"))
        button.click()
        WebDriverWait(browser, 10).until(lambda driver: "Attendance Status: Needs Reported" in driver.find_element(By.TAG_NAME, "body").text)
        print("Test 10 Success ✅")
    except TimeoutException:
        print("Test 10 Failure ❌")

# Test 11
def test_password_works_and_changes_status():
    try:
        passwordbox = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"))
        password = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.XPATH, "//p[contains(text(), 'testing')]"))
        passwordbox.send_keys(password.text[-6:])

        button = WebDriverWait(browser, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondary']"))
        button.click()
        
        WebDriverWait(browser, 10).until(lambda driver: "Attendance Status: Reported" in driver.find_element(By.TAG_NAME, "body").text)
        
        print("Test 11 Success ✅")
    except TimeoutException:
        print("Test 11 Failure ❌")

#
### END TESTS
#

# Open streamlit
process = subprocess.Popen(["streamlit", "run", "../Home.py", "--server.headless", "true"])
sleep(3)

# Run tests
if (connect_to_server()):
    # Start tests
    browser.get(url)

    # Run tests
    test_we_are_on_login_page()
    check_for_username_and_box()
    check_for_password_and_box()
    check_for_login_button()
    log_into_website()
    move_to_attendance_submission_page()
    check_for_attendance_password_and_box()
    check_for_attendance_status()
    check_for_report_in_button()
    test_attendance_status_after_button_push_without_password()
    test_password_works_and_changes_status()

    # End tests
    browser.close()
    process.terminate()
    print("Done 🛑")