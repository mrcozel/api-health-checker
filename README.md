API Health Checker



A Python-based API monitoring tool that checks endpoint availability, measures response times, detects failures, and sends email alerts when problems persist or services recover.



Built as a practical portfolio project to demonstrate skills in API troubleshooting, incident management, monitoring, logging, automated testing, and Python scripting.



Features



API endpoint monitoring: Checks configured HTTP/REST API endpoints.



Response-time measurement: Measures request duration in milliseconds.



Failure detection: Identifies unsuccessful HTTP responses, including server errors such as HTTP 500.



Slow-response detection: Flags successful responses that exceed a configurable response-time threshold.



Consecutive-failure alerts: Sends an email alert after an endpoint reaches a configurable failure threshold.



Recovery notifications: Sends an email when an endpoint recovers after an alert has been triggered.



Email integration: Uses the Brevo API to send email notifications.



JSON reporting: Saves the latest monitoring results to health\_report.json.



Historical CSV logging: Records monitoring results in health\_history.csv for trend analysis.



Rotating application logs: Writes diagnostic information to health\_checker.log and rotates log files to limit their size.



Continuous monitoring: Repeats checks every 60 seconds.



Error handling: Handles request timeouts, connection errors, and unsuccessful HTTP responses.



Automated testing: Includes unit tests for successful responses, failures, timeouts, alert thresholds, and recovery behaviour.



Continuous integration: Uses GitHub Actions to run automated tests when changes are pushed to the repository.



Technologies



Python



Requests



HTTP/REST APIs



JSON and CSV



Python unittest and unittest.mock



Python logging



Brevo API



Git and GitHub



GitHub Actions



Requirements



Python 3



Internet connection



Git (optional, for version control)



A Brevo account and API key for email alerts



Installation



Clone the repository:



git clone https://github.com/mrcozel/api-health-checker.git



Navigate to the project directory:



cd api-health-checker



Create a virtual environment:



python -m venv .venv



Activate the virtual environment on Windows:



.venv\\Scripts\\activate



Install the dependencies:



python -m pip install requests



Configuration



1\. Configure API endpoints



Edit health\_checker.py and update the ENDPOINTS list:



ENDPOINTS = \[

&#x20;   {

&#x20;       "name": "JSONPlaceholder API",

&#x20;       "url": "https://jsonplaceholder.typicode.com/posts/1"

&#x20;   },

]



TIMEOUT = 5

SLOW\_THRESHOLD\_MS = 1000

FAILURE\_THRESHOLD = 3



TIMEOUT: Maximum time to wait for a request, in seconds.



SLOW\_THRESHOLD\_MS: Response times above this value are classified as slow.



FAILURE\_THRESHOLD: Number of consecutive failed checks required before an alert is triggered.



The default monitoring interval is 60 seconds.



2\. Configure email alerts



Email notifications use the Brevo API.



Set your Brevo API key as an environment variable in Windows Command Prompt:



setx BREVO\_API\_KEY "your\_brevo\_api\_key"



Replace the placeholder with your actual API key. Open a new Command Prompt after running setx so the environment variable is available.



The API key is read from the environment and should not be hardcoded into the source code or committed to GitHub.



Make sure the sender address is verified in Brevo and that the email settings in email\_alerts.py match your intended sender and recipient.



To test the email integration separately:



python email\_alerts.py



Usage



Start continuous monitoring:



python health\_checker.py



The application checks the configured endpoints, displays their status, and updates the monitoring reports and logs. It then repeats the checks every 60 seconds.



Press Ctrl + C to stop monitoring.



Test failure alerts



The project includes a helper for testing the failure-alert workflow:



python health\_checker.py --test-alert



This test targets an HTTP endpoint that returns a server error and can send a real email if the failure threshold is reached. Use it only when you intend to test the email notification workflow.



Example Output



API HEALTH CHECKER

========================================



Checking: JSONPlaceholder API

Status: UP

HTTP code: 200

Response time: 184.74 ms



SUMMARY

========================================

Total endpoints: 1

Healthy: 1

Slow: 0

Failed: 0



Report saved to health\_report.json

Historical results saved to health\_history.csv



Response times and results are illustrative and will vary depending on network conditions and API availability.



Understanding the Results



Status



Meaning



UP



The endpoint returned a successful HTTP response within the configured response-time threshold.



SLOW



The endpoint returned a successful HTTP response but exceeded the response-time threshold.



FAIL



The request returned an unsuccessful HTTP status or encountered a request error.



Alert behaviour



Failure alert: Triggered after the configured number of consecutive failed checks.



Recovery alert: Sent when the endpoint returns to a healthy state after a failure alert has been sent.



Alert retry: If sending an alert fails, subsequent failed checks can retry the notification.



Monitoring logs: Record health checks, errors, and alert activity.



Failure counters are maintained in memory and reset when the application restarts.



Running Automated Tests



Run the unit tests from the project directory:



python -m unittest -v



The tests use mocked HTTP responses, so most unit tests do not depend on external APIs being available.



The test suite covers:



Successful HTTP responses.



HTTP server errors.



Request timeouts.



Connection failures.



Alerts after consecutive failures.



Recovery notifications.



Ensuring a slow response does not incorrectly trigger a recovery alert.



Continuous Integration



GitHub Actions automatically runs the unit tests when changes are pushed to the repository.



View the workflow and test results:

https://github.com/mrcozel/api-health-checker/actions



This helps verify that changes do not break the existing functionality.



Output Files



File



Purpose



health\_report.json



Stores the latest health-check results.



health\_history.csv



Stores historical check results for analysis.



health\_checker.log



Records application activity, errors, and alert events.



Generated reports and logs are excluded from version control where configured in .gitignore.



Potential Future Improvements



Add dashboard visualisations for historical response times and availability.



Persist failure state across application restarts.



Add configurable monitoring intervals and endpoint lists through environment variables or a configuration file.



Integrate additional notification channels, such as Microsoft Teams or Slack.



Add retry policies and more advanced alert-suppression controls.



Expand monitoring to include authentication, API response validation, and additional performance metrics.



Disclaimer



Only monitor endpoints you own or are authorised to test. Never commit API keys, credentials, or other sensitive information to public repositories.

