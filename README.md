# ubmail-keep-alive [![](https://github.com/mackorone/ubmail-keep-alive/actions/workflows/main.yml/badge.svg)](https://github.com/mackorone/ubmail-keep-alive/actions/workflows/main.yml)

> Don't let my `buffalo.edu` email address get garbage collected

## Introduction

Every two months, I receive the following email:

> Our records indicate you have not logged in to your UBmail Powered by Google
> email in the last 60 days. You must log in using the link below at least once
> every 90 days to keep your UBmail service active.
>
> Please log in here: https://ubmail.buffalo.edu
>
> If you do not log into your UBmail for 90 days, you will lose access to your
> UBmail service. Any existing email messages you may have in your UBmail will
> eventually be lost.

I'm tired of manually logging into my old email account just to save it from
garbage collection.

Thankfully, this chore can be automated.

## How it works

Once per day, a GitHub action runs `script.py`. The script uses
[Selenium](https://www.selenium.dev/), a browser automation tool, to
programmatically log into my UBmail account. The script also automatically
forwards me all unread emails because, sadly, mail forwarding rules are no
longer supported. My username, password, and "forward to" email are
stored as repository secrets and passed to the script as environment variables.

If you want to keep *your* `buffalo.edu` email address alive:
1. Fork this repository
1. Add `UBIT_USERNAME`, `UBIT_PASSWORD`, and `FORWARD_TO_EMAIL` repository secrets
   - Under `Settings` > `Secrets` > `Actions`
1. Enable `GITHUB_TOKEN` "Read and write permissions"
   - Under `Settings` > `Actions` > `General` > `Workflow permissions`
