import unittest
from mock import Mock


class TestStreamLimitTracker(unittest.TestCase):
    def import_sut(self):
        # Having the import statement here helps isolate import errors
        from videostreaming import StreamLimitTracker
        return StreamLimitTracker

    def create_subscription(self, limit):
        """
        Test helper to create a mock subscription and
        sets the limit
        """
        sub = Mock()
        sub.get_stream_limit.return_value = limit
        return sub

    def create_cache(self, test_user_id, num_keys):
        """
        Test helper to create a mock cache
        """
        StreamLimitTracker = self.import_sut()
        test_cache = Mock()
        test_cache.iter_keys.return_value = [
            StreamLimitTracker.KEY_TEMPLATE.format(test_user_id, x)
            for x in xrange(num_keys)
            ]
        return test_cache

    def test_stream_limits_user_not_authenticated(self):
        test_user = Mock()
        test_user.is_authenticated.return_value = False
        StreamLimitTracker = self.import_sut()
        tracker = StreamLimitTracker(test_user, Mock())
        test_user.subscriptions = []
        expected = StreamLimitTracker.DEFAULT_LIMIT
        limit = tracker.stream_limits(test_user)
        self.assertEqual(limit, expected)

    def test_stream_limits_without_subscription(self):
        test_user = Mock()
        test_user.is_authenticated.return_value  = True
        StreamLimitTracker = self.import_sut()
        tracker = StreamLimitTracker(test_user, Mock())
        test_user.subscriptions = []
        expected = StreamLimitTracker.DEFAULT_LIMIT
        limit = tracker.stream_limits(test_user)
        self.assertEqual(limit, expected)

    def test_stream_limits_with_subscriptions(self):
        test_user = Mock()
        test_user.is_authenticated.return_value  = True
        StreamLimitTracker = self.import_sut()
        tracker = StreamLimitTracker(test_user, Mock())

        test_sub_limit_1 = 1
        test_sub_limit_2 = 3
        test_sub_limit_3 = 2

        test_user.subscriptions = [
            self.create_subscription(test_sub_limit_1),
            self.create_subscription(test_sub_limit_2),
            self.create_subscription(test_sub_limit_3)
            ]

        expected = sum(
            (test_sub_limit_1, test_sub_limit_2, test_sub_limit_3)
            )
        limit = tracker.stream_limits(test_user)
        self.assertEqual(limit, expected)

    def test_current_stream_count(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        key_count = 5
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)

        expected_count = key_count
        count = tracker.current_stream_count(tracker.user)
        self.assertEqual(count, expected_count)

    def test_is_at_limit_not_at_stream_limit(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.is_authenticated.return_value  = True
        test_user.id = 123
        test_sub_limit = 2
        key_count = 1
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)

        test_user.subscriptions = [
            self.create_subscription(test_sub_limit)
            ]
        expected_number = test_sub_limit
        at_limit = tracker.is_at_limit(tracker.user)
        self.assertFalse(at_limit)

    def test_is_at_limit_at_stream_limit(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.is_authenticated.return_value  = True
        test_user.id = 123
        test_sub_limit = 2
        key_count = 2
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)

        test_user.subscriptions = [
            self.create_subscription(test_sub_limit)
            ]
        expected_number = test_sub_limit
        at_limit = tracker.is_at_limit(tracker.user)
        self.assertTrue(at_limit)

    def test_track_stream_with_legacy_devices(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        test_user.is_authenticated.return_value  = True
        test_sub_limit = 1
        key_count = 0
        test_user.subscriptions = [self.create_subscription(test_sub_limit)]
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)
        test_instance_id = 7654
        default_ttl = 70
        key = tracker.format_key(tracker.user.id, test_instance_id)

        self.assertFalse(tracker.is_at_limit(tracker.user))
        self.assertEqual(tracker.current_stream_count(tracker.user), key_count)

        # legacy devices have no device id
        tracker.track_stream(tracker.user, test_instance_id, device_id=None)
        tracker.cache.set.assert_called_with(
            key,
            StreamLimitTracker.DEVICE_LEGACY_VALUE,
            nx=True
            )

        tracker.cache.expire.assert_called_with(
            key, timeout=default_ttl
            )

    def test_track_stream_new_devices(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        test_user.is_authenticated.return_value  = True
        test_sub_limit = 1
        key_count = 0
        test_user.subscriptions = [self.create_subscription(test_sub_limit)]
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)
        test_instance_id = 7654
        test_device_id = 'iphone_6_plus'
        test_ttl = 60
        key = tracker.format_key(tracker.user.id, test_instance_id)

        self.assertFalse(tracker.is_at_limit(tracker.user))
        self.assertEqual(tracker.current_stream_count(tracker.user), key_count)

        # legacy devices have device ids
        tracker.track_stream(
            tracker.user, test_instance_id, device_id=test_device_id, ttl=test_ttl
            )

        tracker.cache.set.assert_called_with(
            key,
            test_device_id,
            nx=True
            )

        tracker.cache.expire.assert_called_with(
            key, timeout=test_ttl
            )

    def test_expire_stream(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        test_user.is_authenticated.return_value  = True
        test_sub_limit = 1
        key_count = 0
        test_user.subscriptions = [self.create_subscription(test_sub_limit)]
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)
        test_instance_id = 7654
        test_device_id = 'iphone_6_plus'
        test_ttl = 60
        key = tracker.format_key(tracker.user.id, test_instance_id)

        tracker.expire_stream(tracker.user, test_instance_id)

        tracker.cache.expire.assert_called_with(key, timeout=0)

    def test_expire_stream(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        test_user.is_authenticated.return_value  = True
        test_sub_limit = 1
        key_count = 0
        test_user.subscriptions = [self.create_subscription(test_sub_limit)]
        test_cache = self.create_cache(test_user.id, key_count)
        tracker = StreamLimitTracker(test_user, test_cache)

        test_instance_id = 7654
        test_device_id = 'iphone_6_plus'
        test_ttl = 60
        key = tracker.format_key(tracker.user.id, test_instance_id)

        tracker.expire_stream(tracker.user, test_instance_id)

        tracker.cache.expire.assert_called_with(key, timeout=0)

    def test_streaming_device_ids(self):
        StreamLimitTracker = self.import_sut()
        test_user = Mock()
        test_user.id = 123
        test_user.is_authenticated.return_value  = True
        test_sub_limit = 2
        key_count = 0
        test_user.subscriptions = [self.create_subscription(test_sub_limit)]

        # This dummy cache allows for state which the test mock above doesn't
        # allow for. This helps in testing the returning of the list of keys
        class DummyCache(object):
            def __init__(self):
                self._cache = {}

            def iter_keys(self, pattern):
                return self._cache.keys()

            def set(self, key, value, nx=True):
                self._cache[key] = value

            def get(self, key):
                return self._cache[key]

            def expire(self, key, timeout=70):
                pass

        test_cache = DummyCache()
        test_instance_id = 7654
        test_device_id = 'android'
        test_ttl = 60
        tracker = StreamLimitTracker(test_user, test_cache)

        tracker.track_stream(tracker.user, test_instance_id, device_id=test_device_id)
        streaming_device_ids = tracker.streaming_device_ids(tracker.user)
        self.assertIn(test_device_id, streaming_device_ids)
