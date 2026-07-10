from agentos.core.state import AgentState, ErrorEntry


class AgentLoopDeadError(Exception):
    pass


class FeedbackController:
    def __init__(self, max_retry: int = 3):
        self._max_retry = max_retry

    def process(self, state: AgentState, exit_code: int, stderr: str) -> bool:
        if exit_code == 0:
            return False
        from agentos.feedback.extractor import extract_error
        entry = extract_error(stderr)
        if entry is None:
            return False
        state.error_logs.append(entry)
        recent = state.error_logs[-self._max_retry:]
        if len(recent) >= self._max_retry:
            if all(e.error_type == recent[0].error_type
                   and e.message == recent[0].message
                   and e.location == recent[0].location
                   for e in recent):
                raise AgentLoopDeadError(
                    f"dead loop detected: {self._max_retry} identical errors"
                )
        return True
