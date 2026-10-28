from pathlib import Path
import plistlib
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from install_refresh_agents import agent_config

class AgentTests(unittest.TestCase):
    def test_both_agents_are_timezone_explicit_and_cannot_publish(self):
        runtime=Path('/a path/runtime');state=Path('/a path/state')
        for kind,after in [('refresh','03:00'),('schedules','03:45')]:
            config=agent_config(kind,runtime,state,Path('/venv/bin/python'),'/runtime/node')
            plist=plistlib.loads(plistlib.dumps(config))
            args=plist['ProgramArguments']
            self.assertEqual(args[args.index('--daily-after-utc')+1],after)
            self.assertEqual(plist['StartInterval'],3600)
            self.assertEqual(args[0],'/venv/bin/python')
            self.assertTrue(args[1].startswith('/a path/runtime/scripts/'))
            self.assertFalse(any('deploy' in arg or 'commit' in arg for arg in args))
            self.assertEqual(plist['EnvironmentVariables']['PATH'],'/runtime:/usr/bin:/bin:/usr/sbin:/sbin')

if __name__=='__main__':unittest.main()
