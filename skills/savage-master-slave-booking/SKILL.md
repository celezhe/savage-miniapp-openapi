---
name: savage-master-slave-booking
description: Monitor SAVAGE class availability with a slave account and perform one authorized zero-cash membership booking or waitlist attempt with a master account. Use for scheduled or availability-triggered SAVAGE reservations with separate monitoring and booking tokens.
---

# SAVAGE Master / Slave Booking

Use the bundled scripts for deterministic execution. Read [runner.md](references/runner.md) for configuration, endpoint sequence and limitations. The config template is [runner-config.json](assets/runner-config.json).

## Accounts and authorization

- During monitoring, the slave token only queries identity and settlement previews; the monitoring script never places orders or calls payment endpoints.
- All live testing uses the slave account. Separately authorized unpaid-order tests may use the slave, but are outside the monitoring script. Never use the master for testing.
- Master token is used only for the user's explicitly authorized classes. Check its account ID and membership status before submitting.
- Confirm the exact date, time in Beijing, store, class and scheduleId, whether FULL inventory may use waitlisting, and the trigger rule. Existing explicit authorization remains valid for those exact choices.
- Only membership deductions with both cashPay and payableAmount equal to zero may proceed. Never invoke wx.requestPayment. Nonzero or unknown amounts stop the attempt.
- Credentials live in separate private env files outside the skill/repository, permissions 600, each with SAVAGE_TOKEN. Never display credentials or private order identifiers.

## Configure or continue

Set SAVAGE_RUNNER_CONFIG to a private JSON file containing master_env_file, slave_env_file, master_account_id, slave_account_id, runtime_dir, start_utc and classes. Classes specify id (scheduleId), classId, name, start, end and room; course start/end values use Beijing local time, start_utc includes a UTC offset.

Before starting a watcher, inspect the private runtime status, PID and once marker. If an authorized watcher is already running, inspect it instead of starting another. Never silently replace an existing scheduled job or switch accounts.

Run from this skill directory:

```sh
export SAVAGE_RUNNER_CONFIG=/absolute/private/runner-config.json
python3 scripts/booking_runner.py
python3 scripts/check_booking_open.py
python3 scripts/watch_and_book.py
```

The first command is offline. The second checks once. The third launches real monitoring and can trigger real authorized zero-cash reservations. Obtain authorization before the third command; the skill itself grants none. Polling defaults to 60 seconds when the user requests per-minute monitoring.

## Submission invariants

- Both/all configured classes must successfully enter settlement before the watcher invokes the master once. A user request to process each independently requires a code/config change, not an improvised request.
- NORMAL inventory uses normal booking. FULL requires settlement isQueue=1 and exactly one selected deadlineOptions value; use that value as waitDeadlineOption without guessing.
- Match the exact class, times, room and IDs, and check existing orders. Missing fields stop the relevant class.
- Acquire process locks. Persist the whole-run marker using O_EXCL and each placement intent before submitting. Never remove those records to retry.
- Each class may call order/place at most once. On timeout, reconcile orders; do not blindly retry. Treat uncertain outcomes as requiring review.
- Complete only the zero-cash prepay path; nonempty or missing prePayItems stops further progression.
- Confirm the returned orderId in COMPLETED. Confirm waitlist state from order details; waitlisting is not a guaranteed class place. Report uncertain state honestly.

## Monitor and stop

Read runtime_dir/work/watch-and-book-status.json for progress. Notify only on opening, completion, failure or required user action; stay quiet when unchanged. Stop on identity failure, 401, 411 or 429. A 412 during slave monitoring means not yet available. Network failure does not mean token expiry.

The watcher stops at start_utc plus 10 minutes and exits after one master invocation, even if it fails. It does not auto-restart. Direct timed execution is limited to the first 60 seconds after start_utc; event mode follows actual opening, including early opening. Explain these semantics when the user requires exact timing. Never promise exact-second scheduling or successful allocation.

Tests with nonmember accounts can check settlement or create separately authorized unpaid orders, but must not bypass the production runner's zero-cash guards. Real membership zero-cash booking and final waitlist activation have not yet been verified end to end.
