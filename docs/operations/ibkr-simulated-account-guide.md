# IBKR Paper Account Setup Guide

This English guide was prepared with the organizer's permission from the team reference material. The original PDF is not distributed in this repository. Account eligibility and permissions depend on IBKR and the current application flow.

## Choose an account setup path

| Path | Characteristics | Suitable use |
|---|---|---|
| Open a full live account, then enable a Paper account | More control over permissions; Paper permissions follow the live account configuration. | Needed when you require specific stock, option, index-option, or futures permissions. |
| IBKR Free Trial | Faster setup, but the system presets permissions and may not let you add products. | Quick testing of the platform or a strategy. |

If the product universe and cross-market permissions are known, consider the first path. For a quick platform test, a Free Trial may be sufficient.

## Path 1: Full account with a Paper account

1. Open a live IBKR account. USD is a suggested base currency.
2. Apply for the required trading permissions, such as stocks, options, index options, or futures.
3. Enable a Paper trading account in account settings.
4. The Paper account is initially funded with USD 1 million; its permissions follow the live account settings.
5. Sign in to the Paper account using its Paper username and password.

In the live account, open the profile menu, choose **Settings**, then **Paper Trading Account**, and set the Paper username and password. Sign in through [IBKR Login](https://www.interactivebrokers.com.hk/sso/Login) and verify that the account mode shows `Paper`.

If a team has an existing Paper account but needs a fresh USD 1 million simulated balance, it may consider opening a separate eligible IBKR account and creating a new Paper account. Confirm account eligibility and base-currency implications before applying.

## Path 2: IBKR Free Trial

Registration: [IBKR Free Trial](https://ndcdyn.interactivebrokers.com/Universal/Application?ft=T&spltst=www&trk=PAPER-COURSE).

The Free Trial does not require completing the full live-account application, but product permissions are preset and may not be changed. Registration region can affect simulated-fund currency and available permissions:

| Registration region | Initial simulated funds | Permission notes |
|---|---:|---|
| United States | USD 1 million | U.S. policy may restrict non-U.S. stock options and non-U.S. cash index options. |
| Singapore | SGD 1 million | Permissions and regional rules apply. |
| Hong Kong | HKD 1 million | The simulated balance is lower in USD terms. |

The original reference guide recommended Singapore for some cases. Confirm the target products before registration; currency and permissions shown in the application and account are authoritative.

## Trading software

- **Trader Workstation (TWS):** graphical trading interface for manual trading, charts, orders, and portfolio management. [Download TWS](https://www.interactivebrokers.com.hk/en/trading/download-tws.php)
- **IB Gateway:** lightweight interface suited to APIs and automated strategies. [Download IB Gateway](https://www.interactivebrokers.com.hk/en/trading/ibgateway-latest.php)

Before use, verify `Paper` or `Simulated` mode, product and market permissions, and the selected software release channel (`Latest` or `Stable`).
