#!/usr/bin/env python3

import argparse
import asyncio
import contextlib
import datetime
import logging
from typing import Iterator

from selenium import webdriver
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from plants.committer import Committer
from plants.environment import Environment
from plants.external import allow_external_calls
from plants.logging import configure_logging
from plants.retry import AttemptFactory, retry
from plants.sleep import sleep

logger: logging.Logger = logging.getLogger(__name__)


def ensure_attribute(element: WebElement, attribute: str, expected_value: str) -> None:
    actual_value = element.get_attribute(attribute)
    if actual_value != expected_value:
        raise RuntimeError(f"Wrong {attribute}: {expected_value=} vs {actual_value=}")


async def click(
    driver: webdriver.Firefox,
    xpath: str,
) -> None:
    wait = WebDriverWait(driver, 1)
    element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    # Hacky workaround for "not clickable because another element obscures it"
    # https://stackoverflow.com/a/63157469/3176152
    driver.execute_script("arguments[0].click();", element)


async def click_with_retries(
    driver: webdriver.Firefox,
    xpath: str,
) -> None:
    with retry(func=click, num_attempts=3, sleep_seconds=1) as wrapper:
        await wrapper(driver, xpath)


async def login(driver: webdriver.Firefox, username: str, password: str) -> None:
    logger.info("Going to UBmail page")
    driver.get("https://ubmail.buffalo.edu/cgi-bin/login.pl")

    logger.info("Waiting for redirect")
    driver.find_element(By.ID, "login-button")

    logger.info("Submitting credentials")
    driver.find_element(By.ID, "login").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.ID, "login-button").click()

    logger.info("Waiting for authentication")

    # Outlook authentication page
    password_input = driver.find_element(By.ID, "i0118")
    ensure_attribute(password_input, "name", "passwd")
    ensure_attribute(password_input, "type", "password")
    ensure_attribute(password_input, "placeholder", "Password")
    password_input.send_keys(password)

    sign_in_button = driver.find_element(By.ID, "idSIButton9")
    ensure_attribute(sign_in_button, "type", "submit")
    ensure_attribute(sign_in_button, "value", "Sign in")
    sign_in_button.click()

    logger.info("Submitting credentials (again)")
    logger.info("Waiting for authentication (again)")

    # Outlook "You're about to sign in" page
    if False:
        continue_button = driver.find_element(By.ID, "idSIButton9")
        ensure_attribute(continue_button, "type", "submit")
        ensure_attribute(continue_button, "value", "Continue")
        continue_button.click()

    # Outlook "save this browser" page
    no_button = driver.find_element(By.ID, "idBtn_Back")
    ensure_attribute(no_button, "type", "button")
    ensure_attribute(no_button, "value", "No")
    no_button.click()

    # "Pick an account"
    account_div = driver.find_element(
        By.XPATH,
        (
            f'//div[starts-with(@data-test-id, "{username}") and '
            f'starts-with(@aria-label, "Sign in with {username}")]'
        )
    )
    account_div.click()

    # Inbox page
    for attempt in AttemptFactory(num_attempts=3, sleep_seconds=1):
        async with attempt:
            logo = driver.find_element(By.ID, "O365_MainLink_TenantLogo")
            ensure_attribute(logo, "href", "http://buffalo.edu/")
            logger.info("Successful login")


async def forward_unread_mail(
    driver: webdriver.Firefox, forwarding_address: str
) -> None:
    for attempt in AttemptFactory(num_attempts=3, sleep_seconds=1):
        async with attempt:
            logger.info("Clicking filter button")
            await click(
                driver=driver,
                xpath='//button[@id="menurn" or @aria-label="Filter"]',
            )
            logger.info("Clicking 'Unread' button")
            await click(
                driver=driver,
                xpath='//div[@role="menuitemradio" and @title="Unread"]',
            )

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

    elements = driver.find_elements(
        By.XPATH, ('//div[@role="option" and starts-with(@aria-label,"Unread ")]')
    )
    num_messages = len(elements)
    logger.info(f"Found {num_messages} unread messages")

    # Forward the messages in the order they were received
    for i, element in enumerate(reversed(elements)):
        logger.info(f"Forwarding message {i + 1} / {num_messages}")
        element.click()

        logger.info("Clicking 'Forward' button")
        # Clicking "Forward" doesn't always work the first time, so try again
        for attempt in AttemptFactory(num_attempts=3, sleep_seconds=1):
            async with attempt:
                await click_with_retries(
                    driver=driver,
                    xpath='//button[@aria-label="Forward"]',
                )
                logger.info("Attempting to enter recipient")
                driver.find_element(
                    By.XPATH, '//div[@role="textbox" and @aria-label="To"]'
                ).send_keys(forwarding_address)

        logger.info("Clicking 'Send' button")
        await click_with_retries(
            driver=driver, xpath='//button[@type="button" and @aria-label="Send"]'
        )

        logger.info("Marking message as read")
        await click_with_retries(
            driver=driver,
            xpath='//button[@aria-label="Read / Unread"]',
        )


@contextlib.contextmanager
def get_firefox_webdriver(*, headless: bool) -> Iterator[Firefox]:
    service = Service()
    options = Options()
    if headless:
        options.add_argument("-headless")
    driver = Firefox(
        service=service,
        options=options,
    )
    try:
        yield driver
    finally:
        driver.quit()


async def main() -> None:
    parser = argparse.ArgumentParser(description="UBmail login script")
    parser.add_argument("--forward-unread-mail", action="store_true")
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()

    logger.info("Reading credentials")
    username = Environment.get_env("UBIT_USERNAME")
    password = Environment.get_env("UBIT_PASSWORD")
    assert username
    assert password

    forwarding_address = None
    if args.forward_unread_mail:
        forwarding_address = Environment.get_env("FORWARD_TO_EMAIL")
        assert forwarding_address

    logger.info("Starting WebDriver")
    with get_firefox_webdriver(
        headless=not args.show_browser,
    ) as driver:
        # Always wait at least 5 seconds before failing to find elements
        driver.implicitly_wait(5)
        try:
            logger.info("Attempting to login")
            await login(driver, username, password)
            if forwarding_address:
                logger.info("Attempting to forward mail")
                await forward_unread_mail(driver, forwarding_address)
            await sleep(1)  # allow actions to finish before closing
        except Exception:
            if args.show_browser:
                logger.exception("Caught exception")
                logger.info("Press CTRL-C to exit")
                await sleep(86400)
            raise

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
    configure_logging()
    asyncio.run(main())
