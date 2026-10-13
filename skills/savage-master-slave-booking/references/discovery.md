# Resolve a screenshot to a SAVAGE schedule

The user's screenshot supplies selection criteria, not IDs. Query using the private slave token only. Do not place an order merely to identify a class.

Use the current repository OpenAPI for city identifiers and optional filter fields. This is an observed Beijing query shape; change the date and city to the user's actual selection:

```json
{
  "queryParam": {
    "scene": "MAIN",
    "longitude": "116.4074",
    "latitude": "39.9042",
    "cityCode": "BJS",
    "scheduleDate": "2026-10-17",
    "scheduleTimePeriods": [],
    "categoryIds": [],
    "classTypes": [],
    "roomIds": [],
    "storeIds": [],
    "roomTypes": [],
    "requireFavoriteCoach": false,
    "searchText": "",
    "displayCompleted": false
  },
  "cursor": "",
  "limit": 100
}
```

POST `/backend-api/groupClass/schedule/scroll`. Response data.list contains rooms; each room has roomName, storeId and itemList. Each item includes scheduleId, classId, scheduleName, startTime, endTime and often publishTime. Follow hasNext/nextCursor using cursor; guard against repeated cursors.

Match all visible criteria. Normalize leading/trailing whitespace and reasonable English case differences, but do not relax date, start/end time or store. Similar names or different rooms are not interchangeable. Confirm exactly one candidate with POST `/backend-api/groupClass/schedule/detail`, body `{"scheduleId": <observed ID>}`. Confirm coach if the screenshot includes it and the detail returns it.

If the date has no year or the store has no city, use explicit conversation context. Otherwise clarify. If a screenshot's displayed price differs, disclose that difference before booking. Do not assume its price is the master's final payable amount.

Write the verified records into a private config: id = scheduleId, classId, name = scheduleName, start/end from the API, room = roomName. Use the returned publishTime as evidence for start_utc only after confirming its timezone and consistency across the selected classes. The user need not provide any ID or JSON.

When the classes have different opening times, the current all-open watcher may delay the earlier class. Explain this and resolve the desired behavior before launching; do not silently claim per-class immediate booking.
