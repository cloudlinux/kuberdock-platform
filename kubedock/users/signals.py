from blinker import Namespace

users_signals = Namespace()
user_logged_in = users_signals.signal('user_logged_in')
user_logged_out = users_signals.signal('user_logged_out')
user_logged_in_by_another = users_signals.signal('user_logged_in_by_another')
user_logged_out_by_another = users_signals.signal('user_logged_out_by_another')
