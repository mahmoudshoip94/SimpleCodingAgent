class Memory:
    def __init__(self):
        self.last_action = ""
        self.recent_files = []
        self.last_folder = ""

    def update(self, action="", files=None, folder=""):
        if files is None:
            files = []

        if action:
            self.last_action = action

        if files:
            for file in files:
                if file not in self.recent_files:
                    self.recent_files.append(file)

            # احتفظ بآخر 5 ملفات فقط
            self.recent_files = self.recent_files[-5:]

        if folder:
            self.last_folder = folder

    def clear(self):
        self.last_action = ""
        self.recent_files.clear()
        self.last_folder = ""