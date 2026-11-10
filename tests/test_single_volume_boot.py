"""Boot configuration boundaries after removal of the separate OS/SystemOS disks."""
import importlib.util
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    spec = importlib.util.spec_from_file_location('single_volume_runner', ROOT / 'scripts/run-macos-vm.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, {'MACOS_ROOT_UUID': '354D4F10-9A79-4243-BA00-60FAB89D7561'}):
        spec.loader.exec_module(module)
    return module


class SingleVolumeBootTests(unittest.TestCase):
    def test_disk_window_matches_only_mmio_disk(self):
        runner = load_runner()
        command = runner.vm_command(5120)
        disks = [command[i + 1] for i, arg in enumerate(command) if arg == '--virtio-mmio-block']
        self.assertEqual(disks, [runner.STORE + ',lock=false'])
        self.assertEqual(runner.DATA_STORE_MMIO, 0x0a000000)
        self.assertEqual(runner.OS_UUID, runner.ROOT_UUID)

    def test_missing_install_does_not_create_empty_store(self):
        runner = load_runner()
        with patch.object(runner, 'sh', return_value='') as shell:
            with self.assertRaisesRegex(SystemExit, 'droidvm-app.py install'):
                runner.require_store(['adb'])
        self.assertEqual(shell.call_count, 1)
        self.assertTrue(shell.call_args.args[1].startswith('test -f '))

    def test_existing_install_is_kept(self):
        runner = load_runner()
        with patch.object(runner, 'sh', return_value='yes\n') as shell:
            runner.require_store(['adb'])
        self.assertEqual(shell.call_count, 1)

    def test_empty_root_uuid_cannot_select_legacy_layout(self):
        with patch.dict(os.environ, {'MACOS_ROOT_UUID': ''}):
            with self.assertRaisesRegex(SystemExit, 'MACOS_ROOT_UUID must name the System volume'):
                runpy.run_path(str(ROOT / 'scripts/run-macos-vm.py'))
