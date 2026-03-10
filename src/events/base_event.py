from abc import ABC, abstractmethod


class BaseEventRule(ABC):
    """Abstract base class for all event detection rules.

    Each rule receives the current state from the pipeline and returns
    a list of Event objects (empty list if nothing detected).
    """

    @abstractmethod
    def evaluate(self, tracks, frame_data, track_manager):
        """Evaluate the rule against the current pipeline state.

        Args:
            tracks: List of confirmed Track objects from the current frame.
            frame_data: FrameData for the current frame.
            track_manager: TrackManager with active/completed track history.

        Returns:
            List of Event objects (may be empty).
        """
        pass

    @property
    @abstractmethod
    def name(self):
        """Human-readable name for this rule."""
        pass
