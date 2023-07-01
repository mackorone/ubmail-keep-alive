#!/usr/bin/env python3

import argparse
import contextlib
import datetime
import logging
import os
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from plants.committer import Committer
from plants.environment import Environment
from plants.external import allow_external_calls
from plants.logging import configure_logging

logger: logging.Logger = logging.getLogger(__name__)


@contextlib.contextmanager
def get_driver(executable_path: str, *, headless: bool) -> Iterator[webdriver.Firefox]:
    service = Service(executable_path=executable_path)
    options = Options()
    options.headless = headless
    # pyre-fixme[28]
    driver = webdriver.Firefox(
        service=service,
        options=options,
    )
    try:
        yield driver
    finally:
        driver.quit()


def ensure_attribute(element: WebElement, attribute: str, expected_value: str) -> None:
    actual_value = element.get_attribute(attribute)
    if actual_value != expected_value:
        raise RuntimeError("Wrong {attribute}: {expected_value=} vs {actual_value=}")


def login(driver: webdriver.Firefox, username: str, password: str) -> None:
    logger.info("Going to UBmail page")
    driver.get("https://ubmail.buffalo.edu/cgi-bin/login.pl")

    logger.info("Waiting for redirect")
    wait = WebDriverWait(driver, timeout=10)
    wait.until(lambda x: x.find_element(By.ID, "login-button"))

    logger.info("Submitting credentials")
    driver.find_element(By.ID, "login").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "login-button").click()

    logger.info("Waiting for authentication")

    # Outlook authentication page
    password_input = wait.until(lambda x: x.find_element(By.ID, "i0118"))
    ensure_attribute(password_input, "name", "passwd")
    ensure_attribute(password_input, "type", "password")
    ensure_attribute(password_input, "placeholder", "Password")
    password_input.send_keys(password)

    sign_in_button = driver.find_element(By.ID, "idSIButton9")
    ensure_attribute(sign_in_button, "type", "submit")
    ensure_attribute(sign_in_button, "value", "Sign in")
    sign_in_button.click()

    logger.info("Waiting for authentication (again)")

    # Outlook "save this browser" page
    no_button = wait.until(lambda x: x.find_element(By.ID, "idBtn_Back"))
    ensure_attribute(no_button, "type", "button")
    ensure_attribute(no_button, "value", "No")
    no_button.click()

    # Inbox page
    logo = wait.until(lambda x: x.find_element(By.ID, "O365_MainLink_TenantLogo"))
    ensure_attribute(logo, "href", "http://buffalo.edu/")
    logger.info("Successful login")


def forward_unread_mail(driver: webdriver.Firefox) -> None:
    wait = WebDriverWait(driver, timeout=10)

    logger.info("Clicking filter button")
    wait.until(
        lambda x: x.find_element(
            By.XPATH,
            (
                '//div[@data-app-section="MessageList"]'
                '//i[@data-icon-name="FilterRegular"]'
            ),
        )
    ).click()

    logger.info("Clicking 'Unread' button")
    wait.until(
        lambda x: x.find_element(
            By.XPATH,
            '//button[@name="Unread"]',
        )
    ).click()

    logger.info("Checking for unread messages")
    try:
        WebDriverWait(driver, timeout=1).until(
            lambda x: x.find_element(
                By.XPATH, '//span[text()="You\'re on top of everything here."]'
            )
        )
        logger.info("No unread messages")
        return
    except Exception:
        pass

    elements = wait.until(
        lambda x: x.find_elements(
            By.XPATH, ('//div[@role="option" and starts-with(@aria-label,"Unread ")]')
        )
    )
    num_messages = len(elements)
    logger.info(f"Found {num_messages} unread messages")

    # Forward the messages in the order they were received
    for i, element in enumerate(reversed(elements)):
        logger.info(f"Forwarding message {i + 1} / {num_messages}")
        element.click()

        logger.info("Clicking 'Forward' button")
        wait.until(lambda x: x.find_element(By.ID, "read_ellipses_menu")).click()
        forward_button = wait.until(
            lambda x: x.find_element(
                By.XPATH, '//button[@role="menuitem" and @aria-label="Forward"]'
            )
        )
        # Hacky workaround for "not clickable because another element obscures it"
        # https://stackoverflow.com/a/63157469/3176152
        driver.execute_script("arguments[0].click();", forward_button)

        logger.info("Entering recipient")
        wait.until(
            lambda x: x.find_element(
                By.XPATH, '//div[@role="textbox" and @aria-label="To"]'
            )
        ).send_keys(Environment.get_env("FORWARD_TO_EMAIL"))

        logger.info("Clicking 'Send' button")
        wait.until(
            lambda x: x.find_element(
                By.XPATH, '//div[@role="button" and @aria-label="Send"]'
            )
        ).click()

        logger.info("Marking message as read")
        wait.until(lambda x: x.find_element(By.ID, "read_ellipses_menu")).click()
        wait.until(
            lambda x: x.find_element(
                By.XPATH, '//button[@role="menuitem" and @aria-label="Mark as read"]'
            )
        ).click()


def main() -> None:
    parser = argparse.ArgumentParser(description="UBmail login script")
    parser.add_argument("--webdriver-executable-path", required=True)
    parser.add_argument("--forward-unread-mail", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args()

    logger.info("Reading credentials")
    username = os.getenv("UBIT_USERNAME")
    password = os.getenv("UBIT_PASSWORD")
    assert username
    assert password

    logger.info("Starting WebDriver")
    with get_driver(
        args.webdriver_executable_path,
        headless=(not args.no_headless),
    ) as driver:
        logger.info("Attempting to login")
        login(driver, username, password)
        if args.forward_unread_mail:
            logger.info("Attempting to forward mail")
            forward_unread_mail(driver)

    # GitHub automatically disables actions for inactive repos. To prevent
    # that, write the timestamp of the last successful run back to the repo.
    logger.info("Writing last success file")
    root = Environment.get_repo_root()
    path = root / "last_success.txt"
    now = datetime.datetime.now()
    with open(path, "w") as f:
        f.write(f"{now}\n")
    Committer.commit_and_push_if_github_actions()


if __name__ == "__main__":
    allow_external_calls()
    configure_logging(auto_indent=True)
    main()
