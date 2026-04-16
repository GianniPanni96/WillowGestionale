class EventBus:
    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, handler):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type, handler):
        handlers = self.subscribers.get(event_type)
        if not handlers:
            return

        try:
            handlers.remove(handler)
        except ValueError:
            return

        if not handlers:
            del self.subscribers[event_type]

    def publish(self, event_type, data):
        if event_type in self.subscribers:
            for handler in list(self.subscribers[event_type]):
                handler(data)
