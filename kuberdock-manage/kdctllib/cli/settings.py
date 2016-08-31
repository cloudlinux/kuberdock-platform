class Settings(object):
    app_description = None
    working_directory = None


class KCliSettings(Settings):
    app_description = 'Kuberdock command line utilities'
    working_directory = '~/.kcli2/'


class KDCtlSettings(Settings):
    app_description = "Kuberdock admin utilities"
    working_directory = '~/.kdctl/'
