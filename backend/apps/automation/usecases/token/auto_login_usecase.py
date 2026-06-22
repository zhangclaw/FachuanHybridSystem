"""Stub: AutoLoginUsecase has been moved to plugins/court_automation/token/auto_login_usecase.py

This file re-exports from the plugin for backward compatibility.
"""

try:
    from plugins.court_automation.token.auto_login_usecase import *  # noqa: F403
    from plugins.court_automation.token.auto_login_usecase import AutoLoginUsecase, RetryConfig

except ImportError:
    pass
