import asyncio
import functools
import datetime
import random

def probalistic_cache(max_age, max_delay):
    """
    A decorator for caching asynchronous function calls with an added 
    probabilistic factor that governs the fetching of new data to avoid hitting
    the server with concurrent requests immediately after cache expiry.

    The probability to fetch new data instead of using the cache begins at 0%
    when the cache expires and increases linearly over time until it reaches
    100% at a specified `max_delay`.

    Args:
    max_age (int): The maximum age of cached data in seconds. Cached data older
        than `max_age` is considered stale.
    max_delay (int): The duration in seconds from the time the cache expires
                     until the probability of using stale cache reaches 100%.

    Returns:
    function: A wrapped coroutine that incorporates caching behavior with
    probabilistic data fetching.

    Usage example:
    -------------
    @probalistic_cache(max_age=30, max_delay=60)
    async def fetch_data(url):
        # Your async fetch logic here
        return data

    This decorator stores results of function calls in a cache with a unique
    key for each set of arguments. 
    Cached values are returned if a subsequent call is made with the same
    arguments before `max_age`  has passed. If a call is made after `max_age`, 
    there's a chance the cache will still be used,  growing incrementally until
    `max_delay` seconds, at which point the cache will no longer be used and
    new data will be fetched.
    """
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            # Create a unique key based on the function's arguments.
            key = (args, frozenset(kwargs.items()))
            # Check if we have a result in the cache.
            current_time = datetime.datetime.now()
            if key in cache:
                result, timestamp = cache[key]
                age = (current_time - timestamp).total_seconds()
                # If cache is fresh, return result.
                if age < max_age:
                    return result
                else:
                    # Calculate elapsed time since the cache expired
                    elapsed_time_since_expiry = age - max_age
                    # The probability grows as more time elapses
                    # past the max_age threshold.
                    probability_to_use_cache = min(
                        1, elapsed_time_since_expiry / max_delay
                    )
                    if random.random() < probability_to_use_cache:
                        # Expired but within the probabilistic allowance to 
                        # use cache.
                        return result
                    # Cache is outdated and not within the probability to use 
                    # stale data, refresh it.
                    del cache[key]

            # Obtain new result since the cache is either empty or stale.
            result = await func(*args, **kwargs)
            # Update the cache with the new result.
            cache[key] = (result, current_time)
            return result
        
        return wrapped
    return decorator

# Example asynchronous function that fetches data from a URL.
@probalistic_cache(max_age=30, max_delay=60)  # Max age is 30 seconds,
async def fetch_data(url):              #  max delay for stale data use is 60s 
    """
    Simulates an asynchronous fetch to a given URL.
    
    Args:
    url (str): The URL to fetch the data from.

    Returns:
    str: A string representing the fetched data.
    """
    # Simulate a network request with a sleep
    await asyncio.sleep(1)
    print('fetching_data')
    return f"Data from {url}"

# Example main function to demonstrate the usage
async def main():
    url = "http://example.com"
    await fetch_data(url)
    # Make concurrent requests to demonstrate cache behavior.
    responses = await asyncio.gather(*(fetch_data(url) for _ in range(10)))
    for response in responses:
        print(response)

# Run the asynchronous main function to test.
if __name__ == "__main__":
    asyncio.run(main())


"""
"Stale data" refers to information that is no longer fresh or up-to-date. In
the context of caching systems, stale data is data that has been retrieved and
stored at an earlier time and has since surpassed its defined freshness 
lifetime, meaning it may not reflect the current state or version of the data 
if it has been updated at the source after it was cached.

Here's how stale data comes into play in caching:

# Fresh Cache:
When data is first retrieved and cached, it is considered fresh. A predefined 
    time-to-live (TTL) or maximum age is often associated with cached data, 
    during which the data is considered to be valid.

# Stale Threshold:
Once the TTL or maximum age passes, the cached data is then considered stale. 
In most cache implementations, when a request for this data is made after it
has become stale, the system will either update the cache with fresh data from
the source or apply specific rules before serving the stale data (such as
checking for changes or waiting for an update to complete).

# Handling Stale Data:
Some caching strategies allow stale data to be served under certain conditions,
such as when the source is temporarily unavailable or when performance is
considered more critical than accuracy. These strategies often involve
trade-offs based on the specific requirements of the system and the tolerance
for outdated information.

# Probabilistic Use of Stale Data:
Stale data can be governed by a probabilistic factor to prevent a sudden rush
of requests to update the cache as soon as data expires. This approach can help
smooth out load spikes by gradually increasing the likelihood that stale data
will be used as the time since its expiration grows, up to a certain delay
limit after which the data must be refreshed.
"""
