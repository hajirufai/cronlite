"""Allow running CronLite as a module: python -m cronlite"""

import sys
from cronlite.cli import main

sys.exit(main())
