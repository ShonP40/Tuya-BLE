# Bluetooth startup and cancellation

Bluetooth connection and the initial status refresh run in a config-entry
background task, so Home Assistant startup does not wait for the device handshake.
Entities can be temporarily unavailable until device reports arrive. For ordinary
(non-advertisement-gated) devices, initial refresh attempts time out after 60
seconds and retry with exponential backoff.

Status refreshes are cancelled before disconnecting on unload or shutdown.
Connection and GATT write handlers propagate cancellation, and command response
futures are cleaned up on cancellation or errors.

Regression tests in `tests/test_startup.py` cover startup while status is delayed
and cancelling refreshes before unload waits for disconnect. Tests in
`tests/test_ble_cancellation.py` cover connection/write cancellation and pending
response cleanup. Run with Home Assistant and the integration dependencies
installed:

```sh
python -m unittest discover -s tests -v
```
