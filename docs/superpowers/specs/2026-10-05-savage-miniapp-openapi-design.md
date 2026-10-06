# SAVAGE Mini Program OpenAPI Design

## Purpose

This repository documents the observed SAVAGE WeChat Mini Program API.
It lets an authenticated user inspect classes and create an unpaid order for the user's account.

This project is unofficial. It has no association with SAVAGE or WeChat.
Users must only access accounts and data that they own or control.

## Scope

The repository contains an OpenAPI 3.1 specification as the source of truth.
The specification includes these verified operations:

- Exchange a WeChat login code for a SAVAGE access token.
- List group classes and get each `scheduleId`.
- Get the inventory status for a class.
- Create a settlement preview for a class.
- Create an unpaid order with `order/place`.
- List orders and get order details.
- Query an order status.

The specification does not include `payment/prepay`.
The project must not start a payment or call `wx.requestPayment`.

## Authentication

Protected endpoints use an HTTP bearer security scheme.
The client sends the token in the `Authorization` header.

The login endpoint accepts a short-lived code from `wx.login()`.
The login response contains `token`, `expireTime`, `userId`, and `unionid`.

The observed token is a JWT-shaped value without `exp`, `iat`, or `nbf` claims.
Clients must treat `expireTime` as the token expiration source.
The API does not return an observed refresh token.

If an API call returns `401`, the user must get a new `wx.login()` code.
The user must then call the login endpoint again.
The repository documents this process but does not automate WeChat.

## OpenAPI Structure

The root file is `openapi.yaml` and uses OpenAPI 3.1.
The file defines the production server URL and the bearer security scheme.

Reusable schemas define envelopes, errors, schedules, inventory items, settlements, orders, and login data.
Each operation has a stable `operationId`, request examples, and response examples.

The specification marks public endpoints without a security requirement.
The specification applies `bearerAuth` to protected endpoints.

The `order/place` operation includes an `x-side-effects` extension.
This extension states that the operation creates a real unpaid order and can reserve inventory.

## Repository Files

The repository contains these main files:

- `openapi.yaml`: The OpenAPI 3.1 specification.
- `README.md`: Usage, authentication, safety, and import instructions.
- `SECURITY.md`: Secret handling and vulnerability reporting.
- `LICENSE`: The MIT license.
- `.gitignore`: Token files, captures, environment files, and generated output.
- `examples/`: Sanitized request examples without personal data.
- `.github/workflows/validate.yml`: OpenAPI validation for each push and pull request.
- `docs/`: Static Swagger UI files for GitHub Pages.

## Data Flow

The user gets a WeChat code from the official WeChat client.
The login endpoint exchanges this code for a SAVAGE token.

The user calls the schedule endpoint and selects a `scheduleId`.
The user calls the inventory endpoint before settlement.

The settlement endpoint returns `settlementId`, `settlementVersion`, `variantCode`, and `tempItemId`.
The user sends these values to `order/place` without modification.

The place response returns `orderId` and `needPrepay`.
The documented flow stops after this response.

## Safety Controls

The repository must not contain real tokens, login codes, user IDs, union IDs, or order IDs.
The examples use obvious placeholder values.

The `.gitignore` file excludes `.env`, token files, proxy captures, and local response files.
The validation workflow scans tracked files for bearer-token patterns.

CAUTION: `order/place` creates a real order and can reserve a class seat.
Users must check existing `TO_PAY` orders before they create another order.

The README tells users to remove the proxy certificate after traffic inspection.
The README also tells users to disable the system proxy after inspection.

## Error Handling

The specification describes HTTP errors and API envelope errors.
The API can return HTTP 200 with a non-200 envelope `code`.

Clients must handle these conditions:

- `401`: Get a new WeChat code and log in again.
- `411` or `412`: Stop and show the business message.
- `429`: Stop and wait before another request.
- `400` or `500`: Stop and show the API message.
- Network timeout: Do not repeat `order/place` until an order-list check completes.

The last rule prevents duplicate orders after an uncertain response.

## Validation

The project uses Redocly CLI to validate `openapi.yaml`.
The workflow operates the validator on each push and pull request.

Tests parse the specification and make sure that required paths exist.
Tests also make sure that `payment/prepay` does not exist.

The repository does not operate live API tests in GitHub Actions.
Live tests require personal credentials and can create real orders.

## Publication

The local repository uses the `main` branch.
The public GitHub repository name is `savage-miniapp-openapi`.

The initial release uses the MIT license.
GitHub Pages publishes the static Swagger UI after the specification passes validation.

