# Platform support

The Python scripts target Windows, macOS and Linux with Python 3.10+. CI runs offline tests on all three. Cross-process locking, Unicode paths, UTF-8 BOM configuration, private token storage, capture filtering and logging are tested. This does not establish live SAVAGE account compatibility or successful booking.

## Commands

POSIX shells use `export VARIABLE=value` and `python3`; PowerShell uses `$env:VARIABLE = "value"` and `python`. For example:

```powershell
$env:SAVAGE_ENV_FILE = "C:/private/savage.env"
python scripts/save_login_response.py --env-file $env:SAVAGE_ENV_FILE
```

Use UTF-8 files. Windows paths in JSON can use forward slashes, such as `C:/private/savage.env`; backslashes require JSON escaping. POSIX requires private mode 600. Windows must use a private NTFS directory with restricted ACLs; chmod cannot provide this protection. Runtime files inherit that directory's ACL.

## Capture prerequisites

Capture requires a supported official WeChat client running the SAVAGE mini program and a proxy tool. These are external application requirements, not provided by the Python scripts. macOS uses Keychain certificate trust; Windows uses its certificate store. Do not follow macOS Keychain or network-service commands on Windows. Use the selected proxy vendor's platform-specific setup. On Linux, do not assume a supported native WeChat mini-program runtime exists: use an official client on a supported device through the proxy when available, or import an already captured login response. If no compatible client is available, explain that capture cannot be completed on that machine.

mitmproxy addons require mitmproxy in the proxy's runtime. Install with `uv tool install mitmproxy`, then use `uv tool run mitmdump` instead of assuming `~/.local/bin/mitmdump` exists. In PowerShell:

```powershell
$env:SAVAGE_ENV_FILE = "C:/private/savage.env"
uv tool run mitmdump --listen-port 9090 --set flow_detail=0 --scripts scripts/capture_token.py
```

Certificate trust, TLS pinning, proxy routing and interactive WeChat login require real device verification. mitmproxy capture remains experimental; do not claim it works solely because addon tests pass. Restore system proxy settings after capture on every OS. Never disable TLS verification to make a test pass.
