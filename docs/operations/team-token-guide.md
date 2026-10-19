# Reporting access and private onboarding

This repository does not collect IBKR login credentials, Flex tokens, Query IDs or team registration information. Event-specific onboarding instructions and private portal addresses belong in the deployment owner's private configuration and records, outside this public repository.

IBKR Flex Web Service retrieves preconfigured reporting data using an access token and a query identifier. Follow the current [official configuration guide](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration) and review the fields and linked accounts included before authorizing any external consumer. IBKR login credentials are not part of the Flex API request.

Store reporting tokens only in the owner's secret store. Do not put them in source, Pages, task XML, command examples, screenshots or logs. A reporting authorization does not authorize this project's execution service to place orders. This public guide does not prescribe a particular team's portal workflow, token expiry, field selection or account activity.
