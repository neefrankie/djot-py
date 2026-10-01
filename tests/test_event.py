import unittest

from djot.event import (
    Event,
)

class TestEvent(unittest.TestCase):
    def test_adjust_end(self):
        event = Event.str(0, 5)
        event.adjust_end(3)

        self.assertEqual(event, Event.str(0, 3))

    def test_expand(self):
        a = Event.str(0, 5)
        b = Event.str(6, 10)

        a.expand(b)

        self.assertEqual(a, Event.str(0, 10))


if __name__ == '__main__':
    unittest.main()