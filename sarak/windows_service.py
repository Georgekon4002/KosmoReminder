"""
Windows Service wrapper for SMS/Viber Sender.

Installation:
    python install_service.py install
    python install_service.py start
    python install_service.py stop
    python install_service.py remove

Requires: pip install pywin32
After install: python -m win32com.client.makepy  (one-time setup)
"""
import logging
import sys
from pathlib import Path

# Add project root to path when running as service
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import win32service
    import win32serviceutil
    import win32event
    import servicemanager

    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("pywin32 not available – Windows Service features disabled")

from src.config import AppConfig, ServiceConfig
from src.service_runner import ServiceRunner

logger = logging.getLogger(__name__)


if WIN32_AVAILABLE:

    class SMSSenderService(win32serviceutil.ServiceFramework):
        """Windows Service that wraps ServiceRunner."""

        _svc_name_ = "SMSViberSender"
        _svc_display_name_ = "SMS/Viber Sender Service"
        _svc_description_ = "Αυτόματη αποστολή SMS και Viber μηνυμάτων"

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.runner: ServiceRunner | None = None

            # Load config from service executable directory
            cfg = AppConfig.load(ROOT / "config.json")
            self._config = cfg

            # Override service name from config
            self._svc_name_ = cfg.service.service_name
            self._svc_display_name_ = cfg.service.service_display_name
            self._svc_description_ = cfg.service.service_description

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            if self.runner:
                self.runner.stop()

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            self._run()

        def _run(self):
            import threading
            config = self._config
            self.runner = ServiceRunner(config)

            t = threading.Thread(target=self.runner.start, daemon=True)
            t.start()

            # Wait for stop signal
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            self.runner.stop()

            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, ""),
            )


def run():
    if not WIN32_AVAILABLE:
        print("ERROR: pywin32 is required for Windows Service.")
        print("Install with: pip install pywin32")
        sys.exit(1)
    win32serviceutil.HandleCommandLine(SMSSenderService)


if __name__ == "__main__":
    run()
