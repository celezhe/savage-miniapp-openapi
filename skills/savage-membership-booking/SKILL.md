---
name: savage-membership-booking
description: Book or cancel a SAVAGE group class for a membership-card account. Use when the user asks to find an available class, reserve one class with membership benefits, inspect the resulting order, or cancel a reservation and return the membership asset.
---

# SAVAGE Membership Booking

Use only the user's account. Read `SAVAGE_TOKEN` from a private `.env` file with mode `600`. Never show the token, headers, order IDs, or private responses.

Use the endpoints and schemas in the `savage-miniapp-openapi` repository.

## Book one class

1. Call `POST /groupClass/schedule/scroll` for the requested Beijing date.
2. Match the exact class name, store, date, and time.
3. Call `POST /groupClass/schedule/detail` with the selected `scheduleId`.
4. Stop if the detail response does not permit booking.
5. Call `POST /inventory/status/batch-query`.
6. Stop unless the selected item has inventory status `NORMAL`.
7. Call `POST /order/settle/groupClass` with `firstSettle: true`, `quantity: 1`, and the `scheduleId`.
8. Stop unless the settlement has `settlementId`, `settlementVersion`, `item`, and `assetAllocations`.
9. Stop unless the membership-card plan makes the payable amount zero.
10. Show the exact class, location, date, time, and payable amount.
11. Get explicit approval for this exact reservation.
12. Call `POST /order/place` once. Use the settlement fields without modification.
13. Call `POST /payment/prepay` with the returned `orderId`.
14. Stop if `prePayItems` is not empty. Never call `wx.requestPayment`.
15. Call `POST /order/query/status` and `POST /order/paySuccess`.
16. Call `POST /order/list` with scene `COMPLETED`.
17. Report success only after the exact class appears in the completed orders.

Do not retry `order/place` after a timeout. First query `TO_PAY`, `COMPLETED`, and `ALL` to reconcile the result.

## Cancel one class

1. Call `POST /order/list` with scene `COMPLETED`.
2. Match the exact class name, date, time, and `orderItemId`.
3. Stop if the item is already refunded or cancelled.
4. Call `POST /refund/group-class/preview` with `orderItemId` and `quantity: 1`.
5. Call `POST /refund/reasons` with `productType: GROUP_CLASS`.
6. Show the exact class and the assets that the service will return.
7. Get explicit approval for this exact cancellation.
8. Call `POST /refund/group-class/apply` once with the preview `operationId`.
9. Call `POST /refund/order/detail` with the returned `refundOrderId`.
10. Report success only after the refund detail shows progress and returned assets.

Never cancel a different order when the match is ambiguous. Never expose order or refund identifiers in chat.

## Stop conditions

- On `401`, stop and use `$get-savage-token`.
- On `411`, `412`, or `429`, stop and report the business message.
- On a network error after a write request, query the related order before any retry.
- Never make concurrent booking or cancellation requests.
