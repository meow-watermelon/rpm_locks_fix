#!/usr/bin/env python3

import os
import re
import signal
import subprocess

def get_pid(filename):
    pids = []
    lsof_cmd = subprocess.run(args=['lsof', '-Fp', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    for i in lsof_cmd.stdout.strip().splitlines():
        pid = re.match(r'^p(\d+)', i)
        if pid:
            pids.append(int(pid.group(1)))

    return pids            

if __name__ == '__main__':
    rpm_db_home = '/var/lib/rpm'
    rpm_runtime_locks = [rpm_db_home+'/'+'.dbenv.lock', rpm_db_home+'/'+'.rpm.lock']

    for f in rpm_runtime_locks:
        if os.path.exists(f):
            rpm_runtime_pids = get_pid(f)
            if rpm_runtime_pids:
                print('RPM RUNTIME LOCK: following PID(s) attach(es) the lock file %s:' %(f))
                print(rpm_runtime_pids)
                for p in rpm_runtime_pids:
                    print('RPM RUNTIME LOCK: sending the signal KILL to %d' %(p))
                    os.kill(p, signal.SIGKILL)
            else:
                print('RPM RUNTIME LOCK: no process attaches the lock file %s, skip this procedure...' %(f))
        else:
            print('RPM RUNTIME LOCK: %s does not exist, skip this procedure...' %(f))
