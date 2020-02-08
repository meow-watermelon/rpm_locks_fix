#!/usr/bin/env python3

import glob
import os
import re
import signal
import subprocess
import sys

def get_pid(filename):
    pids = []

    lsof_cmd = subprocess.run(args=['lsof', '-Fp', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    for i in lsof_cmd.stdout.strip().splitlines():
        pid = re.search(r'^p(\d+)', i)
        if pid:
            pids.append(int(pid.group(1)))

    return pids            

def get_db_lock_holder_pid(db_path):
    pids = []

    db_stat_cmd = subprocess.run(args=['db_stat', '-h', db_path, '-Cl'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    for i in db_stat_cmd.stdout.strip().splitlines():
        pid = re.search(r'pid/thread\s+(\d+)/\d+', i)
        if pid:
            pids.append(int(pid.group(1)))

    '''
    dedup lock holder PIDs
    '''
    pids = list(set(pids))

    return pids

def test_lock_holder_pid_exist(pid_list):
    active_pids = []
    stale_pid_count = 0

    for p in pid_list:
        try:
            os.kill(p, 0)
        except ProcessLookupError:
            stale_pid_count += 1
        else:
            active_pids.append(p)

    lock_holder_stat = [stale_pid_count, active_pids]

    return lock_holder_stat

if __name__ == '__main__':
    '''
    only run by root
    '''
    if os.getuid() != 0:
        print('THIS TOOL MUST RUN BY ROOT USER')
        sys.exit(1)

    '''
    define rpm environment variables
    '''
    rpm_db_home = '/var/lib/rpm'
    rpm_runtime_locks = [rpm_db_home+'/'+'.dbenv.lock', rpm_db_home+'/'+'.rpm.lock']

    '''
    procedure 0: test rpm db
    '''
    try:
        rpm_run_cmd = subprocess.run(args=['rpm', '-qa'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, encoding='utf-8', timeout=120)
    except subprocess.TimeoutExpired:
        '''
        procedure 1: fix rpm runtime locks. 
        '''
        print('RPM RUNTIME LOCK: possible rpm runtime locks detected')

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
    else:
        if rpm_run_cmd.stderr or rpm_run_cmd.returncode != 0:
            '''
            procedure 2: fix rpm berkeley db stale locks.
            '''
            print('RPM DB STALE LOCK: possible rpm db stale locks detected')

            rpm_db_lock_holder_pids = get_db_lock_holder_pid(rpm_db_home)
        
            if rpm_db_lock_holder_pids:
                rpm_db_lock_holder_stat = test_lock_holder_pid_exist(rpm_db_lock_holder_pids)
                if not rpm_db_lock_holder_stat[1]:
                    print('RPM DB STALE LOCK: %d stale lock holder(s) found' %(rpm_db_lock_holder_stat[0]))
        
                    rpm_db_lock_files = glob.glob(rpm_db_home+'/'+'__db.*')
                    for l in rpm_db_lock_files:
                        print('RPM DB STALE LOCK: deleting stale lock file %s...' %(l))
                        os.unlink(l)
        
                    print('RPM DB STALE LOCK: rpm db lock file(s) deleted')
                else:
                    print('RPM DB STALE LOCK: active process(es) still attach(es) the db lock(s), skip this procedure...')
                    print('RPM DB STALE LOCK: active process(es): ', rpm_db_lock_holder_stat[1])
            else:
                print('RPM DB STALE LOCK: no stale lock holder(s) found, skip this procedure...')
        else:
            print('RPM DB LOCK STATUS LOOKS CLEAN')
