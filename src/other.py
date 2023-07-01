#!/usr/bin/env python3

import argparse
import contextlib
import datetime
import importlib
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


def func(driver: webdriver.Firefox) -> None:
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
                By.XPATH,
                '//span[text()="You\'re on top of everything here."]'
            )
        )
        logger.info("No unread messages")
        return
    except Exception:
        pass

    elements = wait.until(
        lambda x: x.find_elements(
            By.XPATH,
            (
                '//div[@role="option" and starts-with(@aria-label,"Unread ")]'
            )
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
                By.XPATH,
                '//button[@role="menuitem" and @aria-label="Forward"]'
            )
        )
        # Hacky workaround for "not clickable because another element obscures it"
        # https://stackoverflow.com/a/63157469/3176152
        driver.execute_script("arguments[0].click();", forward_button)

        logger.info("Entering recipient")
        wait.until(
            lambda x: x.find_element(
                By.XPATH,
                '//div[@role="textbox" and @aria-label="To"]'
            )
        ).send_keys(Environment.get_env("FORWARD_TO_EMAIL"))

        logger.info("Clicking 'Send' button")
        wait.until(
            lambda x: x.find_element(
                By.XPATH,
                '//div[@role="button" and @aria-label="Send"]'
            )
        ).click()

        logger.info("Marking message as read")
        wait.until(lambda x: x.find_element(By.ID, "read_ellipses_menu")).click()
        wait.until(
            lambda x: x.find_element(
                By.XPATH,
                '//button[@role="menuitem" and @aria-label="Mark as read"]'
            )
        ).click()
