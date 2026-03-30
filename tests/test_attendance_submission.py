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
# options.add_argument("--headless")
options.add_experimental_option("prefs", {"credentials_enable_service": False, "profile.password_manager_enabled": False})
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--disable-notifications")
options.add_argument("--disable-infobars")
options.add_argument("--disable-save-password-bubble")
options.add_argument("--window-size=1920,1080")

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

# Helper function for tests
def testCatcher(test, browser, timeout, condition, failMessage):
    try:
        result = WebDriverWait(browser, timeout).until(condition)
        print(test + " Success ✅")
        return result
    except TimeoutException:
        print(test + " Failure ❌ - " + failMessage)
        input("Paused — press Enter to continue . . .")
        raise   # Pushes errors to the console that weren't caught

#
### START TESTS
#

# Test 1
def test_we_are_on_login_page():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    # lambda is a small function with no name
    # lambda arguments: expression
    testCatcher("Test 1.1", browser, 10, lambda driver: "Login" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the login text")

    # End test
    browser.close()

# Test 2
def check_for_username_and_box():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    testCatcher("Test 2.1", browser, 10, lambda driver: "Username" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the username text")
    testCatcher("Test 2.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find the username input box")

    # End test
    browser.close()

# Test 3
def check_for_password_and_box():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)
 
    testCatcher("Test 3.1", browser, 10, lambda driver: "Password" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the password text")
    testCatcher("Test 3.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find the password input box")

    # End test
    browser.close()

# Test 4
def check_for_login_button():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    testCatcher("Test 4.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find the sign in button")

    # End test
    browser.close()

# Test 5
def log_into_website():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 5.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 5.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 5.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")    
   
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()

    # End test
    browser.close()

    # THIS WON'T WORK REPLACE WITH A DIFFERENT FUNCTION THAT RETURNS BROSWER?
    return username, password, button

# Test 6
def move_to_attendance_submission_page():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 6.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 6.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 6.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")    
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()

    attendance = testCatcher("Test 6.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 6.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")

    # End test
    browser.close()

# Test 7
def check_for_attendance_password_and_box():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 7.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 7.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 7.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()
    
    attendance = testCatcher("Test 7.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 7.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")
    testCatcher("Test 7.6", browser, 10, lambda driver: "Password" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find password label")
    testCatcher("Test 7.7", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password text input")

    # End test
    browser.close()

# Test 8
def check_for_attendance_status():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 7.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 7.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 7.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()
    
    attendance = testCatcher("Test 7.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 7.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")

    testCatcher("Test 8.1", browser, 10, lambda driver: "Attendance Status: Needs Reported" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the attendance needs reported text")

    # End test
    browser.close()

# Test 9
# Will still show true even if other tests pass for attendance page
def check_for_report_in_button():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 9.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 9.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 9.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()
    
    attendance = testCatcher("Test 9.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 9.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")

    testCatcher("Test 9.6", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondary']"), "couldn't find the report attendance button")

    # End test
    browser.close()

# Test 10
def test_attendance_status_after_button_push_without_password():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 10.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 10.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 10.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()
    
    attendance = testCatcher("Test 10.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 10.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")


    button = testCatcher("Test 10.6", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[class='st-emotion-cache-134a998 e1mwqyj92']"), "couldn't find the report attendance button")
    sleep(1)
    button.click()
    testCatcher("Test 10.7", browser, 10, lambda driver: "Attendance Status: Needs Reported" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the attendance status: needs reported text")

    # End test
    browser.close()

# Test 11
def test_password_works_and_changes_status():
    # Start test
    browser = webdriver.Chrome(options = options)
    browser.get(url)

    username = testCatcher("Test 11.1", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Username']"), "couldn't find username input box")
    password = testCatcher("Test 11.2", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find password input box")
    button   = testCatcher("Test 11.3", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[kind='secondaryFormSubmit']"), "couldn't find log in button")
    username.send_keys("admin1@rollcall.local")
    password.send_keys("password")
    button.click()
    
    attendance = testCatcher("Test 11.4", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "a[href='http://localhost:8501/Attendance_Submission']"), "couldn't find the attendance tab label")
    attendance.click()
    testCatcher("Test 11.5", browser, 10, lambda driver: "Attendance Submission Page" in driver.find_element(By.TAG_NAME, "body").text, "couldn't veryify being on the attendance page")


    passwordbox = testCatcher("Test 11.5", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "input[aria-label='Password']"), "couldn't find the password box")
    password = testCatcher("Test 11.6", browser, 10, lambda driver: driver.find_element(By.XPATH, "//p[contains(text(), 'testing')]"), "couldn't find the testing password hint")
    passwordbox.send_keys(password.text[-6:])
    button = testCatcher("Test 11.7", browser, 10, lambda driver: driver.find_element(By.CSS_SELECTOR, "button[class='st-emotion-cache-134a998 e1mwqyj92']"), "couldn't find the report attendance button")
    button.click()
    
    testCatcher("Test 11.8", browser, 10, lambda driver: "Attendance Status: Reported" in driver.find_element(By.TAG_NAME, "body").text, "couldn't find the attendance status: reported text")

    # End test
    browser.close()
    
#
### END TESTS
#

# Open streamlit
process = subprocess.Popen(["streamlit", "run", "../Home.py", "--server.headless", "true"])
sleep(3)

# Run tests
if (connect_to_server()):
    for _ in range(10):
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
        process.terminate()
        print("Done 🛑")