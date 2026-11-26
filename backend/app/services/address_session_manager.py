
import threading
from typing import Any


class AddressSelectionSession:
    def __init__(self):
        self.condition = threading.Condition()

        # Address selection (A1)
        self.suggestions: list[dict[str, str]] = []
        self.selected_suggestion_id: str | None = None

        # Provider selection (A3)
        self.providers: list[str] = []
        self.selected_provider: str | None = None

        # Shared pending-session state
        self.pending_type: str | None = None
        self.published = False
        self.completed = False
        self.result: dict[str, Any] | None = None

    def publish_and_wait(self, suggestions, timeout=600):
        """Publish address suggestions and wait for the caller's choice."""
        with self.condition:
            if self.completed:
                raise RuntimeError("Automation has already completed.")

            self.suggestions = suggestions
            self.providers = []
            self.pending_type = "ADDRESS"
            self.published = True
            self.condition.notify_all()

            ready = self.condition.wait_for(
                lambda: self.selected_suggestion_id is not None
                or self.completed,
                timeout=timeout,
            )

            if not ready:
                raise TimeoutError("Address selection timed out.")

            if self.completed:
                raise RuntimeError(
                    "Automation ended before address selection."
                )

            return self.selected_suggestion_id

    def publish_providers_and_wait(self, providers, timeout=600):
        """Publish available providers and wait for customer confirmation."""
        with self.condition:
            if self.completed:
                raise RuntimeError("Automation has already completed.")

            if not providers:
                raise ValueError("No available providers were supplied.")

            self.providers = list(providers)
            self.suggestions = []
            self.pending_type = "PROVIDER"
            self.published = True
            self.condition.notify_all()

            ready = self.condition.wait_for(
                lambda: self.selected_provider is not None
                or self.completed,
                timeout=timeout,
            )

            if not ready:
                raise TimeoutError("Provider selection timed out.")

            if self.completed:
                raise RuntimeError(
                    "Automation ended before provider confirmation."
                )

            return self.selected_provider

    def wait_for_initial_result(self, timeout=150):
        """Wait until the worker publishes its first customer decision."""
        with self.condition:
            self.condition.wait_for(
                lambda: self.published or self.completed,
                timeout=timeout,
            )

            return {
                "published": self.published,
                "pending_type": self.pending_type,
                "completed": self.completed,
                "suggestions": self.suggestions,
                "providers": self.providers,
                "result": self.result,
            }

    def choose(self, suggestion_id):
        """Submit an address choice."""
        with self.condition:
            if (
                not self.published
                or self.completed
                or self.pending_type != "ADDRESS"
            ):
                raise ValueError(
                    "There is no pending address selection."
                )

            allowed = {
                item["suggestion_id"]
                for item in self.suggestions
            }

            if suggestion_id != "NONE_OF_THESE":
                if suggestion_id not in allowed:
                    raise ValueError(
                        "Invalid address suggestion ID."
                    )

            if self.selected_suggestion_id is not None:
                raise ValueError(
                    "An address selection was already submitted."
                )

            self.selected_suggestion_id = suggestion_id
            self.published = False
            self.pending_type = None
            self.condition.notify_all()

    def choose_provider(self, provider):
        """Submit a provider choice, matching the portal's option."""
        with self.condition:
            if (
                not self.published
                or self.completed
                or self.pending_type != "PROVIDER"
            ):
                raise ValueError(
                    "There is no pending provider selection."
                )

            matched = next(
                (
                    item for item in self.providers
                    if item.casefold() == provider.strip().casefold()
                ),
                None,
            )

            if matched is None:
                raise ValueError(
                    "Selected provider is not among the available providers."
                )

            if self.selected_provider is not None:
                raise ValueError(
                    "A provider selection was already submitted."
                )

            self.selected_provider = matched
            self.published = False
            self.pending_type = None
            self.condition.notify_all()

    def finish(self, result):
        with self.condition:
            self.result = result
            self.completed = True
            self.published = False
            self.pending_type = None
            self.condition.notify_all()


class AddressSessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict[str, AddressSelectionSession] = {}

    def create(self, order_id):
        with self._lock:
            if order_id in self._sessions:
                raise ValueError(
                    "An automation session already exists."
                )

            session = AddressSelectionSession()
            self._sessions[order_id] = session
            return session

    def get(self, order_id):
        with self._lock:
            return self._sessions.get(order_id)

    def remove(self, order_id):
        with self._lock:
            self._sessions.pop(order_id, None)


address_session_manager = AddressSessionManager()
