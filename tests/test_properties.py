import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

DEFAULT_DEVICES = [
    {'name': 'Mic 1', 'max_input_channels': 1},
    {'name': 'Speakers', 'max_input_channels': 0},
    {'name': 'Mic 2', 'max_input_channels': 2},
]

sd_mock = MagicMock()
sd_mock.query_devices.return_value = DEFAULT_DEVICES
sys.modules['sounddevice'] = sd_mock

from audio_recorder import properties as props_mod
from mo.core.plugin.models.properties import PropertyType


class TestProperties(unittest.TestCase):

    def test_microphone_options_input_only(self):
        opts = props_mod.get_microphone_options()
        self.assertEqual(len(opts), 2)

    def test_microphone_option_labels(self):
        opts = props_mod.get_microphone_options()
        labels = [o.label for o in opts]
        self.assertIn('Mic 1', labels)
        self.assertIn('Mic 2', labels)

    def test_microphone_options_no_input_fallback(self):
        with patch.object(sd_mock, 'query_devices', return_value=[{'name': 'Speaker', 'max_input_channels': 0}]):
            opts = props_mod.get_microphone_options()
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].value, -1)

    def test_microphone_options_no_devices_fallback(self):
        with patch.object(sd_mock, 'query_devices', return_value=[]):
            opts = props_mod.get_microphone_options()
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0].value, -1)

    def test_on_microphone_change_returns_dict(self):
        mock_props = MagicMock()
        mock_props._properties = {'x': 1}
        result = props_mod.on_microphone_change(mock_props, None)
        self.assertEqual(result, {'x': 1})

    def test_get_properties_instance(self):
        from mo.core import Properties
        props = props_mod.get_properties()
        self.assertIsInstance(props, Properties)

    def test_option_microphone_exists(self):
        props = props_mod.get_properties()
        self.assertTrue(props.has_property('option_microphone'))

    def test_option_microphone_is_select(self):
        props = props_mod.get_properties()
        self.assertEqual(props.get_type('option_microphone'), PropertyType.SELECT)

    def test_sr_exists(self):
        props = props_mod.get_properties()
        self.assertTrue(props.has_property('SR'))

    def test_sr_is_int(self):
        props = props_mod.get_properties()
        self.assertEqual(props.get_type('SR'), PropertyType.INT)

    def test_sr_default(self):
        props = props_mod.get_properties()
        self.assertEqual(props.get_default_values()['SR'], 44100)

    def test_microphone_default_set(self):
        props = props_mod.get_properties()
        self.assertIn('option_microphone', props.get_default_values())

    def test_microphone_default_no_devices(self):
        with patch.object(sd_mock, 'query_devices', return_value=[]):
            props = props_mod.get_properties()
        self.assertIn('option_microphone', props.get_default_values())


if __name__ == '__main__':
    unittest.main()
