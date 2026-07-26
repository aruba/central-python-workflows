"""Tests for device model construction."""

import unittest

from utils.models import Device


class DeviceFromApiObjectTests(unittest.TestCase):
    def test_reads_the_firmware_version_attribute(self):
        class FakeAccessPoint:
            pass

        ap = FakeAccessPoint()
        setattr(ap, "firmware-version", "10.7.0.0")

        device = Device.from_api_object(ap)

        self.assertEqual(device.firmware, "10.7.0.0")


if __name__ == "__main__":
    unittest.main()
