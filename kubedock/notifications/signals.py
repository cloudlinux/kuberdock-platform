from blinker import Namespace

notification_signals = Namespace()
notification_send = notification_signals.signal('notification_send')