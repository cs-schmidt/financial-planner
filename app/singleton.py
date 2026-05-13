import inspect
from typing import TypeVar, Any, Type, Optional
from weakref import WeakKeyDictionary


T = TypeVar("T")


class Singleton(type):
    """Metaclass for implementing the singleton class pattern."""

    _instance_cache: WeakKeyDictionary[Type[T], T] = WeakKeyDictionary()

    def __call__(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        if cls not in Singleton._instance_cache:
            instance = super().__call__(*args, **kwargs)
            Singleton._instance_cache[cls] = instance
        return Singleton._instance_cache[cls]

    # ----------------------------------------------------------------------
    # Static Methods
    # ----------------------------------------------------------------------

    @staticmethod
    def get_instance(cls: Type[T]) -> Optional[T]:
        """Return the singleton's instance if it exists or None."""
        if not inspect.isclass(cls):
            raise ValueError("Expected a class object to be passed.")
        return Singleton._instance_cache.get(cls)

    @staticmethod
    def drop_instance(cls: Type[T]) -> None:
        """Remove the singleton's instance from the cache."""
        if not inspect.isclass(cls):
            raise ValueError("Expected a class object to be passed.")
        Singleton._instance_cache.pop(cls)
