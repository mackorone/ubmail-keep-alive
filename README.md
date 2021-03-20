# ubmail-keep-alive

> Don't let my `buffalo.edu` email address get garbage collected

## Introduction

Every two months, I receive the following email:

> Our records indicate you have not logged in to your UBmail Powered by Google email in the last 60 days. You must log in using the link below at least once every 90 days to keep your UBmail service active.
>
> Please log in here: https://ubmail.buffalo.edu
>
> If you do not log into your UBmail for 90 days, you will lose access to your UBmail service. Any existing email messages you may have in your UBmail will eventually be lost.

I'm tired of manually logging into my old email account just to save it from garbage collection.

Thankfully, this chore can be automated.

## How it works

Once a week, a GitHub action runs `script.py`. The script uses
[Selenium](https://www.selenium.dev/), a browser automation tool, to
programmatically log into my UBmail account. My username and password are
stored as repository secrets and passed to the script as environment variables.

If you want to keep *your* `buffalo.edu` email address alive:
1. Fork this repository
1. Add `UBIT_USERNAME` and `UBIT_PASSWORD` repository secrets
1. Profit
