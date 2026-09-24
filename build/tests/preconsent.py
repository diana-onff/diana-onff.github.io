"""Start every browser test as a returning visitor who has already answered
the welcome screen.

Since the privacy package, a device that has never opened Diana gets a
full-screen welcome screen first (location explanation + the statistics
question), and the startup position request waits until it is answered.
That is right for a real first visit, and test_privacy.py tests exactly that.
Every other test is about something else, and would otherwise find the
screen covering whatever it tries to tap, or a map that has not located
itself yet.

Importing this module is all a test needs to do: from then on every new
browser context in that test starts with the answer on record (statistics:
no), unless the test has put a different answer there itself. Only the two
consent keys are touched; nothing else in localStorage.
"""
from playwright.sync_api import Browser

PRE_CONSENT = """
try {
  if (!localStorage.getItem('diana.consent.seen')) {
    localStorage.setItem('diana.consent.seen', '1');
    if (!localStorage.getItem('diana.consent.stats')) localStorage.setItem('diana.consent.stats', '0');
  }
} catch (e) {}
"""

_new_context = Browser.new_context


def _answered_context(self, *args, **kwargs):
    ctx = _new_context(self, *args, **kwargs)
    ctx.add_init_script(PRE_CONSENT)
    return ctx


Browser.new_context = _answered_context
