import json

import kdclick


class IO(object):
    def __init__(self, json_only):
        self.json_only = json_only

    def out_text(self, text, **kwargs):
        """Print text. If `self.json_only` == True,
        then text will not be printed.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.echo()`.
        """
        if not self.json_only:
            kdclick.echo(text, **kwargs)

    def out_json(self, message, **kwargs):
        """Print message as json.
        :param message: Message to be printed.
        :param kwargs: Is passed to `kdclick.echo()`.
        """
        message = json.dumps(message, indent=4, sort_keys=True,
                             ensure_ascii=False)
        kdclick.echo(message, **kwargs)

    def confirm(self, text, **kwargs):
        """Prompts for confirmation (yes/no question).
        Parameter `self.json_only` must be set to False, otherwise
        `kdclick.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.confirm()`.
        :return: True or False.
        """
        if self.json_only:
            raise kdclick.UsageError(
                'Cannot perform confirmation in json-only mode')
        return kdclick.confirm(text, **kwargs)

    def prompt(self, text, **kwargs):
        """Prompts a user for input.
        Parameter `self.json_only` must be set to False, otherwise
        `kdclick.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.prompt()`.
        :return: User input.
        """
        if self.json_only:
            raise kdclick.UsageError(
                'Cannot perform user input in json-only mode')
        return kdclick.prompt(text, **kwargs)
