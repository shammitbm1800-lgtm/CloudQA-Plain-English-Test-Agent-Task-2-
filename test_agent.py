import os
import re
import json
import getpass
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

# ---------- Configuration ----------
BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
KEY = os.getenv("GROQ_API_KEY", "").strip()
if not KEY:
    raise SystemExit("Add GROQ_API_KEY=... to your .env file.")

client = Groq(api_key=KEY)
MODEL_SETTING = os.getenv("GROQ_MODEL", "auto").strip()
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
KEEP_OPEN = os.getenv("KEEP_BROWSER_OPEN", "true").lower() in ("1", "true", "yes")
credentials = {}
assertions = 0


# ---------- AI ----------
def choose_models():
    """Choose one stable text/chat model; avoid audio and tool-specific models."""
    try:
        models = client.models.list()
        items = getattr(models, "data", models)
        found = []
        for item in items:
            name = getattr(item, "id", "")
            if not name:
                continue
            low = name.lower()
            if any(x in low for x in (
                "whisper", "guard", "embed", "tts", "speech",
                "orpheus", "playai", "transcribe"
            )):
                continue
            found.append(name)

        if MODEL_SETTING and MODEL_SETTING.lower() != "auto":
            if MODEL_SETTING in found:
                return [MODEL_SETTING]
            return [MODEL_SETTING]

        # Prefer known general-purpose text models, in a deterministic order.
        preferred = [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
        ]
        for name in preferred:
            if name in found:
                return [name]
        return found[:1]
    except Exception:
        return [MODEL_SETTING] if MODEL_SETTING and MODEL_SETTING.lower() != "auto" else []


def parse_action(raw):
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S | re.I).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise ValueError("AI did not return a JSON action.")
        obj = json.loads(match.group())
    if not isinstance(obj, dict) or not isinstance(obj.get("action"), str):
        raise ValueError("AI JSON must contain an action field.")
    return obj


def ask_ai(prompt):
    errors = []
    for model in choose_models():
        print("Using AI model:", model)
        try:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content":
                         "You are a browser testing agent. Return exactly one JSON object "
                         "with an action field. No markdown or explanation."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_completion_tokens=450
                )
            except Exception as exc:
                if not any(x in str(exc).lower() for x in
                           ("response_format", "json_object", "unsupported", "not supported")):
                    raise
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content":
                         "Return exactly one valid JSON object with an action field."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_completion_tokens=450
                )
            return parse_action(response.choices[0].message.content)
        except Exception as exc:
            errors.append(f"{model}: {exc}")
            print("Model attempt failed; trying another available model.")
    raise RuntimeError("No available Groq model completed the request. " + " | ".join(errors[-3:]))


# ---------- Page inspection and element matching ----------
def inspect(page):
    try:
        text = page.locator("body").inner_text(timeout=3000)[:900]
    except Exception:
        text = ""
    try:
        elements = page.locator(
            "input,button,select,textarea,a,[role=button],[role=link]"
        ).evaluate_all("""els => els.slice(0,28).map(e => ({
            tag:e.tagName.toLowerCase(), type:e.type || "",
            text:(e.innerText || e.getAttribute('aria-label') || "").trim().slice(0,55),
            placeholder:e.placeholder || "", name:e.name || "", id:e.id || "",
            label:e.getAttribute('aria-label') || ""
        }))""")
    except Exception:
        elements = []
    return {"url": page.url.split("?")[0], "title": page.title()[:120],
            "text": text, "elements": elements}


def visible(locator):
    try:
        for i in range(min(locator.count(), 6)):
            item = locator.nth(i)
            if item.is_visible():
                return item
    except Exception:
        pass
    return None


def locate_checkbox(page, target):
    """Find a checkbox input from its accessible label or associated label text."""
    target = str(target or "").strip()
    if not target:
        raise ValueError("AI supplied an empty checkbox target.")

    # Preferred accessible-label lookup.
    try:
        item = visible(page.get_by_role("checkbox", name=target, exact=False))
        if item:
            return item
    except Exception:
        pass

    try:
        item = visible(page.get_by_label(target, exact=False))
        if item and item.get_attribute("type") == "checkbox":
            return item
    except Exception:
        pass

    # Handle standard <label> elements that contain or reference the input.
    labels = page.locator("label").filter(has_text=target)
    for i in range(min(labels.count(), 12)):
        label = labels.nth(i)
        try:
            if not label.is_visible():
                continue
            nested = visible(label.locator("input[type=checkbox]"))
            if nested:
                return nested
            label_for = label.get_attribute("for")
            if label_for:
                linked = visible(page.locator("input[type=checkbox]").filter(
                    has=page.locator(f"#{label_for}")
                ))
                if linked:
                    return linked
        except Exception:
            continue

    # Some sites (including The Internet's checkbox exercise) do not use
    # <label> tags. Their text is a text node immediately after the input.
    # Match the nearby text belonging to each individual checkbox, rather
    # than the whole parent form (which may contain several checkbox labels).
    inputs = page.locator('input[type="checkbox"]')
    wanted = " ".join(target.lower().split())
    for i in range(min(inputs.count(), 30)):
        item = inputs.nth(i)
        try:
            if not item.is_visible() or not item.is_enabled():
                continue
            nearby = item.evaluate("""el => {
                const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const pieces = [];
                if (el.getAttribute('aria-label')) pieces.push(el.getAttribute('aria-label'));
                if (el.id) {
                    const byId = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                    if (byId) pieces.push(byId.innerText);
                }
                for (const node of [el.previousSibling, el.nextSibling]) {
                    if (node && node.nodeType === Node.TEXT_NODE) pieces.push(node.textContent);
                    if (node && node.nodeType === Node.ELEMENT_NODE) pieces.push(node.innerText);
                }
                if (el.parentElement) {
                    for (const child of el.parentElement.children) {
                        if (child !== el && child.tagName === 'LABEL') pieces.push(child.innerText);
                    }
                }
                return norm(pieces.join(' '));
            }""")
            if wanted and wanted in nearby:
                return item
        except Exception:
            continue

    raise LookupError(
        f"Could not associate the text '{target}' with a checkbox input. "
        "The page may use a custom checkbox structure."
    )


def locate(page, target):
    target = str(target or "").strip()
    low = target.lower()
    if not target:
        raise ValueError("AI supplied an empty element target.")
    vague = {
        "visible button/link", "button/link", "visible button",
        "button", "link", "visible element", "element", "field",
        "input", "text field"
    }
    if low in vague:
        raise ValueError(
            "AI supplied a vague target. It must name the actual visible label, "
            "placeholder, or field name from the page."
        )

    if "password" in low or "passcode" in low:
        item = visible(page.locator("input[type=password]"))
        if item:
            return item
    if any(x in low for x in ("email", "username", "user name")):
        item = visible(page.locator(
            "input[type=email],input[autocomplete=username],"
            "input[name*=email i],input[placeholder*=email i],"
            "input[name*=user i],input[placeholder*=user i],input[type=text]"
        ))
        if item:
            return item

    for locator in (
        page.get_by_label(target, exact=False),
        page.get_by_placeholder(target, exact=False),
        page.get_by_role("textbox", name=target, exact=False),
        page.get_by_role("button", name=target, exact=False),
        page.get_by_role("link", name=target, exact=False),
        page.get_by_role("checkbox", name=target, exact=False),
        page.get_by_role("radio", name=target, exact=False),
        page.get_by_text(target, exact=False)
    ):
        item = visible(locator)
        if item:
            return item

    # Generic fallback: if the planner says login/sign in but the page's
    # submit control has no accessible name, use it only when exactly one
    # visible submit control exists.
    if any(term in low for term in ("login", "log in", "sign in", "signin")):
        submits = page.locator(
            "button[type=submit],input[type=submit],button:not([type])"
        )
        visible_submits = []
        for i in range(min(submits.count(), 8)):
            candidate = submits.nth(i)
            try:
                if candidate.is_visible() and candidate.is_enabled():
                    visible_submits.append(candidate)
            except Exception:
                pass
        if len(visible_submits) == 1:
            return visible_submits[0]

    escaped = target.replace("\\", "\\\\").replace("'", "\\'")
    for selector in (f"[name='{escaped}']", f"#{escaped}"):
        item = visible(page.locator(selector))
        if item:
            return item
    raise LookupError(f"Could not find visible element: {target}")


# ---------- Plain-English test planner ----------
def next_action(test_case, page, history):
    data = inspect(page)
    have_creds = bool(credentials.get("email") and credentials.get("password"))
    prompt = f"""
Convert this plain-English browser test into its next single browser action.

TEST: {test_case[:700]}
PAGE: {json.dumps(data, separators=(',', ':'))[:3500]}
RECENT ACTIONS: {json.dumps(history[-6:], separators=(',', ':'))[:1200]}
CREDENTIALS ALREADY COLLECTED: {have_creds}

Return one JSON action:
{{"action":"click","target":"visible button/link"}}
{{"action":"fill","target":"email/username/password/field label","value":""}}
{{"action":"select","target":"dropdown label","value":"option"}}
{{"action":"check","target":"checkbox label"}}
{{"action":"uncheck","target":"checkbox label"}}
{{"action":"assert_checked","target":"checkbox label"}}
{{"action":"assert_unchecked","target":"checkbox label"}}
{{"action":"press","target":"field label","value":"Enter"}}
{{"action":"wait","value":1000}}
{{"action":"assert_text","target":"distinctive expected visible text"}}
{{"action":"assert_url","target":"URL fragment"}}
{{"action":"assert_visible","target":"distinctive visible element"}}
{{"action":"request_credentials","message":"why credentials are needed"}}
{{"action":"ask_user","message":"question"}}
{{"action":"finish","status":"PASS or FAIL","reason":"evidence-based reason"}}

Rules:
- Use only evidence from this page. Do not invent credentials or selectors.
- NEVER use generic targets such as "visible button/link", "button", "link", or "element".
  For a click, copy the actual visible button/link text from the page evidence.
- If a visible button has no text, use its aria-label or ask the user; do not guess.
- If credentials are already collected, do not ask for them again. For email/password fill, use an empty value; the program inserts the locally stored value.
- Do not repeat successful actions unnecessarily.
- After performing the requested task, run a specific assertion that proves the outcome.
- For login, do not treat generic public navigation (for example Login, Signup, My Booking) as proof of authentication.
  Verify a customer-specific account/dashboard element or authenticated state visible on this page.
- If login fails, inspect visible error text and finish FAIL.
- Never claim PASS without at least one successful assertion.
- If CAPTCHA/MFA blocks progress, ask the user for manual help; do not bypass it.
"""
    return ask_ai(prompt)


# ---------- Execute actions ----------
def clean_email(value):
    value = str(value).strip()
    value = re.sub(r"^(?:email(?:\s*/\s*username)?|username|user)\s*:\s*", "", value,
                   flags=re.I)
    return value.strip()


def execute(page, action):
    global assertions
    name = action["action"].lower()
    target = str(action.get("target", "")).strip()
    value = action.get("value", "")

    if name == "request_credentials":
        if credentials.get("email") and credentials.get("password"):
            return {"note": "Credentials already collected"}
        print("\nCredentials are entered locally and are not sent to the AI.")
        email = clean_email(input("Email / username: "))
        password = getpass.getpass("Password (input hidden): ")
        if not email or not password:
            raise ValueError("Email and password are required.")
        credentials.update(email=email, password=password)
    elif name == "fill":
        low = target.lower()
        if "password" in low or "passcode" in low:
            value = credentials.get("password", "")
        elif any(x in low for x in ("email", "username", "user name", "login")):
            value = credentials.get("email", "")
        if not value:
            raise ValueError(f"No value available for {target}.")
        field = locate(page, target)
        if field.input_value() != str(value):
            field.fill(str(value))
    elif name == "click":
        button = locate(page, target)
        button.click(timeout=12000)
        page.wait_for_timeout(900)
    elif name == "select":
        locate(page, target).select_option(label=str(value))
    elif name == "check":
        checkbox = locate_checkbox(page, target)
        if not checkbox.is_checked():
            checkbox.check()
    elif name == "uncheck":
        checkbox = locate_checkbox(page, target)
        if checkbox.is_checked():
            checkbox.uncheck()
    elif name == "assert_checked":
        checkbox = locate_checkbox(page, target)
        if not checkbox.is_checked():
            raise AssertionError(f"Checkbox '{target}' is not checked.")
        assertions += 1
    elif name == "assert_unchecked":
        checkbox = locate_checkbox(page, target)
        if checkbox.is_checked():
            raise AssertionError(f"Checkbox '{target}' is checked but should be unchecked.")
        assertions += 1
    elif name == "press":
        locate(page, target).press(str(value or "Enter"))
    elif name == "wait":
        page.wait_for_timeout(max(250, min(int(value or 1000), 6000)))
    elif name == "assert_text":
        page.get_by_text(target, exact=False).first.wait_for(state="visible", timeout=9000)
        assertions += 1
    elif name == "assert_url":
        if target.lower() not in page.url.lower():
            raise AssertionError(f"URL does not contain '{target}'. Current URL: {page.url}")
        assertions += 1
    elif name == "assert_visible":
        locate(page, target).wait_for(state="visible", timeout=9000)
        assertions += 1
    elif name == "ask_user":
        input("\n" + str(action.get("message", "Manual help needed")) + "\nPress Enter when ready...")
    else:
        raise ValueError(f"Unsupported action: {name}")
    return {}


# ---------- Report and runner ----------
def save_report(page, status, reason, history, started):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shot = BASE / f"test_result_{stamp}.png"
    report = BASE / f"test_report_{stamp}.json"
    final_url = page.url if page else ""
    try:
        if page and not page.is_closed():
            page.screenshot(path=str(shot), full_page=True, timeout=15000)
    except Exception as exc:
        print("Screenshot could not be saved:", exc)
        shot = None
    data = {
        "status": status, "reason": reason, "final_url": final_url,
        "total_actions": len(history),
        "successful_actions": sum(x["result"] == "SUCCESS" for x in history),
        "failed_actions": sum(x["result"] == "FAILED" for x in history),
        "verified_assertions": assertions, "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "history": history, "screenshot": str(shot) if shot else None
    }
    report.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("\n" + "=" * 48)
    print("          PLAIN-ENGLISH TEST REPORT")
    print("=" * 48)
    for key, value in (
        ("STATUS", status), ("REASON", reason), ("FINAL URL", final_url),
        ("TOTAL ACTIONS", data["total_actions"]),
        ("SUCCESSFUL ACTIONS", data["successful_actions"]),
        ("FAILED ACTIONS", data["failed_actions"]),
        ("VERIFIED ASSERTIONS", assertions),
        ("SCREENSHOT", shot or "Not saved"), ("JSON REPORT", report)
    ):
        print(f"{key + ':':24} {value}")
    print("=" * 48)


def run_test():
    global assertions
    assertions = 0
    credentials.clear()
    website = input("Enter website URL: ").strip()
    test_case = input("Enter test case in plain English: ").strip()
    if not website or not test_case:
        raise SystemExit("Website URL and test case are required.")
    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    history, status = [], "FAIL"
    reason = "Test did not complete."
    started = datetime.now().isoformat(timespec="seconds")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1365, "height": 900})
        page.set_default_timeout(10000)
        try:
            page.goto(website, wait_until="domcontentloaded", timeout=60000)
            print("\nOpened:", page.url)
            failures = 0
            for step in range(1, MAX_STEPS + 1):
                action = next_action(test_case, page, history)
                name = action["action"].lower()
                print(f"\nStep {step}: {name} {action.get('target', '')}".rstrip())

                if name == "finish":
                    requested = str(action.get("status", "FAIL")).upper()
                    reason = str(action.get("reason", "AI finished the test."))
                    # A recovered exploratory action may fail without invalidating
                    # the test. PASS depends on the requested outcome being verified
                    # by successful assertions, not on every exploratory action.
                    if requested == "PASS" and assertions > 0:
                        status = "PASS"
                    else:
                        status = "FAIL"
                        if requested == "PASS":
                            reason = "PASS rejected: no successful browser assertion. " + reason
                    break

                if name == "request_credentials" and credentials.get("email") and credentials.get("password"):
                    history.append({"action": name, "result": "SKIPPED",
                                    "note": "Credentials already collected"})
                    continue
                try:
                    execute(page, action)
                    safe_action = dict(action)
                    if any(x in str(safe_action.get("target", "")).lower()
                           for x in ("email", "username", "password", "login")):
                        safe_action["value"] = "[REDACTED]"
                    history.append({"action": safe_action, "result": "SUCCESS"})
                    failures = 0
                except Exception as exc:
                    history.append({"action": action, "result": "FAILED", "error": str(exc)[:250]})
                    failures += 1
                    print("Action failed:", exc)
                    if failures >= 3:
                        reason = "Three consecutive actions failed."
                        break
            else:
                reason = f"Maximum step limit ({MAX_STEPS}) reached."
        except KeyboardInterrupt:
            reason = "Interrupted by user."
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            print("\nTEST ERROR:", reason)
        finally:
            save_report(page, status, reason, history, started)
            if KEEP_OPEN:
                input("\nBrowser is open. Press Enter to close it...")
            browser.close()


if __name__ == "__main__":
    run_test()
