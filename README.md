Plain-English Browser Testing Agent
An AI-assisted browser automation tool that converts test cases written in plain English into browser actions. It uses a Groq-hosted AI model to plan actions and Playwright to interact with webpages and verify results.
Features
- Accepts a website URL and a plain-English test case.
- Inspects the current webpage and sends relevant page information to the AI model.
- Generates browser actions one step at a time.
- Uses Playwright to click links and buttons, fill fields, select options, interact with checkboxes, and verify expected results.
- Requests login credentials locally in the terminal when required.
- Produces a PASS/FAIL summary, a JSON report, and a screenshot.
Technology
- Python
- Groq API (AI model)
- Playwright
- Chromium
- python-dotenv
Requirements
- Python 3.10 or newer
- A Groq API key
- Internet connection
Setup
1. Clone or download this repository and open a terminal in the project folder.
2. Install the dependencies:
   py -m pip install -r requirements.txt
3. Install the Playwright Chromium browser:
   py -m playwright install chromium
4. Create a file named .env in the project folder and add your Groq API key:
   GROQ_API_KEY=your_groq_api_key
   GROQ_MODEL=auto
   MAX_STEPS=20
   KEEP_BROWSER_OPEN=true
   Do not commit or share this file.
Run
Start the program:
py test_agent.py
When prompted, enter:
1. The website URL.
2. The test case in plain English.
If the test requires authentication, enter the requested credentials in the terminal. The password is entered as hidden input.


Approach
1. The user supplies a URL and a plain-English test case.
2. The program inspects the page, including its title, visible text, and a limited set of interactive elements.
3. The page information and test case are sent to the Groq AI model.
4. The AI returns the next action as JSON.
5. Python interprets the action and Playwright performs it in the browser.
6. The program repeats this process until the AI finishes the test or the step limit is reached.
7. Assertions and the final AI decision are used to produce the test report.
Element matching uses available page semantics such as accessible roles, labels, placeholders, visible text, and generic fallbacks rather than relying on selectors specific to one website.

Limitations
- The tool depends on the Groq API, an available model, and an internet connection.
- AI-generated actions can be incorrect, ambiguous, or unsuitable for a particular page.
- Page inspection is limited to a short portion of page text and a limited number of interactive elements; relevant elements may be missed on large or complex pages.
- Custom controls, iframes, shadow DOM, CAPTCHAs, MFA, and websites that block browser automation may require additional handling or manual intervention.
- Element matching is not guaranteed to work on every website or every page structure.
- The current PASS logic requires an AI-requested PASS and at least one successful assertion. It does not always reject PASS when another action failed, so the action history, screenshot, and report should also be reviewed.
- The tool has been demonstrated on selected scenarios on PHPTravels, The Internet, and the Selenium demo form. These tests do not prove that it will work for every website or unseen test case.
