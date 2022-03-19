#!/usr/bin/env python3

import argparse
import datetime
import contextlib
import logging
import os

from plants.committer import Committer
from plants.environment import Environment
from plants.external import allow_external_calls
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def get_driver(executable_path):
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(
        options=options,
        executable_path=executable_path,
    )
    try:
        yield driver
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="UBmail login script")
    parser.add_argument("--webdriver-executable-path", required=True)
    args = parser.parse_args()

    logger.info("Reading credentials")
    username = os.getenv("UBIT_USERNAME")
    password = os.getenv("UBIT_PASSWORD")
    assert username
    assert password

    logger.info("Starting WebDriver")
    with get_driver(args.webdriver_executable_path) as driver:
        logger.info("Going to UBmail page")
        driver.get("https://ubmail.buffalo.edu/cgi-bin/login.pl")

        logger.info("Waiting for redirect")
        wait = WebDriverWait(driver, timeout=10)
        wait.until(lambda x: x.find_element_by_id("login-button"))

        logger.info("Submitting credentials")
        driver.find_element_by_id("login").send_keys(username)
        driver.find_element_by_id("password").send_keys(password)
        driver.find_element_by_id("login-button").click()

        logger.info("Waiting for authentication")
        wait.until(EC.title_contains(f"{username}@buffalo.edu"))
        logger.info("Success")

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
    main()
