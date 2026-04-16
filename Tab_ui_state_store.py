class TabUIStateStore:
    """Memorizza in memoria lo stato volatile dei controlli per ciascuna tab."""

    def __init__(self):
        self._tab_states = {}

    def save_state(self, tab_name, state):
        if not tab_name:
            return

        self._tab_states[tab_name] = dict(state or {})

    def get_state(self, tab_name):
        return dict(self._tab_states.get(tab_name, {}))

    def clear_state(self, tab_name):
        self._tab_states.pop(tab_name, None)
