# Unified Logging

**Purpose**: All Python files in `$PROJECT_ROOT/` MUST use the unified logging module.

## Required Pattern

```python
# MANDATORY - Unified logging_util
from mvp_site import logging_util
logging_util.info("message")
logging_util.warning("something concerning")
logging_util.error("something failed")
logging_util.debug("debug info")
```

## Forbidden Pattern

```python
# FORBIDDEN - Direct logging module
import logging
logger = logging.getLogger(__name__)
logger.info("message")
```

## Benefits

- Unified output to both GCP Cloud Logging (stdout) and local file
- Automatic log file path: `/tmp/<repo>/<branch>/<service>.log`
- Consistent emoji formatting for errors and warnings
- Single initialization point - no duplicate handlers

## Exceptions

Test files (`$PROJECT_ROOT/tests/*`) may use direct logging.
