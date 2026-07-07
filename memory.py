class Memory:
    def __init__(self):
        self.last_action = ""
        self.recent_files = []
        self.last_folder = ""

    def update(self, action="", files=[], folder=""):
        if action:
            self.last_action = action

        if files:
            self.recent_files.extend(files)

        if folder:
            self.last_folder = folder

    def clear(self):
        self.last_action = ""
        self.recent_files = []
        self.last_folder = ""