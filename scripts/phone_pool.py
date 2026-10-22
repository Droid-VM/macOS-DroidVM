"""Host hugepage pool preparation for a DroidVM guest (adapted unchanged from ios tools/run-xnu-boot.py, ios commit 9a1e72d)."""
import json
import subprocess
import time

POOL = '/sys/module/gh_hugepage_reserve/parameters'


def prepare_host_pool(adb, memory_mb, reserve_mb, evidence):
    """Size the host order-9 pool before VM creation; never disturb an owner."""
    def read_state():
        output = subprocess.check_output(adb + ['shell', 'cat', POOL + '/refill_stat'],
                                         text=True, timeout=15)
        state = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        for key in ('active_vms', 'served', 'acquire_active', 'pool_avail', 'pool_want', 'pool_want_with_cma'):
            state[key] = int(state[key])
        return state

    def write(name, value):
        # Both the path and the integer are owned by this program.
        subprocess.run(adb + ['shell', f'printf "%s\\n" {int(value)} > {POOL}/{name}'],
                       check=True, timeout=15)

    before = read_state()
    report = dict(memory_mb=memory_mb, reserve_mb=reserve_mb, before=before, verified=False)
    evidence.write_text(json.dumps(report, indent=2) + '\n')
    if before['active_vms'] or before['served'] or before['acquire_active']:
        raise RuntimeError('Host pool has VM owners, served pages or an active adjustment; refusing to resize it')
    maximum = int(subprocess.check_output(adb + ['shell', 'cat', POOL + '/pool_size_max'], text=True, timeout=15))
    hook = int(subprocess.check_output(adb + ['shell', 'cat', POOL + '/hook_enable'], text=True, timeout=15))
    target = reserve_mb // 2
    minimum = (memory_mb + 32 + 1) // 2  # RAM plus firmware/framebuffer/preparation headroom.
    if not hook or target < minimum or target > maximum:
        raise RuntimeError(f'Invalid reserve: hook={hook}, target={target}, minimum={minimum}, maximum={maximum}')
    if before['pool_want'] != target:
        write('pool_want', target)
    deadline, acquired = time.monotonic() + 30, False
    while True:
        state = read_state()
        report['after'] = state
        evidence.write_text(json.dumps(report, indent=2) + '\n')
        if state['active_vms'] or state['served']:
            raise RuntimeError('Another VM acquired the host pool during preparation')
        if state['pool_want'] != target:
            raise RuntimeError('Host pool target was clamped or changed concurrently')
        if not state['acquire_active'] and state['pool_avail'] >= target:
            report['verified'] = True
            evidence.write_text(json.dumps(report, indent=2) + '\n')
            print(f'Host hugepage pool ready: {state["pool_avail"]} x 2 MiB, target {reserve_mb} MiB', flush=True)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Host hugepage pool did not become ready; no VM was started')
        if not state['acquire_active'] and not acquired:
            write('acquire', 1)
            acquired = True
        time.sleep(1)
