import time
import functools

def async_profile_step(name):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            end = time.perf_counter()
            print(f"[PROFILE] {name} took {end - start:.2f} seconds")
            return result
        return wrapper
    return decorator
