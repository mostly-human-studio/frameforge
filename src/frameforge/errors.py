"""User-facing errors. Every error carries an actionable recovery hint."""


class FrameForgeError(Exception):
    exit_code = 1

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class ProjectNotFound(FrameForgeError):
    exit_code = 2


class ApprovalRequired(FrameForgeError):
    exit_code = 3


class MissingArtifact(FrameForgeError):
    exit_code = 4


class CorruptState(FrameForgeError):
    exit_code = 5


class InvalidArtifact(FrameForgeError):
    exit_code = 6
