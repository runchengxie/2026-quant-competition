# FundConnectHK Team Token Setup Guide

This English guide was prepared with the organizer's permission from the team reference material. The original PDF is not distributed in this repository. Follow the latest instructions in the team portal if the workflow changes.

## What is an IBKR Flex Token?

An IBKR Flex Token authorizes an external system to retrieve account statement data, such as account values, positions, trades, cash activity, and reports. It is for report retrieval only; it does not grant trading, transfer, or withdrawal permission.

## Before you start

- Your IBKR account is open.
- You can sign in to the IBKR Client Portal.
- Sign in with the account's primary user. Some linked accounts may require Master Account access.

## Create a token

1. Sign in to the [IBKR website](https://www.interactivebrokers.com.hk/cn/home.php).
2. Open report settings.
3. Configure the Flex Web Service.
4. Select the option to generate a new token.
5. Set the expiry period to `1 Year`.
6. Create the token and copy it to your local secret manager.

Creating a new token replaces the previous token. Do not put the token in source control or send it through an unverified channel.

## Create a Query ID

1. Open the option to create an Activity Flex Query.
2. Enter a query name using English characters.
3. Select the required query sections. The original team instructions suggested selecting all sections; apply least privilege if the organizer specifies a narrower field set.
4. Set the send period to the past 365 calendar days if that remains the organizer's requirement.
5. Continue to review the Activity Flex Query.
6. Create the query and copy its Query ID.

## Submit to the team portal

Sign in to the [FundConnectHK team portal](https://team.fundconnecthk.com/login) and submit the Flex Token and Query ID through the approved form. Never submit an IBKR login password.

## First completed trade

After the token and Query ID are linked, the account may need at least one completed buy or sell transaction. An unfilled order does not count as a completed trade. If the account has no completed trades, the system may validate the IBKR credentials but the latest Flex report may contain no trade data. After a completed transaction, later automatic synchronization should update the performance record without linking the token again.

## Security

- Do not commit the token, Query ID, or account password to a public repository.
- Submit credentials only through a verified team system.
- Although a Flex Token cannot place trades, it is sensitive account authorization data and must be handled like a secret.
