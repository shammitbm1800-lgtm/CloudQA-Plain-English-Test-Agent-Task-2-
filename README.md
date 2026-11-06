# Plain-English Browser Testing Agent

A small AI-assisted browser automation tool that converts a test case written in plain English into browser actions. It uses the Groq API to plan actions and Playwright to interact with the website and verify results.

## Features

- Accepts a website URL and a plain-English test case.
- Uses an AI model available through Groq to choose browser actions.
- Uses Playwright to inspect pages and interact with visible elements.
- Supports common actions such as clicking, filling fields, selecting options, checking/unchecking controls, waiting, and assertions.
- Requests credentials in the terminal when needed; credentials are entered locally rather than included in the AI prompt.
- Produces a timestamped screenshot and JSON test report.
- Keeps the browser open after the run when configured to do so.

## Technology

- Python
- Groq API
- Playwright (Chromium)
- python-dotenv

## Project files

```text
CloudQA_Task2/
├── test_agent8.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── .env                 # local only; do not commit or share
└── test_result_*.png    # generated screenshots
    test_report_*.json   # generated reports
```

## Requirements

- Python 3.10 or newer
- A Groq API key
- Internet access
- Windows, macOS, or Linux

## Setup

1. Open a terminal in the project directory.
2. Create and activate a virtual environment (recommended):

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows Command Prompt**
   ```bat
   py -m venv .venv
   .venv\Scripts\activate.bat
   ```

3. Install Python dependencies:

   ```bash
   py -m pip install -r requirements.txt
   ```

4. Install the Playwright Chromium browser:

   ```bash
   py -m playwright install chromium
   ```

5. Copy `.env.example` to `.env` and add your own Groq API key:

   ```env
   GROQ_API_KEY=your_actual_key
   GROQ_MODEL=auto
   MAX_STEPS=20
   KEEP_BROWSER_OPEN=true
   ```

   Never commit or share `.env`. The `.gitignore` file excludes it.

## Run

```bash
py test_agent8.py
```

The program prompts for:

1. Website URL
2. Plain-English test case

If the requested test requires login, the program may ask for the username/email and password in the terminal.

## Example test cases

**Navigation**
```text
Open the Checkboxes page and verify that the page heading "Checkboxes" is displayed.
```

**Checkbox interaction**
```text
Select checkbox 1 and verify that checkbox 1 is checked. Also verify that checkbox 2 remains checked.
```

**Form submission**
```text
Enter "Shammit" into the Text input field. Submit the form and verify that the submission confirmation page displays "Received!".
```

## Output

After a run, the program writes files in the project directory:

- `test_result_<timestamp>.png` — screenshot of the browser result.
- `test_report_<timestamp>.json` — structured test report containing the status, reason, final URL, action counts, assertion count, and output file paths.

The browser remains open when `KEEP_BROWSER_OPEN=true`. Press Enter in the terminal to close it.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GROQ_API_KEY` | API key used to access Groq | Required |
| `GROQ_MODEL` | Model name, or `auto` for automatic selection | `auto` |
| `MAX_STEPS` | Maximum number of AI-planned steps per test | `20` |
| `KEEP_BROWSER_OPEN` | Keep the browser open after the run | `true` |

## Demonstration coverage

The project was manually exercised against multiple test scenarios on different practice websites, including:

- PHPTravels demo: customer login/dashboard verification and booking lookup interface.
- The Internet: navigation to the Checkboxes page and checkbox state interaction.
- Selenium demo web form: text entry, form submission, and confirmation text verification.

These demonstrations show the tested scenarios; they do not guarantee that every arbitrary website or instruction will work. Dynamic websites, CAPTCHAs, MFA, custom controls, authentication restrictions, and ambiguous instructions may require additional handling.

## Security notes

- Keep API keys in `.env`; do not put them in source code.
- Do not commit `.env` or share screenshots/reports containing personal or sensitive information.
- Use test accounts and websites where you have permission to automate interactions.
