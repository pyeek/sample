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


        Notes::

            Since we won't be discussing this code in person, I have left some extra comments

            The reason I wrote chose this code was because it illustrates various considerations
            I view as important within a code base. It also had various constraints at the time
            when I wrote this code which lead to certain decisions as well.

            This was a new feature which I implemented in a day. The feature was to limit
            the number of videos a user can watch simultaneously based off of their subscription plan
            limits. In addition to being a new feature, it also had to work with older versions of the
            app which didn't have certain data available.

            Since the feature needed to be backwards compatible, it was designed to piggyback off of
            an existing call to a API to track video view history (how much of a video they watched)
            which is called when the video plays and is called every 60 seconds while the video is playing.

            The way this works is that it tracks user's list of "view session" where each item in that list is
            a key/value pair with a given ttl (70 seconds by default). Every time the history api updates,
            the key/value pair is extended. If a video is stopped, the history update also stops and the
            key/value pair expires on its own. If the number of tracked key value pairs hits the limit, the
            player can display a message telling the user they have reached their limit.

        Considerations::

            The code using this primarily deals with a given user object and since the properties involved
            with the user object doesn't reach deep into the user object, I have chosen the user object as
            the primary dependency in terms of the API's "usability"

            The methods here are typically kept very short so that they are easily testable and readable.
            I believe in writing testable code and method size and the ability to pass dependencies enables
            the developer to do so. 

            Having said that, you may find it odd that the user is passed in every method. Normally, given
            that the user object is already injected into the __init__ method, there is no reason to not just
            use the injected user object. The reason in this particular case is that at the time of writing
            this code, I was attempting to understand functional programming practice of pure functions and
            apply that to my code where possible, even though Python does not have the same support of functional
            programming concepts.

            Except for `track_stream` and `expire_stream`, none of the function has any side effects and in
            addition, none of the methods mutates the user object in any way.

            If you have experience with functional programming, you may be thinking, he isn't using `map`, `reduce`
            `filter` and applying items over collections. The methods such as sum, method calls within list
            comprehension/generator expressions has essentially the same effect and are some of the more common
            constructs in Python
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
        """ Returns the current tracked stream count """
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
        """
        Helper method that returns the key.
        """
        return self.KEY_TEMPLATE.format(user_id, instance_id)

    def expire_stream(self, user, instance_id):
        """
        Decrements the number of streams tracked
        """
        cache_key = self.format_key(user.id, instance_id)
        self.cache.expire(cache_key, timeout=0)
