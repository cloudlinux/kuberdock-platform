from blinker import Namespace

pods_signals = Namespace()
allocate_ip_address = pods_signals.signal('allocate_ip_address')
