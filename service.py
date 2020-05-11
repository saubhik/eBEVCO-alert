import base64
import logging
import os
import smtplib
import time
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException


class Service:
    def setup_configs(self):
        self._recipients: List[str] = input(
            "Please enter comma-separated email addresses to notify: "
        ).split(",")
        self._notifier = {
            "email": os.environ["FROM_ADDR"],
            "password": os.environ["EMAIL_PASSWORD"],
        }
        logging.info(msg=f"Notifier = {self._notifier}")
        logging.info(msg=f"Subscribers = {self._recipients}")
        self.last_email_sent = None

    def send_email(self) -> None:
        if self.last_email_sent:
            if datetime.utcnow() - self.last_email_sent < timedelta(hours=1):
                logging.info(msg="Not yet 1 hour")
                return
        from_addr = self._notifier["email"]
        to_addrs = self._recipients + [from_addr]
        subject = f"eBEVCO Delivery Available!"
        body = "Check out eBEVCO right now!"
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(user=from_addr, password=self._notifier["password"])
        server.sendmail(
            from_addr=from_addr,
            to_addrs=to_addrs,
            msg="Subject: {}\n\n{}".format(subject, body),
        )
        self.last_email_sent = datetime.utcnow()
        logging.info("Email sent")

    def run_service(self) -> None:
        self.setup_configs()

        logging.info(msg="Starting a new session")
        # https://bit.ly/2yz7W6T
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-extensions")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument("--disable-gpu")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option(
            "prefs", {"profile.managed_default_content_settings.images": 2}
        )
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(time_to_wait=5)
        driver.get(url="https://excise.wb.gov.in/eRetail/Page/eRetail_Home.aspx")
        driver.find_element_by_xpath(xpath="//img[@id='notice_cl']").click()

        mobile_number_input = driver.find_element_by_xpath(
            xpath="//input[contains(@placeholder, 'Enter Registered Mobile No')]"
        )
        mobile_number_input.click()
        mobile_number = input("Please enter mobile number: ")
        mobile_number_input.send_keys(mobile_number)

        captcha_element = driver.find_element_by_xpath(xpath="//img[@id='Image2']")
        img_captcha_base64 = driver.execute_async_script(
            """
            var ele = arguments[0], callback = arguments[1];
            ele.addEventListener('load', function fn(){
              ele.removeEventListener('load', fn, false);
              var cnv = document.createElement('canvas');
              cnv.width = this.width; cnv.height = this.height;
              cnv.getContext('2d').drawImage(this, 0, 0);
              callback(cnv.toDataURL('image/jpeg').substring(22));
            }, false);
            ele.dispatchEvent(new Event('load'));
            """,
            captcha_element,
        )
        with open(file=r"captcha.jpg", mode="wb") as file:
            file.write(base64.b64decode(img_captcha_base64))
        logging.info(msg="Downloaded captcha. Check captcha.jpg")
        captcha_text = input("Please enter captcha text: ")
        captcha_input = driver.find_element_by_xpath(
            xpath="//input[@placeholder='Enter Above Text Here']"
        )
        captcha_input.send_keys(captcha_text)

        driver.find_element_by_xpath(xpath="//input[@value='Send OTP']").click()
        logging.info(msg="OTP sent")

        otp = input("Please enter OTP: ")
        driver.find_element_by_xpath(
            xpath="//input[@placeholder='Enter OTP Here']"
        ).send_keys(otp)
        driver.find_element_by_xpath(xpath="//input[@value='Verify OTP']").click()

        try:
            driver.find_element_by_xpath(
                xpath="//*[contains(text(), 'Sellers Near You')]"
            )
            logging.info(msg="Logged in successfully!")
        except NoSuchElementException:
            logging.info(msg="Failed to log in")
            return

        while True:
            try:
                time.sleep(1)
                driver.find_element_by_xpath(
                    xpath="//span[contains(text(), 'Purchase Order')]"
                ).click()
                driver.find_element_by_xpath(
                    xpath="//*[contains(text(), 'Prepare Order')]"
                ).click()
                try:
                    alert = driver.find_element_by_xpath(
                        xpath="//*[contains(text(), "
                        "'Sorry, we are overbooked and not taking any new orders now. "
                        "Please bear with us. We will be back soon for accepting new "
                        "orders')]"
                    )
                    logging.info(msg=alert.text)
                    driver.find_element_by_xpath(
                        xpath="//button[contains(text(), 'Close')]"
                    ).click()
                except NoSuchElementException:
                    logging.info(msg="No Alerts! Sending email")
                    self.send_email()
            except NoSuchElementException as exc:
                logging.exception(msg=exc)
                logging.info(msg="Retrying")


if __name__ == "__main__":
    logging.basicConfig(level="INFO")
    Service().run_service()
