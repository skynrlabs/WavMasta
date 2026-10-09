# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| Latest release on `main` | ✅ |
| Older releases | ❌ — please update |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report vulnerabilities privately via GitHub's built-in security advisory system:

1. Go to the [Security tab](https://github.com/skynrlabs/WavMasta/security/advisories) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the details — include steps to reproduce, affected component, and potential impact.

You will receive an acknowledgement within **5 business days**. We aim to triage and respond with a remediation plan within **14 days** of receiving a valid report.

---

## Scope

In scope:

- Malicious or malformed audio files causing code execution or writing files outside the chosen output folder
- Unsafe handling of the settings file or temporary preview files

Out of scope:

- Vulnerabilities in third-party dependencies such as pedalboard, NumPy or SciPy (report those upstream)
- Issues requiring physical access to the device
- Social engineering attacks

---

## Security Design

- **Local only.** WavMasta runs entirely on your computer. Audio is never uploaded.
- **No accounts, no network calls.** The app does not contact any server.
- **Local storage.** Settings are stored in `settings.json` in your user app-data folder (`%APPDATA%\WavMasta` on Windows); previews are written to your system temp folder.

---

## Disclosure Policy

Once a fix is released, we will publish a GitHub Security Advisory crediting the reporter (unless they request anonymity). We ask that reporters observe a **90-day coordinated disclosure** window from the time of our acknowledgement before publishing independently.
