"""API management class and base class for the different end points."""

import logging
from pprint import pformat
from typing import Any, Callable, Dict, Iterator, List, Optional, Union, ValuesView

from aiounifi.events import event as unifi_event

LOGGER = logging.getLogger(__name__)

SOURCE_DATA = "data"
SOURCE_EVENT = "event"


class APIItem:
    """Base class for all end points using APIItems class."""

    def __init__(self, raw: dict, request) -> None:
        """Initialize API item."""
        self._raw = raw
        self._request = request
        self._event: Optional[unifi_event] = None
        self._source = SOURCE_DATA
        self._callbacks: List[Callable] = []

    @property
    def raw(self) -> dict:
        """Read only raw data."""
        return self._raw

    @property
    def event(self) -> Optional[unifi_event]:
        """Read only event data."""
        return self._event

    @property
    def last_updated(self) -> str:
        """Which source, data or event last called update."""
        return self._source

    def update(
        self, raw: Optional[dict] = None, event: Optional[unifi_event] = None
    ) -> None:
        """Update raw data and signal new data is available."""
        if raw:
            self._raw = raw
            self._source = SOURCE_DATA

        elif event:
            self._event = event
            self._source = SOURCE_EVENT

        else:
            return None

        for signal_update in self._callbacks:
            signal_update()

    def register_callback(self, callback: Callable) -> None:
        """Register callback for signalling.

        Callback will be used by update.
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable) -> None:
        """Remove registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)


class APIItems:
    """Base class for a map of API Items."""

    KEY = ""

    def __init__(self, raw: list, request, path: str, item_cls: Any) -> None:
        """Initialize API items."""
        self._request = request
        self._path = path
        self._item_cls = item_cls
        self._items: Dict[Union[int, str], Any] = {}
        self.process_raw(raw)
        LOGGER.debug(pformat(raw))

    async def update(self) -> None:
        """Refresh data."""
        raw = await self._request("get", self._path)
        self.process_raw(raw)

    def process_raw(self, raw: list) -> set:
        """Process data."""
        new_items = set()

        for raw_item in raw:
            key = raw_item[self.KEY]
            obj = self._items.get(key)

            if obj is not None:
                obj.update(raw=raw_item)
            else:
                self._items[key] = self._item_cls(raw_item, self._request)
                new_items.add(key)

        return new_items

    def process_event(self, events: list) -> set:
        """Process event."""
        new_items = set()

        for event in events:
            obj = self._items.get(event.mac)

            if obj is not None:
                obj.update(event=event)
                new_items.add(event.mac)

        return new_items

    def remove(self, raw: list) -> set:
        """Remove list of items."""
        removed_items = set()

        for raw_item in raw:
            key = raw_item[self.KEY]

            if key in self._items:
                self._items.pop(key)
                removed_items.add(key)

        return removed_items

    def values(self) -> ValuesView[APIItem]:
        """Return item values."""
        return self._items.values()

    def __getitem__(self, obj_id: str) -> Optional[APIItem]:
        """Get item value based on key."""
        try:
            return self._items[obj_id]
        except KeyError:
            LOGGER.error(f"Couldn't find key: {obj_id}")
        return None

    def __iter__(self) -> Iterator[Union[int, str]]:
        """Allow iterate over items."""
        return iter(self._items)
