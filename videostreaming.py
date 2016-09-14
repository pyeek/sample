import redis


class StreamLimitTracker(object):
    KEY_TEMPLATE = 'streamlimit:{}:{}'
    KEY_PATTERN = 'streamlimit:{}:*'
    DEFAULT_LIMIT = 1
    DEVICE_LEGACY_VALUE = 'legacy'

    @classmethod
    def with_defaults(cls, user):
        """
        Convenience method for creating a tracker with defaults
        """
        return cls(user, redis)

    def __init__(self, user, cache_lib):
        """
        This class is used for tracking simultaneous video streaming limits
        based off of user subscriptions
        """
        self.cache = cache_lib
        self.user = user

    def stream_limits(self, user):
        """ Returns the total stream limit for a given user """
        if not user.is_authenticated():
            limit = self.DEFAULT_LIMIT
        else:
            limit = sum((sub.get_stream_limit() for sub in user.subscriptions))
            if limit < self.DEFAULT_LIMIT:
                limit = self.DEFAULT_LIMIT
        return limit

    def current_stream_count(self, user):
        """
        Returns the current tracked stream count
        """
        keys = [
            key for key in self.cache.iter_keys(
                self.KEY_PATTERN.format(user.id)
                )
            ]
        return len(keys)

    def is_at_limit(self, user):
        """ Returns if a user is at their limit """
        limits = self.stream_limits(user)
        count = self.current_stream_count(user)
        return count >= limits

    def track_stream(self, user, instance_id, device_id=None, ttl=70):
        """ Tracks a new stream """
        key = self.format_key(user.id, instance_id)
        tracked_value = device_id if device_id is not None else self.DEVICE_LEGACY_VALUE
        self.cache.set(key, tracked_value, nx=True)
        self.cache.expire(key, timeout=ttl)

    def streaming_device_ids(self, user):
        return [self.cache.get(key) for key in self.cache.iter_keys(self.KEY_PATTERN.format(user.id))]

    def format_key(self, user_id, instance_id):
        return self.KEY_TEMPLATE.format(user_id, instance_id)

    def expire_stream(self, user, instance_id):
        """
        Decrements the number of streams tracked
        """
        cache_key = self.format_key(user.id, instance_id)
        self.cache.expire(cache_key, timeout=0)
